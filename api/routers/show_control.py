"""ショーコントロールルーター – キューベースのライブショー制御

精度上の要件 (audit 2026-05-16):
- auto-follow task と手動 go/goto/pause が同じ show を更新すると race が起きる。
  show_id ごとに asyncio.Lock を取り、すべての state mutation を直列化する。
- expected_current_cue_id による compare-and-swap で、stale auto-task が
  ユーザー操作後の cue を勝手に進めるのを防ぐ。
- _execute_cue は OSC の送信結果を待ち、ack mode の場合は load_content の
  ack を確認してから transition を呼ぶ (黒フレーム/誤遷移防止)。
- OSC が失敗した場合は cue を進めず "degraded" を status に乗せて UI に通知する。
"""

import asyncio
import contextlib
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from api.models.database import SessionLocal, get_db
from api.models.schemas import (
    Show,
    ShowCue,
    StoryboardScene,
    ShowCreate,
    ShowCueCreate,
    ShowCueUpdate,
    ShowResponse,
    ShowListResponse,
    ShowStatusResponse,
    ShowCueResponse,
)
from api.services.osc_controller import osc, OscSendResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shows", tags=["show_control"])

# ─── インメモリ実行状態 ────────────────────────────────────────────────────────


class ShowRuntime:
    """実行中ショーのランタイム状態（インメモリ）"""

    def __init__(self):
        # show_id -> dict[
        #   cue_started_at: float,
        #   auto_task: asyncio.Task | None,
        #   lock: asyncio.Lock,
        #   degraded: bool,             # 直近 cue が OSC エラーで部分失敗した
        #   last_osc_error: str | None,
        # ]
        self._state: dict[int, dict] = {}

    def _entry(self, show_id: int) -> dict:
        entry = self._state.get(show_id)
        if entry is None:
            entry = {
                "cue_started_at": None,
                "auto_task": None,
                "lock": asyncio.Lock(),
                "degraded": False,
                "last_osc_error": None,
            }
            self._state[show_id] = entry
        return entry

    def lock(self, show_id: int) -> asyncio.Lock:
        return self._entry(show_id)["lock"]

    def start_cue(self, show_id: int) -> None:
        """新しい cue 開始のタイミングを記録し、既存の auto-task をキャンセルする。

        重要: auto-follow task 内から呼ばれた場合 (current task == auto_task)、
        自身を cancel すると次の await で CancelledError が立ち上がり、後段の
        OSC 実行や broadcast が中断される。同一 task なら no-cancel にする。
        """
        entry = self._entry(show_id)
        entry["cue_started_at"] = time.time()
        task = entry.get("auto_task")
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        if task and not task.done() and task is not current:
            task.cancel()
            entry["auto_task"] = None

    async def cancel_auto_task(self, show_id: int) -> None:
        """既存 auto-task が完全に終了するまで待つ。stale task のレースを防ぐ。"""
        entry = self._state.get(show_id)
        if not entry:
            return
        task = entry.get("auto_task")
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        entry["auto_task"] = None

    def set_auto_task(self, show_id: int, task: asyncio.Task) -> None:
        self._entry(show_id)["auto_task"] = task

    def elapsed_in_cue(self, show_id: int) -> float:
        entry = self._state.get(show_id)
        if not entry or entry.get("cue_started_at") is None:
            return 0.0
        return round(time.time() - entry["cue_started_at"], 2)

    def set_degraded(self, show_id: int, error: Optional[str]) -> None:
        entry = self._entry(show_id)
        entry["degraded"] = error is not None
        entry["last_osc_error"] = error

    def is_degraded(self, show_id: int) -> bool:
        entry = self._state.get(show_id)
        return bool(entry and entry.get("degraded"))

    def last_osc_error(self, show_id: int) -> Optional[str]:
        entry = self._state.get(show_id)
        return entry.get("last_osc_error") if entry else None

    def clear(self, show_id: int) -> None:
        entry = self._state.pop(show_id, {})
        task = entry.get("auto_task")
        if task and not task.done():
            task.cancel()


_runtime = ShowRuntime()

# WebSocket 接続管理（ショー制御専用）
_show_ws_clients: set[WebSocket] = set()


