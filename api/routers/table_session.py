"""テーブルセッション管理 & 料理同期ルーター"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    CourseEvent,
    CourseEventResponse,
    CourseServeRequest,
    SessionTimelineResponse,
    TableSession,
    TableSessionCreate,
    TableSessionResponse,
)
from api.services.osc_controller import osc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

COURSE_ORDER = ["welcome", "appetizer", "soup", "main", "dessert"]


def _session_or_404(session_id: int, db: Session) -> TableSession:
    session = db.query(TableSession).filter(TableSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    return session


def _has_allergen(session: TableSession) -> bool:
    if not session.special_requests:
        return False
    try:
        data = json.loads(session.special_requests)
        return bool(data.get("allergies") or data.get("dietary"))
    except (json.JSONDecodeError, AttributeError):
        return False


# ─── エンドポイント ───────────────────────────────────────────────────────────


@router.post("", response_model=TableSessionResponse, status_code=201)
def create_session(data: TableSessionCreate, db: Session = Depends(get_db)):
    """ゲスト着席時にセッションを開始する"""
    session = TableSession(
        table_number=data.table_number,
        guest_count=data.guest_count,
        storyboard_id=data.storyboard_id,
        show_id=data.show_id,
        special_requests=data.special_requests,
        status="seated",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    osc.session_start(session.id, session.table_number)
    logger.info("Session started: id=%d table=%d guests=%d", session.id, session.table_number, session.guest_count)
    return session


@router.get("", response_model=list[TableSessionResponse])
def list_sessions(status: Optional[str] = None, db: Session = Depends(get_db)):
    """セッション一覧（status でフィルタ可能。未指定時はアクティブセッションのみ）"""
    q = db.query(TableSession)
    if status:
        q = q.filter(TableSession.status == status)
    else:
        q = q.filter(TableSession.status != "completed")
    return q.order_by(TableSession.started_at.desc()).all()


@router.get("/{session_id}", response_model=TableSessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """セッション詳細"""
    return _session_or_404(session_id, db)


@router.post("/{session_id}/course/{course_key}/serve", response_model=TableSessionResponse)
def serve_course(
    session_id: int,
    course_key: str,
    body: CourseServeRequest = CourseServeRequest(),
    db: Session = Depends(get_db),
):
    """料理提供トリガー（テーブルへ配膳完了時に呼ぶ）"""
    session = _session_or_404(session_id, db)

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="すでに完了したセッションです")

    # セッション状態を更新
    session.current_course = course_key
    session.course_started_at = datetime.now()

    # course_key に応じてセッションステータスを更新
    if course_key == "dessert":
        session.status = "dessert"
    elif course_key in ("welcome", "appetizer", "soup", "main"):
        session.status = "dining"

    # CourseEvent を記録
    event = CourseEvent(
        session_id=session_id,
        course_key=course_key,
        event_type="served",
        notes=body.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    # OSC 送信
    osc.course_serve(session_id, course_key)

    # アレルギー対応アラート
    if _has_allergen(session):
        osc.allergen_alert(session_id)
        logger.info("Allergen alert triggered for session=%d course=%s", session_id, course_key)

    # 次コースをプリロード（現コースの次があれば）
    if course_key in COURSE_ORDER:
        idx = COURSE_ORDER.index(course_key)
        if idx + 1 < len(COURSE_ORDER):
            next_course = COURSE_ORDER[idx + 1]
            osc.course_preload(next_course)

    logger.info("Course served: session=%d course=%s", session_id, course_key)
    return session


@router.post("/{session_id}/course/{course_key}/clear", response_model=TableSessionResponse)
def clear_course(
    session_id: int,
    course_key: str,
    body: CourseServeRequest = CourseServeRequest(),
    db: Session = Depends(get_db),
):
    """料理下げトリガー（皿を下げた後に呼ぶ）"""
    session = _session_or_404(session_id, db)

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="すでに完了したセッションです")

    event = CourseEvent(
        session_id=session_id,
        course_key=course_key,
        event_type="cleared",
        notes=body.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    osc.course_clear(session_id, course_key)
    logger.info("Course cleared: session=%d course=%s", session_id, course_key)
    return session


@router.post("/{session_id}/complete", response_model=TableSessionResponse)
def complete_session(session_id: int, db: Session = Depends(get_db)):
    """セッション完了（全コース終了・退席時に呼ぶ）"""
    session = _session_or_404(session_id, db)

    if session.status == "completed":
        raise HTTPException(status_code=400, detail="すでに完了したセッションです")

    session.status = "completed"
    session.completed_at = datetime.now()
    db.commit()
    db.refresh(session)

    osc.session_complete(session_id)
    logger.info("Session completed: id=%d", session_id)
    return session


@router.get("/{session_id}/timeline", response_model=SessionTimelineResponse)
def get_session_timeline(session_id: int, db: Session = Depends(get_db)):
    """セッションのイベントタイムラインを取得"""
    session = _session_or_404(session_id, db)
    events = (
        db.query(CourseEvent)
        .filter(CourseEvent.session_id == session_id)
        .order_by(CourseEvent.timestamp)
        .all()
    )
    return SessionTimelineResponse(
        session=TableSessionResponse.model_validate(session),
        events=[CourseEventResponse.model_validate(e) for e in events],
    )
