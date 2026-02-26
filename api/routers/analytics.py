"""分析APIルーター

ダッシュボード、セッション分析、生成パフォーマンス、イベントログを提供。
"""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, case, text
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    EventLog,
    EventLogCreate,
    EventLogResponse,
    GenerationMetrics,
    GenerationMetricsCreate,
    GenerationMetricsResponse,
    DashboardSummary,
    ProviderStats,
    ThemeStats,
    Storyboard,
    StoryboardScene,
    PlaybackLog,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ─── ダッシュボードサマリー ─────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    """今日の統計サマリーを返す"""
    today_str = date.today().isoformat()
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = today_start + timedelta(days=1)

    # セッション数（今日のPlaybackLog）
    total_sessions = (
        db.query(func.count(PlaybackLog.id))
        .filter(PlaybackLog.started_at >= today_start, PlaybackLog.started_at < today_end)
        .scalar()
        or 0
    )

    # 生成数（今日のGenerationMetrics）
    gen_query = db.query(GenerationMetrics).filter(
        GenerationMetrics.timestamp >= today_start,
        GenerationMetrics.timestamp < today_end,
    )
    total_generations = gen_query.count()

    success_count = gen_query.filter(GenerationMetrics.status == "success").count()
    success_rate = (success_count / total_generations * 100) if total_generations > 0 else 0.0

    # 平均生成時間（画像/動画別）
    avg_image = (
        db.query(func.avg(GenerationMetrics.total_duration_ms))
        .filter(
            GenerationMetrics.timestamp >= today_start,
            GenerationMetrics.timestamp < today_end,
            GenerationMetrics.generation_type == "image",
            GenerationMetrics.status == "success",
        )
        .scalar()
    )
    avg_video = (
        db.query(func.avg(GenerationMetrics.total_duration_ms))
        .filter(
            GenerationMetrics.timestamp >= today_start,
            GenerationMetrics.timestamp < today_end,
            GenerationMetrics.generation_type == "video",
            GenerationMetrics.status == "success",
        )
        .scalar()
    )

    # 合計コスト
    total_cost = (
        db.query(func.sum(GenerationMetrics.cost_estimate))
        .filter(
            GenerationMetrics.timestamp >= today_start,
            GenerationMetrics.timestamp < today_end,
        )
        .scalar()
        or 0.0
    )

    # カテゴリー別イベント数
    category_rows = (
        db.query(EventLog.event_category, func.count(EventLog.id))
        .filter(
            EventLog.timestamp >= today_start,
            EventLog.timestamp < today_end,
        )
        .group_by(EventLog.event_category)
        .all()
    )
    event_counts = {row[0]: row[1] for row in category_rows}

    return DashboardSummary(
        date=today_str,
        total_sessions=total_sessions,
        total_generations=total_generations,
        generation_success_rate=round(success_rate, 1),
        avg_image_duration_ms=round(avg_image, 1) if avg_image else None,
        avg_video_duration_ms=round(avg_video, 1) if avg_video else None,
        total_cost_estimate=round(total_cost, 4),
        event_counts_by_category=event_counts,
    )


# ─── セッション分析 ────────────────────────────────────────────────────────


@router.get("/sessions")
def get_sessions(
    period: str = Query("daily", description="daily or weekly"),
    days: int = Query(7, description="集計対象の日数"),
    db: Session = Depends(get_db),
):
    """日別/週別セッション分析"""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            func.date(PlaybackLog.started_at).label("day"),
            func.count(PlaybackLog.id).label("sessions"),
            func.avg(
                func.julianday(PlaybackLog.completed_at) - func.julianday(PlaybackLog.started_at)
            ).label("avg_duration_days"),
        )
        .filter(PlaybackLog.started_at >= since)
        .group_by(func.date(PlaybackLog.started_at))
        .order_by(func.date(PlaybackLog.started_at))
        .all()
    )

    result = []
    for row in rows:
        avg_min = round(row.avg_duration_days * 24 * 60, 1) if row.avg_duration_days else None
        result.append(
            {
                "date": str(row.day),
                "sessions": row.sessions,
                "avg_duration_minutes": avg_min,
            }
        )

    return {"period": period, "days": days, "data": result}


# ─── 生成パフォーマンス ────────────────────────────────────────────────────


@router.get("/generation")
def get_generation_stats(
    days: int = Query(7),
    db: Session = Depends(get_db),
):
    """生成パフォーマンス分析（プロバイダー別）"""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            GenerationMetrics.provider,
            GenerationMetrics.generation_type,
            func.count(GenerationMetrics.id).label("total"),
            func.sum(case((GenerationMetrics.status == "success", 1), else_=0)).label("success"),
            func.avg(GenerationMetrics.api_duration_ms).label("avg_api_ms"),
            func.avg(GenerationMetrics.total_duration_ms).label("avg_total_ms"),
            func.sum(GenerationMetrics.cost_estimate).label("total_cost"),
        )
        .filter(GenerationMetrics.timestamp >= since)
        .group_by(GenerationMetrics.provider, GenerationMetrics.generation_type)
        .all()
    )

    result = []
    for row in rows:
        total = row.total or 0
        success = row.success or 0
        result.append(
            ProviderStats(
                provider=row.provider,
                generation_type=row.generation_type,
                total_count=total,
                success_count=success,
                success_rate=round(success / total * 100, 1) if total > 0 else 0.0,
                avg_api_duration_ms=round(row.avg_api_ms, 1) if row.avg_api_ms else None,
                avg_total_duration_ms=round(row.avg_total_ms, 1) if row.avg_total_ms else None,
                total_cost_estimate=round(row.total_cost or 0.0, 4),
            )
        )

    return {"days": days, "providers": result}