async def _broadcast_show_status(show_id: int, db: Session):
    """全WebSocketクライアントにショーステータスを配信"""
    status = _build_status(show_id, db)
    if status is None:
        return
    payload = {
        "channel": "status",
        "data": status.model_dump(),
    }
    data = json.dumps(payload, default=str)
    disconnected = set()
    for ws in _show_ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    _show_ws_clients.difference_update(disconnected)


def _build_status(show_id: int, db: Session) -> Optional[ShowStatusResponse]:
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        return None

    total = db.query(ShowCue).filter(ShowCue.show_id == show_id).count()

    current_cue_number = None
    current_cue_type = None
    completed = 0

    if show.current_cue_id:
        cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
        if cue:
            current_cue_number = cue.cue_number
            current_cue_type = cue.cue_type
            completed = (
                db.query(ShowCue)
                .filter(ShowCue.show_id == show_id, ShowCue.sort_order < cue.sort_order)
                .count()
            )

    return ShowStatusResponse(
        show_id=show_id,
        status=show.status,
        current_cue_id=show.current_cue_id,
        current_cue_number=current_cue_number,
        current_cue_type=current_cue_type,
        elapsed_in_cue=_runtime.elapsed_in_cue(show_id),
        total_cues=total,
        completed_cues=completed,
        degraded=_runtime.is_degraded(show_id),
        last_osc_error=_runtime.last_osc_error(show_id),
    )


async def _execute_cue(cue: ShowCue, show_id: int) -> bool:
    """キューの内容を OSC で実行し、成功可否を返す。

    Returns:
        True  -- すべての OSC 送信が成功 (ack mode では ack 受信)
        False -- いずれかが失敗。caller は cue 進行を止めるか degraded で続行するか決める。

    Sequencing:
        content cue は load_content -> transition の順で送る。ack mode のときは
        load_content の ack が返ってから transition を発火するので、preload
        前に transition が走って黒フレームが出るのを防げる。
    """
    last_error: Optional[str] = None

    if cue.cue_type == "content" and cue.content_path:
        zones = cue.target_zones if cue.target_zones else "all"
        load_res = osc.load_content(cue.content_path, zones)
        if not load_res.ok:
            last_error = f"load_content failed: {load_res.error or 'no ack'}"
            logger.error("[Show %s cue %s] %s", show_id, cue.id, last_error)
            _runtime.set_degraded(show_id, last_error)
            return False
        trans_res = osc.transition(cue.transition, cue.duration_seconds)
        if not trans_res.ok:
            last_error = f"transition failed: {trans_res.error or 'no ack'}"
            logger.error("[Show %s cue %s] %s", show_id, cue.id, last_error)
            _runtime.set_degraded(show_id, last_error)
            return False

    elif cue.cue_type == "transition":
        trans_res = osc.transition(cue.transition, cue.duration_seconds)
        if not trans_res.ok:
            last_error = f"transition failed: {trans_res.error or 'no ack'}"
            logger.error("[Show %s cue %s] %s", show_id, cue.id, last_error)
            _runtime.set_degraded(show_id, last_error)
            return False

    elif cue.cue_type == "trigger" and cue.content_path:
        # BGM / 音響トリガー: content_path をBGMパスとして送信
        bgm_load: OscSendResult = osc.send("/audio/bgm/load", cue.content_path, cue.duration_seconds)
        bgm_play: OscSendResult = osc.send("/audio/bgm/play", 1.0, 1)
        if not bgm_load.ok or not bgm_play.ok:
            err = bgm_load.error or bgm_play.error or "no ack"
            last_error = f"bgm trigger failed: {err}"
            logger.error("[Show %s cue %s] %s", show_id, cue.id, last_error)
            _runtime.set_degraded(show_id, last_error)
            return False

    elif cue.cue_type == "wait":
        # 待機キュー: OSC送信なし。常に成功扱い。
        pass

    _runtime.set_degraded(show_id, None)
    return True


def _get_next_cue(show_id: int, current_cue: ShowCue, db: Session) -> Optional[ShowCue]:
    return (
        db.query(ShowCue)
        .filter(ShowCue.show_id == show_id, ShowCue.sort_order > current_cue.sort_order)
        .order_by(ShowCue.sort_order)
        .first()
    )


