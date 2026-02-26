"""バースデー予約ルーター"""

import os
import sys
import uuid
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    BirthdayReservation,
    BirthdayResponse,
    BirthdayStatusUpdate,
)

# ワーカー読み込み
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from workers.photo_animator import (
    PhotoAnimatorService,
    AnimationProvider,
    AnimationStatus,
    BIRTHDAY_TEMPLATES,
)

router = APIRouter(prefix="/api/birthdays", tags=["birthdays"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

VALID_STATUSES = ("pending", "processing", "ready", "played")

_photo_service = PhotoAnimatorService()


class AnimateReservationRequest(BaseModel):
    template_id: str = "birthday_cake"
    zone_id: int = 1
    provider: str = "liveportrait"


@router.get("/templates")
def list_birthday_templates():
    """利用可能な誕生日アニメーションテンプレート"""
    return {
        k: {"name": v["name"], "description": v["description"], "duration": v["duration"]}
        for k, v in BIRTHDAY_TEMPLATES.items()
    }


@router.get("", response_model=list[BirthdayResponse])
def list_birthdays(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """バースデー予約一覧"""
    q = db.query(BirthdayReservation)
    if status:
        q = q.filter(BirthdayReservation.status == status)
    return q.order_by(BirthdayReservation.reservation_date.desc()).all()


@router.post("", response_model=BirthdayResponse, status_code=201)
async def create_birthday(
    guest_name: str = Form(...),
    reservation_date: str = Form(...),  # ISO形式: 2025-03-15
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """バースデー予約を作成 (写真アップロード可)"""
    photo_path = None
    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1]
        filename = f"birthday_{uuid.uuid4().hex}{ext}"
        photo_path = os.path.join(UPLOAD_DIR, filename)
        async with aiofiles.open(photo_path, "wb") as f:
            data = await photo.read()
            await f.write(data)

    reservation = BirthdayReservation(
        guest_name=guest_name,
        reservation_date=reservation_date,
        photo_path=photo_path,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@router.get("/{reservation_id}", response_model=BirthdayResponse)
def get_birthday(reservation_id: int, db: Session = Depends(get_db)):
    """予約ステータス確認"""
    reservation = (
        db.query(BirthdayReservation)
        .filter(BirthdayReservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.put("/{reservation_id}/status", response_model=BirthdayResponse)
def update_birthday_status(
    reservation_id: int,
    body: BirthdayStatusUpdate,
    db: Session = Depends(get_db),
):
    """予約ステータスを更新 (pending → processing → ready → played)"""
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        )

    reservation = (
        db.query(BirthdayReservation)
        .filter(BirthdayReservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation.status = body.status
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/{reservation_id}/animate", response_model=BirthdayResponse)
async def animate_birthday(
    reservation_id: int,
    body: AnimateReservationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """予約の写真からキャラクターアニメーション生成"""
    reservation = (
        db.query(BirthdayReservation)
        .filter(BirthdayReservation.id == reservation_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if not reservation.photo_path:
        raise HTTPException(status_code=400, detail="写真がアップロードされていません")

    if body.template_id not in BIRTHDAY_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {body.template_id}. Available: {list(BIRTHDAY_TEMPLATES.keys())}",
        )

    # ステータスを processing に
    reservation.status = "processing"
    db.commit()
    db.refresh(reservation)

    # バックグラウンドでアニメーション生成
    res_id = reservation.id
    photo_path = reservation.photo_path
    guest_name = reservation.guest_name

    async def _run_animation():
        from api.models.database import SessionLocal
        final_status = "pending"
        video_path = None
        try:
            job = _photo_service.create_job(
                photo_path=photo_path,
                template_id=body.template_id,
                guest_name=guest_name,
                zone_id=body.zone_id,
                provider=AnimationProvider(body.provider),
            )
            result = await _photo_service.process(job)
            if result.status == AnimationStatus.COMPLETE:
                final_status = "ready"
                video_path = result.final_output_path
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).exception(
                "Animation failed for reservation %s: %s", res_id, exc
            )
            final_status = "pending"

        session = SessionLocal()
        try:
            res = session.query(BirthdayReservation).filter(BirthdayReservation.id == res_id).first()
            if res:
                res.status = final_status
                if video_path:
                    res.character_video_path = video_path
                session.commit()
        finally:
            session.close()

    background_tasks.add_task(_run_animation)

    return reservation
