"""AI映像生成パイプライン (スタブ)

Runway API / LivePortrait を使った映像生成のスタブ実装。
実際のAPI連携は後日実装予定。
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationJob(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


# インメモリのジョブトラッカー
_jobs: dict[str, GenerationJob] = {}


async def generate_runway_video(
    prompt: str,
    reference_image_path: Optional[str] = None,
    duration: float = 5.0,
) -> GenerationJob:
    """Runway API を使った映像生成 (スタブ)

    将来的に Runway Gen-3 API を呼び出す。
    現段階ではジョブを作成して queued 状態で返す。
    """
    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        status=JobStatus.QUEUED,
        created_at=datetime.now(),
    )
    _jobs[job.job_id] = job
    logger.info("Runway job created (stub): %s – prompt=%s", job.job_id, prompt)
    return job


async def generate_live_portrait(
    photo_path: str,
    driving_video_path: Optional[str] = None,
) -> GenerationJob:
    """LivePortrait で写真からキャラクター動画を生成 (スタブ)

    バースデー演出用: ゲストの写真をアニメーション化する。
    """
    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        status=JobStatus.QUEUED,
        created_at=datetime.now(),
    )
    _jobs[job.job_id] = job
    logger.info("LivePortrait job created (stub): %s – photo=%s", job.job_id, photo_path)
    return job


def get_job_status(job_id: str) -> Optional[GenerationJob]:
    """ジョブのステータスを取得"""
    return _jobs.get(job_id)


def list_jobs() -> list[GenerationJob]:
    """全ジョブ一覧"""
    return list(_jobs.values())