async def _auto_follow_task(show_id: int, delay: float, expected_current_cue_id: int):
    """auto_follow=True のキューが終わったら自動で次へ進む。

    expected_current_cue_id を引数で受け取り、起動時点での current_cue_id
    と一致しない場合は no-op で終了する (stale task の race 防止)。
    Show 単位 lock も取得して手動操作と相互排他する。
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    lock = _runtime.lock(show_id)
    async with lock:
        db = SessionLocal()
        try:
            show = db.query(Show).filter(Show.id == show_id).first()
            if not show or show.status != "running":
                return
            # CAS: 期待した cue 以外を指していたら、別操作が走ったので no-op
            if show.current_cue_id != expected_current_cue_id:
                logger.info(
                    "[Auto-follow] stale task ignored: show=%s expected_cue=%s actual=%s",
                    show_id, expected_current_cue_id, show.current_cue_id,
                )
                return
            current_cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
            if not current_cue:
                return
            next_cue = _get_next_cue(show_id, current_cue, db)
            if next_cue:
                ok = await _advance_to_cue(show, next_cue, db)
                await _broadcast_show_status(show_id, db)
                if ok and next_cue.auto_follow:
                    _schedule_auto_follow(show_id, next_cue)
            else:
                show.status = "completed"
                show.current_cue_id = None
                db.commit()
                _runtime.clear(show_id)
                await _broadcast_show_status(show_id, db)
        except Exception:
            db.rollback()
            logger.exception("[Auto-follow] failed for show %s", show_id)
        finally:
            db.close()


async def _advance_to_cue(show: Show, target_cue: ShowCue, db: Session) -> bool:
    """show を target_cue に進める。

    順序 (codex review 2026-05-16 P2):
        1. OSC で _execute_cue を実行 (load_content / transition / trigger 等)
        2. OSC 成功時のみ DB を commit (current_cue_id, status) + ランタイムの cue 開始時刻
        3. OSC 失敗時は DB を rollback して degraded フラグだけ立てる
           (実際は投影されていない cue を UI/DB が「現在 cue」と見せる事故を防ぐ)

    Returns:
        True  -- OSC 成功 + DB commit 済み。caller は auto-follow を spawn してよい
        False -- OSC 失敗。show 状態は変更されていない。caller は auto-follow を spawn しないこと
    """
    ok = await _execute_cue(target_cue, show.id)
    if not ok:
        # _execute_cue 内で degraded フラグは既に立っている
        db.rollback()
        return False

    show.current_cue_id = target_cue.id
    show.status = "running"
    db.commit()
    _runtime.start_cue(show.id)
    return True


def _schedule_auto_follow(show_id: int, cue: ShowCue) -> None:
    """auto_follow=True の cue に対応する次回進行 task を spawn する。"""
    total_delay = cue.duration_seconds + cue.auto_follow_delay
    task = asyncio.create_task(
        _auto_follow_task(show_id, total_delay, expected_current_cue_id=cue.id)
    )
    _runtime.set_auto_task(show_id, task)


# ─── エンドポイント ───────────────────────────────────────────────────────────

@router.post("", response_model=ShowResponse, status_code=201)
def create_show(body: ShowCreate, db: Session = Depends(get_db)):
    """ショー作成。storyboard_id を指定するとシーンからキューを自動生成"""
    show = Show(name=body.name, storyboard_id=body.storyboard_id, status="standby")
    db.add(show)
    db.flush()  # show.id を確定

    if body.storyboard_id:
        scenes = (
            db.query(StoryboardScene)
            .filter(StoryboardScene.storyboard_id == body.storyboard_id)
            .order_by(StoryboardScene.sort_order)
            .all()
        )
        for idx, scene in enumerate(scenes):
            cue = ShowCue(
                show_id=show.id,
                cue_number=float(idx + 1),
                cue_type="content",
                target_zones=scene.target_zones or "all",
                content_path=scene.video_path or scene.image_path,
                transition=scene.transition,
                duration_seconds=float(scene.duration_seconds),
                auto_follow=False,
                auto_follow_delay=0.0,
                sort_order=idx,
            )
            db.add(cue)

    db.commit()
    db.refresh(show)
    return show


@router.get("", response_model=list[ShowListResponse])
def list_shows(db: Session = Depends(get_db)):
    """ショー一覧"""
    return db.query(Show).order_by(Show.created_at.desc()).all()


@router.get("/{show_id}", response_model=ShowResponse)
def get_show(show_id: int, db: Session = Depends(get_db)):
    """ショー詳細（キューリスト付き）"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


