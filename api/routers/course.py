"""コース料理管理ルーター"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    CourseDish,
    CourseDishCreate,
    CourseDishResponse,
)

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[CourseDishResponse])
def list_courses(day_of_week: str | None = None, db: Session = Depends(get_db)):
    """コース料理一覧（曜日フィルタ可能）"""
    q = db.query(CourseDish)
    if day_of_week:
        q = q.filter(CourseDish.day_of_week == day_of_week)
    return q.order_by(CourseDish.day_of_week, CourseDish.sort_order).all()


@router.post("", response_model=CourseDishResponse)
def create_course(data: CourseDishCreate, db: Session = Depends(get_db)):
    """コース料理を登録"""
    dish = CourseDish(**data.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


@router.get("/{course_id}", response_model=CourseDishResponse)
def get_course(course_id: int, db: Session = Depends(get_db)):
    """コース料理詳細"""
    dish = db.query(CourseDish).filter(CourseDish.id == course_id).first()
    if not dish:
        raise HTTPException(404, "コースが見つかりません")
    return dish


@router.put("/{course_id}", response_model=CourseDishResponse)
def update_course(course_id: int, data: CourseDishCreate, db: Session = Depends(get_db)):
    """コース料理を更新"""
    dish = db.query(CourseDish).filter(CourseDish.id == course_id).first()
    if not dish:
        raise HTTPException(404, "コースが見つかりません")
    for key, value in data.model_dump().items():
        setattr(dish, key, value)
    db.commit()
    db.refresh(dish)
    return dish


@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """コース料理を削除"""
    dish = db.query(CourseDish).filter(CourseDish.id == course_id).first()
    if not dish:
        raise HTTPException(404, "コースが見つかりません")
    db.delete(dish)
    db.commit()
    return {"ok": True}


@router.post("/batch", response_model=list[CourseDishResponse])
def create_courses_batch(dishes: list[CourseDishCreate], db: Session = Depends(get_db)):
    """複数コース料理を一括登録"""
    created = []
    for data in dishes:
        dish = CourseDish(**data.model_dump())
        db.add(dish)
        created.append(dish)
    db.commit()
    for dish in created:
        db.refresh(dish)
    return created
