"""イベントログヘルパー

他のルーターやワーカーから簡単にイベントを記録するユーティリティ。
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.database import SessionLocal
from api.models.schemas import EventLog, GenerationMetrics

logger = logging.getLogger(__name__)


class EventLogger:
    """イベントをDBに記録するヘルパークラス"""

    @staticmethod
    def log(
        event_type: str,
        category: str,
        data: Optional[dict] = None,
        session_id: Optional[int] = None,
        storyboard_id: Optional[int] = None,
    ) -> None:
        """イベントをDBに記録する。失敗しても例外を投げない。"""
        try:
            db: Session = SessionLocal()
            try:
                entry = EventLog(
                    event_type=event_type,
                    event_category=category,
                    session_id=session_id,
                    storyboard_id=storyboard_id,
                    data=json.dumps(data, ensure_ascii=False) if data else None,
                    timestamp=datetime.utcnow(),
                )
                db.add(entry)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("EventLogger.log failed: %s", exc)

    @staticmethod
    def log_generation(
        provider: str,
        model: str,
        gen_type: str,
        duration_ms: int,
        status: str,
        size_bytes: int = 0,
        scene_id: Optional[int] = None,
        prompt_length: Optional[int] = None,
        api_duration_ms: Optional[int] = None,
        cost_estimate: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """生成メトリクスをDBに記録する。失敗しても例外を投げない。"""
        try:
            db: Session = SessionLocal()
            try:
                entry = GenerationMetrics(
                    provider=provider,
                    model=model,
                    generation_type=gen_type,
                    scene_id=scene_id,
                    prompt_length=prompt_length,
                    api_duration_ms=api_duration_ms,
                    total_duration_ms=duration_ms,
                    output_size_bytes=size_bytes if size_bytes else None,
                    status=status,
                    error_message=error,
                    cost_estimate=cost_estimate,
                    timestamp=datetime.utcnow(),
                )
                db.add(entry)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("EventLogger.log_generation failed: %s", exc)