@router.post("/{show_id}/start", response_model=ShowStatusResponse)
async def start_show(show_id: int, db: Session = Depends(get_db)):
    """ショー開始: 最初のキューを実行"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)

        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")
        if show.status == "running":
            raise HTTPException(status_code=400, detail="Show is already running")

        first_cue = (
            db.query(ShowCue)
            .filter(ShowCue.show_id == show_id)
            .order_by(ShowCue.sort_order)
            .first()
        )
        if not first_cue:
            raise HTTPException(status_code=400, detail="Show has no cues")

        ok = await _advance_to_cue(show, first_cue, db)
        if ok and first_cue.auto_follow:
            _schedule_auto_follow(show_id, first_cue)

        await _broadcast_show_status(show_id, db)
        return _build_status(show_id, db)


@router.post("/{show_id}/go", response_model=ShowStatusResponse)
async def go_next_cue(show_id: int, db: Session = Depends(get_db)):
    """次のキューへ進む（手動進行）"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)

        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")
        if show.status not in ("running", "paused"):
            raise HTTPException(status_code=400, detail="Show is not active")
        if not show.current_cue_id:
            raise HTTPException(status_code=400, detail="No current cue")

        current_cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
        if not current_cue:
            raise HTTPException(status_code=404, detail="Current cue not found")

        next_cue = _get_next_cue(show_id, current_cue, db)
        if not next_cue:
            show.status = "completed"
            show.current_cue_id = None
            db.commit()
            _runtime.clear(show_id)
            await _broadcast_show_status(show_id, db)
            return _build_status(show_id, db)

        ok = await _advance_to_cue(show, next_cue, db)
        if ok and next_cue.auto_follow:
            _schedule_auto_follow(show_id, next_cue)

        await _broadcast_show_status(show_id, db)
        return _build_status(show_id, db)


@router.post("/{show_id}/goto/{cue_id}", response_model=ShowStatusResponse)
async def goto_cue(show_id: int, cue_id: int, db: Session = Depends(get_db)):
    """特定キューへジャンプ"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)

        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        target_cue = (
            db.query(ShowCue)
            .filter(ShowCue.id == cue_id, ShowCue.show_id == show_id)
            .first()
        )
        if not target_cue:
            raise HTTPException(status_code=404, detail="Cue not found")

        ok = await _advance_to_cue(show, target_cue, db)
        if ok and target_cue.auto_follow:
            _schedule_auto_follow(show_id, target_cue)

        await _broadcast_show_status(show_id, db)
        return _build_status(show_id, db)


@router.post("/{show_id}/pause", response_model=ShowStatusResponse)
async def pause_show(show_id: int, db: Session = Depends(get_db)):
    """ショーを一時停止"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)

        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")
        if show.status != "running":
            raise HTTPException(status_code=400, detail="Show is not running")

        show.status = "paused"
        db.commit()

        pause_res = osc.pause()
        if not pause_res.ok:
            _runtime.set_degraded(show_id, f"pause failed: {pause_res.error or 'no ack'}")

        await _broadcast_show_status(show_id, db)
        return _build_status(show_id, db)


