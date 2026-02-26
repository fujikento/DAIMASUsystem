"""ショーコントロールルーター – キューベースのライブショー制御"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    Show,
    ShowCue,
    Storyboard,
    StoryboardScene,
    ShowCreate,
    ShowCueCreate,
    ShowCueUpdate,
    ShowResponse,
    ShowListResponse,
    ShowStatusResponse,
    ShowCueResponse,
)
from api.services.osc_controller import osc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shows", tags=["show_control"])

# ─── インメモリ実行状態 ────────────────────────────────────────────────────────

class ShowRuntime:
    """実行中ショーのランタイム状態（インメモリ）"""

    def __init__(self):
        # show_id -> {"cue_started_at": float, "auto_task": asyncio.Task | None}
        self._state: dict[int, dict] = {}

    def start_cue(self, show_id: int):
        entry = self._state.setdefault(show_id, {})
        entry["cue_started_at"] = time.time()
        # 既存の自動進行タスクをキャンセル
        task = entry.get("auto_task")
        if task and not task.done():
            task.cancel()
        entry["auto_task"] = None

    def set_auto_task(self, show_id: int, task: asyncio.Task):
        self._state.setdefault(show_id, {})["auto_task"] = task

    def elapsed_in_cue(self, show_id: int) -> float:
        entry = self._state.get(show_id)
        if not entry or "cue_started_at" not in entry:
            return 0.0
        return round(time.time() - entry["cue_started_at"], 2)

    def clear(self, show_id: int):
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
    import json
    data = json.dumps(payload)
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
    )


def _execute_cue(cue: ShowCue):
    """キューの内容をOSCで実行"""
    if cue.cue_type == "content" and cue.content_path:
        zones = cue.target_zones if cue.target_zones else "all"
        osc.load_content(cue.content_path, zones)
        osc.transition(cue.transition, cue.duration_seconds)

    elif cue.cue_type == "transition":
        osc.transition(cue.transition, cue.duration_seconds)

    elif cue.cue_type == "trigger" and cue.content_path:
        # BGM / 音響トリガー: content_path をBGMパスとして送信
        osc._send("/audio/bgm/load", cue.content_path, cue.duration_seconds)
        osc._send("/audio/bgm/play", 1.0, 1)

    elif cue.cue_type == "wait":
        # 待機キュー: OSC送信なし
        pass


def _get_next_cue(show_id: int, current_cue: ShowCue, db: Session) -> Optional[ShowCue]:
    return (
        db.query(ShowCue)
        .filter(ShowCue.show_id == show_id, ShowCue.sort_order > current_cue.sort_order)
        .order_by(ShowCue.sort_order)
        .first()
    )


async def _auto_follow_task(show_id: int, delay: float, db_factory):
    """auto_follow=True のキューが終わったら自動で次へ進む"""
    try:
        await asyncio.sleep(delay)
        # Open a fresh session — never reuse a request-scoped session across awaits.
        from api.models.database import SessionLocal
        db = SessionLocal()
        try:
            show = db.query(Show).filter(Show.id == show_id).first()
            if not show or show.status != "running":
                return
            if not show.current_cue_id:
                return
            current_cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
            if not current_cue:
                return
            next_cue = _get_next_cue(show_id, current_cue, db)
            if next_cue:
                show.current_cue_id = next_cue.id
                db.commit()
                _runtime.start_cue(show_id)
                _execute_cue(next_cue)
                await _broadcast_show_status(show_id, db)
                if next_cue.auto_follow:
                    total_delay = next_cue.duration_seconds + next_cue.auto_follow_delay
                    task = asyncio.create_task(_auto_follow_task(show_id, total_delay, db_factory))
                    _runtime.set_auto_task(show_id, task)
            else:
                show.status = "completed"
                show.current_cue_id = None
                db.commit()
                _runtime.clear(show_id)
                await _broadcast_show_status(show_id, db)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except asyncio.CancelledError:
        pass


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

    show.status = "running"
    show.current_cue_id = first_cue.id
    db.commit()

    _runtime.start_cue(show_id)
    _execute_cue(first_cue)

    if first_cue.auto_follow:
        total_delay = first_cue.duration_seconds + first_cue.auto_follow_delay
        task = asyncio.create_task(_auto_follow_task(show_id, total_delay, get_db))
        _runtime.set_auto_task(show_id, task)

    await _broadcast_show_status(show_id, db)
    return _build_status(show_id, db)


@router.post("/{show_id}/go", response_model=ShowStatusResponse)
async def go_next_cue(show_id: int, db: Session = Depends(get_db)):
    """次のキューへ進む（手動進行）"""
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

    show.status = "running"
    show.current_cue_id = next_cue.id
    db.commit()

    _runtime.start_cue(show_id)
    _execute_cue(next_cue)

    if next_cue.auto_follow:
        total_delay = next_cue.duration_seconds + next_cue.auto_follow_delay
        task = asyncio.create_task(_auto_follow_task(show_id, total_delay, get_db))
        _runtime.set_auto_task(show_id, task)

    await _broadcast_show_status(show_id, db)
    return _build_status(show_id, db)


@router.post("/{show_id}/goto/{cue_id}", response_model=ShowStatusResponse)
async def goto_cue(show_id: int, cue_id: int, db: Session = Depends(get_db)):
    """特定キューへジャンプ"""
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

    # 既存の自動進行タスクをキャンセル
    _runtime.start_cue(show_id)

    show.status = "running"
    show.current_cue_id = cue_id
    db.commit()

    _execute_cue(target_cue)

    if target_cue.auto_follow:
        total_delay = target_cue.duration_seconds + target_cue.auto_follow_delay
        task = asyncio.create_task(_auto_follow_task(show_id, total_delay, get_db))
        _runtime.set_auto_task(show_id, task)

    await _broadcast_show_status(show_id, db)
    return _build_status(show_id, db)


@router.post("/{show_id}/pause", response_model=ShowStatusResponse)
async def pause_show(show_id: int, db: Session = Depends(get_db)):
    """ショーを一時停止"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    if show.status != "running":
        raise HTTPException(status_code=400, detail="Show is not running")

    # 自動進行タスクをキャンセル（一時停止中は自動進行しない）
    _runtime.start_cue(show_id)  # タスクキャンセルのみ利用

    show.status = "paused"
    db.commit()

    osc.pause()
    await _broadcast_show_status(show_id, db)
    return _build_status(show_id, db)