# ─── コスト分析 ────────────────────────────────────────────────────────────


@router.get("/generation/costs")
def get_generation_costs(
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """日別・プロバイダー別コスト分析"""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            func.date(GenerationMetrics.timestamp).label("day"),
            GenerationMetrics.provider,
            func.sum(GenerationMetrics.cost_estimate).label("cost"),
            func.count(GenerationMetrics.id).label("count"),
        )
        .filter(
            GenerationMetrics.timestamp >= since,
            GenerationMetrics.cost_estimate.isnot(None),
        )
        .group_by(func.date(GenerationMetrics.timestamp), GenerationMetrics.provider)
        .order_by(func.date(GenerationMetrics.timestamp))
        .all()
    )

    result = [
        {
            "date": str(row.day),
            "provider": row.provider,
            "cost_estimate": round(row.cost or 0.0, 4),
            "generation_count": row.count,
        }
        for row in rows
    ]

    return {"days": days, "data": result}


# ─── テーマ別利用統計 ─────────────────────────────────────────────────────


@router.get("/themes")
def get_theme_stats(db: Session = Depends(get_db)):
    """テーマ（曜日）別のストーリーボード利用統計

    Single aggregated query instead of N+1 per-theme queries.
    """
    # Single query: join Storyboard → StoryboardScene and aggregate all stats at once.
    scene_rows = (
        db.query(
            Storyboard.day_of_week,
            func.count(Storyboard.id.distinct()).label("storyboard_count"),
            func.count(StoryboardScene.id).label("scene_count"),
            func.sum(
                case((StoryboardScene.image_status == "complete", 1), else_=0)
            ).label("image_ready_count"),
            func.sum(
                case((StoryboardScene.video_status == "complete", 1), else_=0)
            ).label("video_ready_count"),
        )
        .outerjoin(StoryboardScene, StoryboardScene.storyboard_id == Storyboard.id)
        .group_by(Storyboard.day_of_week)
        .all()
    )

    result = [
        ThemeStats(
            day_of_week=row.day_of_week,
            storyboard_count=row.storyboard_count or 0,
            scene_count=row.scene_count or 0,
            image_ready_count=int(row.image_ready_count or 0),
            video_ready_count=int(row.video_ready_count or 0),
        )
        for row in scene_rows
    ]

    return {"themes": result}


# ─── イベントログ ─────────────────────────────────────────────────────────


@router.get("/events", response_model=List[EventLogResponse])
def get_events(
    event_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date string YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date string YYYY-MM-DD"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """イベントログ検索"""
    q = db.query(EventLog)
    if event_type:
        q = q.filter(EventLog.event_type == event_type)
    if category:
        q = q.filter(EventLog.event_category == category)
    if date_from:
        try:
            q = q.filter(EventLog.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_from format: '{date_from}'. Use YYYY-MM-DD.")
    if date_to:
        try:
            q = q.filter(EventLog.timestamp < datetime.fromisoformat(date_to) + timedelta(days=1))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_to format: '{date_to}'. Use YYYY-MM-DD.")
    events = q.order_by(EventLog.timestamp.desc()).limit(limit).all()
    return events


@router.post("/events", response_model=EventLogResponse, status_code=201)
def create_event(payload: EventLogCreate, db: Session = Depends(get_db)):
    """イベントを記録する"""
    entry = EventLog(
        event_type=payload.event_type,
        event_category=payload.event_category,
        session_id=payload.session_id,
        storyboard_id=payload.storyboard_id,
        data=json.dumps(payload.data, ensure_ascii=False) if payload.data else None,
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ─── システムヘルスチェック ────────────────────────────────────────────────


@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    """システムヘルスチェック"""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    recent_error = (
        db.query(GenerationMetrics)
        .filter(GenerationMetrics.status == "failed")
        .order_by(GenerationMetrics.timestamp.desc())
        .first()
    )

    last_5min = datetime.utcnow() - timedelta(minutes=5)
    recent_activity = db.query(func.count(EventLog.id)).filter(
        EventLog.timestamp >= last_5min
    ).scalar() or 0

    return {
        "status": "ok" if db_ok else "degraded",
        "db_connected": db_ok,
        "recent_events_5min": recent_activity,
        "last_generation_error": {
            "provider": recent_error.provider,
            "error": recent_error.error_message,
            "timestamp": recent_error.timestamp.isoformat(),
        }
        if recent_error
        else None,
        "checked_at": datetime.utcnow().isoformat(),
    }
