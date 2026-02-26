"""タイムライン管理ルーター"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from api.models.database import get_db
from api.models.schemas import (
    Timeline,
    TimelineItem,
    TimelineCreate,
    TimelineResponse,
    TimelineListResponse,
    TimelineItemCreate,
    TimelineItemResponse,
)

router = APIRouter(prefix="/api/timelines", tags=["timelines"])


@router.get("", response_model=list[TimelineListResponse])
def list_timelines(db: Session = Depends(get_db)):
    """タイムライン一覧"""
    return db.query(Timeline).order_by(Timeline.created_at.desc()).all()


@router.post("", response_model=TimelineResponse, status_code=201)
def create_timeline(body: TimelineCreate, db: Session = Depends(get_db)):
    """タイムラインを新規作成"""
    timeline = Timeline(**body.model_dump())
    db.add(timeline)
    db.commit()
    db.refresh(timeline)
    return timeline


@router.get("/{timeline_id}", response_model=TimelineResponse)
def get_timeline(timeline_id: int, db: Session = Depends(get_db)):
    """タイムライン詳細 (アイテム含む)"""
    timeline = (
        db.query(Timeline)
        .options(joinedload(Timeline.items).joinedload(TimelineItem.content))
        .filter(Timeline.id == timeline_id)
        .first()
    )
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return timeline


@router.put("/{timeline_id}/items", response_model=list[TimelineItemResponse])
def update_timeline_items(
    timeline_id: int,
    items: list[TimelineItemCreate],
    db: Session = Depends(get_db),
):
    """タイムラインアイテムを一括更新 (既存を全置換)"""
    timeline = db.query(Timeline).filter(Timeline.id == timeline_id).first()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # 既存アイテムを削除
    db.query(TimelineItem).filter(TimelineItem.timeline_id == timeline_id).delete()

    # 新しいアイテムを追加
    new_items = []
    for item_data in items:
        item = TimelineItem(timeline_id=timeline_id, **item_data.model_dump())
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)

    return new_items


@router.delete("/{timeline_id}", status_code=204)
def delete_timeline(timeline_id: int, db: Session = Depends(get_db)):
    """タイムラインを削除 (cascade でアイテムも削除)"""
    timeline = db.query(Timeline).filter(Timeline.id == timeline_id).first()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    db.delete(timeline)
    db.commit()
