"""予約管理ルーター"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    CalendarDaySummary,
    Reservation,
    ReservationCreate,
    ReservationResponse,
    ReservationUpdate,
)

router = APIRouter(prefix="/api/reservations", tags=["reservations"])

VALID_STATUSES = ("confirmed", "checked_in", "seated", "completed", "cancelled")
VALID_TIME_SLOTS = ("18:00", "19:30", "21:00")


# ─── 本日の予約一覧 (固定パスを先に定義) ────────────────────────────────────────


@router.get("/today", response_model=list[ReservationResponse])
def list_today_reservations(db: Session = Depends(get_db)):
    """本日の予約一覧を返す"""
    today = date.today()
    return (
        db.query(Reservation)
        .filter(
            Reservation.reservation_date == today,
            Reservation.status != "cancelled",
        )
        .order_by(Reservation.time_slot, Reservation.id)
        .all()
    )


@router.get("/calendar", response_model=list[CalendarDaySummary])
def get_calendar(
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    """月間カレンダー用サマリーを返す（各日の予約数を集計）"""
    rows = (
        db.query(
            Reservation.reservation_date,
            Reservation.status,
            func.count(Reservation.id).label("count"),
        )
        .filter(
            extract("year", Reservation.reservation_date) == year,
            extract("month", Reservation.reservation_date) == month,
        )
        .group_by(Reservation.reservation_date, Reservation.status)
        .all()
    )

    # date → {status: count} に集約
    by_date: dict[date, dict[str, int]] = {}
    for row in rows:
        d = row.reservation_date
        if d not in by_date:
            by_date[d] = {}
        by_date[d][row.status] = row.count

    result = []
    for d, counts in sorted(by_date.items()):
        total = sum(counts.values())
        result.append(
            CalendarDaySummary(
                date=d,
                total=total,
                confirmed=counts.get("confirmed", 0),
                checked_in=counts.get("checked_in", 0),
                seated=counts.get("seated", 0),
                completed=counts.get("completed", 0),
                cancelled=counts.get("cancelled", 0),
            )
        )
    return result


# ─── CRUD ────────────────────────────────────────────────────────────────────


@router.post("", response_model=ReservationResponse, status_code=201)
def create_reservation(body: ReservationCreate, db: Session = Depends(get_db)):
    """予約を作成する"""
    if body.time_slot not in VALID_TIME_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time_slot. Must be one of: {', '.join(VALID_TIME_SLOTS)}",
        )

    reservation = Reservation(**body.model_dump())
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@router.get("", response_model=list[ReservationResponse])
def list_reservations(
    reservation_date: Optional[date] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """予約一覧を返す（date / status でフィルタ可）"""
    q = db.query(Reservation)
    if reservation_date:
        q = q.filter(Reservation.reservation_date == reservation_date)
    if status:
        q = q.filter(Reservation.status == status)
    return q.order_by(Reservation.reservation_date, Reservation.time_slot, Reservation.id).all()


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """予約詳細を返す"""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.put("/{reservation_id}", response_model=ReservationResponse)
def update_reservation(
    reservation_id: int,
    body: ReservationUpdate,
    db: Session = Depends(get_db),
):
    """予約情報を変更する"""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    update_data = body.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        )
    if "time_slot" in update_data and update_data["time_slot"] not in VALID_TIME_SLOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time_slot. Must be one of: {', '.join(VALID_TIME_SLOTS)}",
        )

    for field, value in update_data.items():
        setattr(reservation, field, value)

    db.commit()
    db.refresh(reservation)
    return reservation


@router.delete("/{reservation_id}", response_model=ReservationResponse)
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """予約をキャンセルする（ソフトデリート: status → cancelled）"""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status == "cancelled":
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")

    reservation.status = "cancelled"
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/{reservation_id}/check-in", response_model=ReservationResponse)
def check_in_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """ゲストのチェックイン処理（confirmed → checked_in）"""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot check-in: current status is '{reservation.status}'",
        )

    reservation.status = "checked_in"
    db.commit()
    db.refresh(reservation)
    return reservation