@router.post("/{show_id}/stop", response_model=ShowStatusResponse)
async def stop_show(show_id: int, db: Session = Depends(get_db)):
    """ショーを終了"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)

        show = db.query(Show).filter(Show.id == show_id).first()
        if not show:
            raise HTTPException(status_code=404, detail="Show not found")

        _runtime.clear(show_id)

        show.status = "completed"
        show.current_cue_id = None
        db.commit()

        stop_res = osc.stop()
        if not stop_res.ok:
            logger.warning("[Show %s] OSC stop failed: %s", show_id, stop_res.error)

        await _broadcast_show_status(show_id, db)
        return _build_status(show_id, db)


@router.get("/{show_id}/status", response_model=ShowStatusResponse)
def get_show_status(show_id: int, db: Session = Depends(get_db)):
    """リアルタイムステータス取得"""
    status = _build_status(show_id, db)
    if not status:
        raise HTTPException(status_code=404, detail="Show not found")
    return status


@router.put("/{show_id}/cues/{cue_id}", response_model=ShowCueResponse)
def update_cue(
    show_id: int,
    cue_id: int,
    body: ShowCueUpdate,
    db: Session = Depends(get_db),
):
    """キュー編集"""
    cue = (
        db.query(ShowCue)
        .filter(ShowCue.id == cue_id, ShowCue.show_id == show_id)
        .first()
    )
    if not cue:
        raise HTTPException(status_code=404, detail="Cue not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cue, key, value)

    db.commit()
    db.refresh(cue)
    return cue


@router.post("/{show_id}/cues", response_model=ShowCueResponse, status_code=201)
def add_cue(show_id: int, body: ShowCueCreate, db: Session = Depends(get_db)):
    """キュー追加"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    cue = ShowCue(show_id=show_id, **body.model_dump())
    db.add(cue)
    db.commit()
    db.refresh(cue)
    return cue


# ─── WebSocket (ショー専用) ───────────────────────────────────────────────────

@router.websocket("/ws")
async def show_websocket(ws: WebSocket):
    """ショーコントロール用双方向 WebSocket。各メッセージは show_id 単位の lock
    を取って、auto-follow と直列化される。
    """
    await ws.accept()
    _show_ws_clients.add(ws)
    logger.info("Show WS client connected (%d total)", len(_show_ws_clients))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(
                    json.dumps({"channel": "alert", "level": "error", "message": "Invalid JSON"})
                )
                continue

            channel = msg.get("channel")
            action = msg.get("action")
            data = msg.get("data", {})

            if channel != "control":
                continue

            show_id = data.get("show_id")
            if not show_id:
                continue

            lock = _runtime.lock(show_id)
            async with lock:
                await _runtime.cancel_auto_task(show_id)
                db = SessionLocal()
                try:
                    show = db.query(Show).filter(Show.id == show_id).first()
                    if not show:
                        continue

                    if action == "next_cue":
                        if show.status in ("running", "paused") and show.current_cue_id:
                            current_cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
                            if current_cue:
                                next_cue = _get_next_cue(show_id, current_cue, db)
                                if next_cue:
                                    ok = await _advance_to_cue(show, next_cue, db)
                                    if ok and next_cue.auto_follow:
                                        _schedule_auto_follow(show_id, next_cue)
                                else:
                                    show.status = "completed"
                                    show.current_cue_id = None
                                    db.commit()
                                    _runtime.clear(show_id)
                                await _broadcast_show_status(show_id, db)

                    elif action == "pause":
                        if show.status == "running":
                            show.status = "paused"
                            db.commit()
                            pause_res = osc.pause()
                            if not pause_res.ok:
                                _runtime.set_degraded(show_id, f"pause failed: {pause_res.error or 'no ack'}")
                            await _broadcast_show_status(show_id, db)

                    elif action == "stop":
                        _runtime.clear(show_id)
                        show.status = "completed"
                        show.current_cue_id = None
                        db.commit()
                        stop_res = osc.stop()
                        if not stop_res.ok:
                            logger.warning("[Show %s] OSC stop failed: %s", show_id, stop_res.error)
                        await _broadcast_show_status(show_id, db)

                    elif action == "go_to_cue":
                        cue_id = data.get("cue_id")
                        if cue_id:
                            target_cue = (
                                db.query(ShowCue)
                                .filter(ShowCue.id == cue_id, ShowCue.show_id == show_id)
                                .first()
                            )
                            if target_cue:
                                ok = await _advance_to_cue(show, target_cue, db)
                                if ok and target_cue.auto_follow:
                                    _schedule_auto_follow(show_id, target_cue)
                                await _broadcast_show_status(show_id, db)
                except Exception:
                    db.rollback()
                    logger.exception("Error handling WS action '%s' for show %s", action, show_id)
                finally:
                    db.close()

    except WebSocketDisconnect:
        pass
    finally:
        _show_ws_clients.discard(ws)
        logger.info("Show WS client disconnected (%d remaining)", len(_show_ws_clients))
