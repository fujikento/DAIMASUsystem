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
                # codex round 4 P1: emergency_stop で立て、再 start 時に解除する panic flag
                # True の間は _advance_to_cue が OSC 送信を block する
                "panic_stopped": False,
            }
            self._state[show_id] = entry
        return entry

    def set_panic(self, show_id: int, panic: bool) -> None:
        self._entry(show_id)["panic_stopped"] = bool(panic)

    def is_panic(self, show_id: int) -> bool:
        entry = self._state.get(show_id)
        return bool(entry and entry.get("panic_stopped"))

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

    panic guard (codex round 4 P1): /emergency-stop で set_panic されている間は
    どんな cue 進行要求も block する。/start で reset するまで OSC を一切送らない。

    Returns:
        True  -- OSC 成功 + DB commit 済み。caller は auto-follow を spawn してよい
        False -- OSC 失敗 or panic blocked。show 状態は変更されていない。
    """
    if _runtime.is_panic(show.id):
        logger.warning(
            "[Show %s] _advance_to_cue blocked — panic flag is set. Use /start to reset.",
            show.id,
        )
        db.rollback()
        return False
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
    """ショー開始: 最初のキューを実行 (emergency-stop された後の復帰経路でもある)"""
    lock = _runtime.lock(show_id)
    async with lock:
        await _runtime.cancel_auto_task(show_id)
        # codex round 4 P1: emergency_stop 後の意図的な再開時は panic flag を解除
        _runtime.set_panic(show_id, False)
        _runtime.set_degraded(show_id, None)

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


@router.post("/{show_id}/emergency-stop", response_model=ShowStatusResponse)
async def emergency_stop_show(show_id: int, db: Session = Depends(get_db)):
    """ライブ中の致命的失敗用 — 全 OSC タスクを即時 cancel し、blackout を送る。

    通常の /stop と違って:
      - DB 状態更新を待たず、まず OSC blackout を送る
      - auto-task を sync で cancel (await しない)
      - 失敗してもエラーを上に投げない (ステージ上の操作優先)
      - showRuntime に panic flag を立てて以後の cue 進行を block
    """
    logger.warning("[Show %s] EMERGENCY STOP requested", show_id)

    # Step 0: panic flag を最初に立てる (in-flight _advance_to_cue が panic check に
    # 引っかからずに進むのを防ぐ。codex round 10 P1: それでも race window は残るので
    # Step 2 で lock を取って serialize する)
    _runtime.set_panic(show_id, True)

    # Step 1: OSC blackout を即発射 (lock 取得前 — UX 優先で 1ms でも早く真っ暗に)
    try:
        bo_res = osc.send("/projection/blackout", 1)
        logger.warning("[Show %s] blackout result: ok=%s", show_id, bo_res.ok)
    except Exception as e:
        logger.exception("[Show %s] blackout OSC failed: %s", show_id, e)

    # Step 2: in-flight _advance_to_cue が完了するのを最大 2 秒待つ。
    # その後 blackout を再送して最終 OSC として保証する。
    lock = _runtime.lock(show_id)
    try:
        async with asyncio.timeout(2.0):
            async with lock:
                try:
                    await _runtime.cancel_auto_task(show_id)
                except Exception as e:
                    logger.exception("[Show %s] cancel_auto_task failed: %s", show_id, e)
                try:
                    stop_res = osc.stop()
                    logger.warning("[Show %s] stop result: ok=%s", show_id, stop_res.ok)
                    # 最後にもう一度 blackout して in-flight 後の表示も真っ暗に保証
                    osc.send("/projection/blackout", 1)
                except Exception as e:
                    logger.exception("[Show %s] OSC stop/blackout failed: %s", show_id, e)
    except (asyncio.TimeoutError, Exception) as e:
        # lock 取得 / cancel_auto_task が 2 秒以内に終わらなくても続行する
        logger.error("[Show %s] emergency lock acquisition timeout: %s — forcing clear", show_id, e)

    _runtime.clear(show_id)
    _runtime.set_degraded(show_id, "emergency_stop")
    _runtime.set_panic(show_id, True)  # clear() 後の entry にも再設定

    # Step 3: DB 状態反映 (失敗しても継続)
    try:
        show = db.query(Show).filter(Show.id == show_id).first()
        if show:
            show.status = "emergency_stopped"
            show.current_cue_id = None
            db.commit()
    except Exception as e:
        logger.exception("[Show %s] DB rollback after emergency stop failed: %s", show_id, e)
        db.rollback()

    try:
        await _broadcast_show_status(show_id, db)
    except Exception:
        pass

    return _build_status(show_id, db) or ShowStatusResponse(
        show_id=show_id, status="emergency_stopped", current_cue_id=None,
        current_cue_number=None, current_cue_type=None, elapsed_in_cue=0.0,
        total_cues=0, completed_cues=0, degraded=True, last_osc_error="emergency_stop",
    )


@router.post("/{show_id}/blackout")
async def blackout(show_id: int) -> dict:
    """全プロジェクター黒画面化 (緊急時 / VIP プライバシー対応用)。

    DB / 状態は触らず OSC 1 発だけ送る。auto-task は止めないので復帰時は
    /resume か /go で再開できる。
    """
    logger.warning("[Show %s] BLACKOUT requested", show_id)
    try:
        res = osc.send("/projection/blackout", 1)
        return {"ok": res.ok, "error": res.error, "show_id": show_id}
    except Exception as e:
        logger.exception("[Show %s] blackout failed: %s", show_id, e)
        return {"ok": False, "error": str(e), "show_id": show_id}


@router.post("/{show_id}/unblackout")
async def unblackout(show_id: int) -> dict:
    """ブラックアウト解除 (現在 cue の表示に戻す)"""
    logger.info("[Show %s] UNBLACKOUT requested", show_id)
    try:
        res = osc.send("/projection/blackout", 0)
        return {"ok": res.ok, "error": res.error, "show_id": show_id}
    except Exception as e:
        return {"ok": False, "error": str(e), "show_id": show_id}


@router.get("/{show_id}/rehearsal/validate")
async def validate_show_for_rehearsal(show_id: int, db: Session = Depends(get_db)) -> dict:
    """ライブ投入前の事前検証 — 全 cue が成立するか、content 不足や duration ズレが
    無いかを返す。actual 投入なし。

    検査:
      1. show が存在し cue を 1 個以上持つ
      2. 各 cue の content_path が指すファイルが存在し video QC 通る
         (期待解像度なし、duration ≧ cue.duration_seconds × 0.5 を warning)
      3. auto_follow cue の duration + auto_follow_delay 累計から total runtime を算出
      4. transition / trigger cue の引数が妥当か

    返す形:
      {
        ok: bool,
        total_runtime_seconds: float,
        cues: [
          {cue_id, cue_number, cue_type, content_path, ok, errors, warnings, qc?},
          ...
        ],
        summary: {n_cues, n_ok, n_warning, n_error}
      }
    """
    from api.services.content_qc import qc_video as _qc

    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(404, "Show not found")
    cues = (
        db.query(ShowCue)
        .filter(ShowCue.show_id == show_id)
        .order_by(ShowCue.sort_order)
        .all()
    )
    if not cues:
        return {
            "ok": False,
            "total_runtime_seconds": 0,
            "cues": [],
            "summary": {"n_cues": 0, "n_ok": 0, "n_warning": 0, "n_error": 1},
            "errors": ["no_cues_defined"],
        }

    cue_results: list[dict] = []
    total_runtime = 0.0
    n_ok = n_warn = n_err = 0

    for c in cues:
        entry: dict = {
            "cue_id": c.id,
            "cue_number": c.cue_number,
            "cue_type": c.cue_type,
            "content_path": c.content_path,
            "duration_seconds": c.duration_seconds,
            "auto_follow": c.auto_follow,
            "auto_follow_delay": c.auto_follow_delay,
            "errors": [],
            "warnings": [],
        }
        # total runtime 計算
        if c.auto_follow:
            total_runtime += float(c.duration_seconds + (c.auto_follow_delay or 0))
        else:
            total_runtime += float(c.duration_seconds)

        # content cue は video file の QC
        if c.cue_type == "content":
            if not c.content_path:
                entry["errors"].append("content_path_missing")
            else:
                try:
                    qc = await _qc(
                        path=c.content_path,
                        expected_duration_seconds=float(c.duration_seconds),
                        duration_tolerance_pct=0.30,  # cue は意図的に長め短めあり
                        check_black=False,  # rehearsal validate では速さ重視で skip
                    )
                    entry["qc"] = {
                        "ok": qc.ok,
                        "width": qc.width, "height": qc.height,
                        "duration": qc.duration_seconds,
                        "errors": qc.errors, "warnings": qc.warnings,
                    }
                    if not qc.ok:
                        entry["errors"].extend(qc.errors)
                    entry["warnings"].extend(qc.warnings)
                except Exception as e:
                    entry["errors"].append(f"qc_failed: {e}")
        elif c.cue_type == "transition":
            if not c.transition:
                entry["warnings"].append("transition_type_unspecified")
        elif c.cue_type == "trigger":
            if not c.content_path:
                entry["warnings"].append("trigger_content_path_missing (BGM trigger needs path)")
        elif c.cue_type == "wait":
            pass  # 待機 cue は何もチェックしない
        else:
            entry["warnings"].append(f"unknown_cue_type: {c.cue_type}")

        entry["ok"] = not entry["errors"]
        if entry["errors"]:
            n_err += 1
        elif entry["warnings"]:
            n_warn += 1
        else:
            n_ok += 1
        cue_results.append(entry)

    return {
        "ok": n_err == 0,
        "total_runtime_seconds": round(total_runtime, 1),
        "cues": cue_results,
        "summary": {
            "n_cues": len(cues),
            "n_ok": n_ok,
            "n_warning": n_warn,
            "n_error": n_err,
        },
    }


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
