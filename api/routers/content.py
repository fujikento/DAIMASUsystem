"""コンテンツ CRUD ルーター"""

import os
import uuid
from typing import Optional

try:
    import aiofiles
    _aiofiles_available = True
except ImportError:
    aiofiles = None  # type: ignore[assignment]
    _aiofiles_available = False

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    Content,
    ContentResponse,
)
from api.services.content_scheduler import get_theme_for_day

router = APIRouter(prefix="/api/contents", tags=["contents"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=list[ContentResponse])
def list_contents(
    theme: Optional[str] = None,
    content_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """コンテンツ一覧を取得"""
    q = db.query(Content)
    if theme:
        q = q.filter(Content.theme == theme)
    if content_type:
        q = q.filter(Content.type == content_type)
    return q.order_by(Content.created_at.desc()).all()


@router.post("", response_model=ContentResponse, status_code=201)
async def create_content(
    name: str = Form(...),
    type: str = Form(...),
    theme: str = Form(...),
    duration: Optional[float] = Form(None),
    resolution: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """コンテンツを作成 (ファイルアップロード付き)"""
    if not _aiofiles_available:
        raise HTTPException(
            status_code=503,
            detail="aiofiles package is not installed. Run: pip install aiofiles",
        )

    # ユニークなファイル名を生成
    ext = os.path.splitext(file.filename or "")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    async with aiofiles.open(file_path, "wb") as f:
        data = await file.read()
        await f.write(data)

    content = Content(
        name=name,
        type=type,
        theme=theme,
        file_path=file_path,
        duration=duration,
        resolution=resolution,
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


@router.get("/themes/{day_of_week}", response_model=list[ContentResponse])
def get_contents_by_day_theme(day_of_week: str, db: Session = Depends(get_db)):
    """曜日テーマに対応するコンテンツを取得"""
    theme = get_theme_for_day(day_of_week)
    return (
        db.query(Content)
        .filter(Content.theme == theme)
        .order_by(Content.created_at.desc())
        .all()
    )


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: int, db: Session = Depends(get_db)):
    """コンテンツ詳細を取得"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


@router.delete("/{content_id}", status_code=204)
def delete_content(content_id: int, db: Session = Depends(get_db)):
    """コンテンツを削除 (ファイルも削除)"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # ファイルを削除
    if content.file_path and os.path.exists(content.file_path):
        os.remove(content.file_path)

    db.delete(content)
    db.commit()