@router.post("/{show_id}/stop", response_model=ShowStatusResponse)
async def stop_show(show_id: int, db: Session = Depends(get_db)):
    """ショーを終了"""
    show = db.query(Show).filter(Show.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    _runtime.clear(show_id)

    show.status = "completed"
    show.current_cue_id = None
    db.commit()

    osc.stop()
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
    """ショーコントロール用双方向WebSocket

    Each message gets its own short-lived DB session so we never hold a
    session across an `await` boundary (which can cause SQLite locking
    issues and stale-data problems).
    """
    import json
    from api.models.database import SessionLocal

    await ws.accept()
    _show_ws_clients.add(ws)
    logger.info("Show WS client connected (%d total)", len(_show_ws_clients))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"channel": "alert", "level": "error", "message": "Invalid JSON"}))
                continue

            channel = msg.get("channel")
            action = msg.get("action")
            data = msg.get("data", {})

            if channel != "control":
                continue

            show_id = data.get("show_id")
            if not show_id:
                continue

            # Open a fresh session for each control message.
            db = SessionLocal()
            try:
                if action == "next_cue":
                    show = db.query(Show).filter(Show.id == show_id).first()
                    if show and show.status in ("running", "paused") and show.current_cue_id:
                        current_cue = db.query(ShowCue).filter(ShowCue.id == show.current_cue_id).first()
                        if current_cue:
                            next_cue = _get_next_cue(show_id, current_cue, db)
                            if next_cue:
                                show.status = "running"
                                show.current_cue_id = next_cue.id
                                db.commit()
                                _runtime.start_cue(show_id)
                                _execute_cue(next_cue)
                                if next_cue.auto_follow:
                                    total_delay = next_cue.duration_seconds + next_cue.auto_follow_delay
                                    task = asyncio.create_task(_auto_follow_task(show_id, total_delay, get_db))
                                    _runtime.set_auto_task(show_id, task)
                                await _broadcast_show_status(show_id, db)
                            else:
                                show.status = "completed"
                                show.current_cue_id = None
                                db.commit()
                                _runtime.clear(show_id)
                                await _broadcast_show_status(show_id, db)

                elif action == "pause":
                    show = db.query(Show).filter(Show.id == show_id).first()
                    if show and show.status == "running":
                        _runtime.start_cue(show_id)
                        show.status = "paused"
                        db.commit()
                        osc.pause()
                        await _broadcast_show_status(show_id, db)

                elif action == "stop":
                    show = db.query(Show).filter(Show.id == show_id).first()
                    if show:
                        _runtime.clear(show_id)
                        show.status = "completed"
                        show.current_cue_id = None
                        db.commit()
                        osc.stop()
                        await _broadcast_show_status(show_id, db)

                elif action == "go_to_cue":
                    cue_id = data.get("cue_id")
                    if cue_id:
                        show = db.query(Show).filter(Show.id == show_id).first()
                        target_cue = db.query(ShowCue).filter(ShowCue.id == cue_id, ShowCue.show_id == show_id).first()
                        if show and target_cue:
                            _runtime.start_cue(show_id)
                            show.status = "running"
                            show.current_cue_id = cue_id
                            db.commit()
                            _execute_cue(target_cue)
                            if target_cue.auto_follow:
                                total_delay = target_cue.duration_seconds + target_cue.auto_follow_delay
                                task = asyncio.create_task(_auto_follow_task(show_id, total_delay, get_db))
                                _runtime.set_auto_task(show_id, task)
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
