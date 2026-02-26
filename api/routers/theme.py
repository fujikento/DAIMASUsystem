"""曜日テーマ管理ルーター"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    DayThemeModel,
    DayThemeBase,
    DayThemeUpdate,
    DayThemeResponse,
)

router = APIRouter(prefix="/api/themes", tags=["themes"])

# デフォルトテーマ定義
DEFAULT_THEMES: list[dict] = [
    {
        "day_of_week": "monday",
        "name_ja": "和 〜 Japanese Zen",
        "name_en": "Japanese Zen",
        "color": "#8B7355",
        "icon": "\U0001f38d",
        "bg_gradient": "from-amber-950 to-stone-900",
    },
    {
        "day_of_week": "tuesday",
        "name_ja": "火 〜 Fire & Passion",
        "name_en": "Fire & Passion",
        "color": "#FF4500",
        "icon": "\U0001f525",
        "bg_gradient": "from-red-950 to-orange-950",
    },
    {
        "day_of_week": "wednesday",
        "name_ja": "海 〜 Ocean Deep",
        "name_en": "Ocean Deep",
        "color": "#006994",
        "icon": "\U0001f30a",
        "bg_gradient": "from-cyan-950 to-blue-950",
    },
    {
        "day_of_week": "thursday",
        "name_ja": "森 〜 Forest Spirit",
        "name_en": "Forest Spirit",
        "color": "#228B22",
        "icon": "\U0001f332",
        "bg_gradient": "from-green-950 to-emerald-950",
    },
    {
        "day_of_week": "friday",
        "name_ja": "宝 〜 Golden Luxury",
        "name_en": "Golden Luxury",
        "color": "#FFD700",
        "icon": "\u2728",
        "bg_gradient": "from-yellow-950 to-amber-950",
    },
    {
        "day_of_week": "saturday",
        "name_ja": "宇宙 〜 Space Odyssey",
        "name_en": "Space Odyssey",
        "color": "#4B0082",
        "icon": "\U0001f680",
        "bg_gradient": "from-indigo-950 to-purple-950",
    },
    {
        "day_of_week": "sunday",
        "name_ja": "物語 〜 Fairy Tale",
        "name_en": "Fairy Tale",
        "color": "#FF69B4",
        "icon": "\U0001f4d6",
        "bg_gradient": "from-pink-950 to-rose-950",
    },
]

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def seed_defaults(db: Session) -> list[DayThemeModel]:
    """デフォルトテーマが無ければシード"""
    existing = db.query(DayThemeModel).count()
    if existing >= 7:
        return []
    created = []
    for t in DEFAULT_THEMES:
        exists = db.query(DayThemeModel).filter(DayThemeModel.day_of_week == t["day_of_week"]).first()
        if not exists:
            row = DayThemeModel(**t)
            db.add(row)
            created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


@router.get("", response_model=list[DayThemeResponse])
def list_themes(db: Session = Depends(get_db)):
    """全曜日テーマ一覧"""
    seed_defaults(db)
    themes = db.query(DayThemeModel).all()
    # 曜日順にソート
    order_map = {d: i for i, d in enumerate(DAY_ORDER)}
    themes.sort(key=lambda t: order_map.get(t.day_of_week, 99))
    return themes


@router.get("/{day_of_week}", response_model=DayThemeResponse)
def get_theme(day_of_week: str, db: Session = Depends(get_db)):
    """指定曜日のテーマ取得"""
    seed_defaults(db)
    theme = db.query(DayThemeModel).filter(DayThemeModel.day_of_week == day_of_week).first()
    if not theme:
        raise HTTPException(404, f"Theme not found for {day_of_week}")
    return theme


@router.put("/{day_of_week}", response_model=DayThemeResponse)
def update_theme(day_of_week: str, data: DayThemeUpdate, db: Session = Depends(get_db)):
    """テーマを更新"""
    seed_defaults(db)
    theme = db.query(DayThemeModel).filter(DayThemeModel.day_of_week == day_of_week).first()
    if not theme:
        raise HTTPException(404, f"Theme not found for {day_of_week}")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(theme, key, value)
    db.commit()
    db.refresh(theme)
    return theme


@router.post("/reset", response_model=list[DayThemeResponse])
def reset_themes(db: Session = Depends(get_db)):
    """全テーマをデフォルトにリセット"""
    db.query(DayThemeModel).delete()
    db.commit()
    created = []
    for t in DEFAULT_THEMES:
        row = DayThemeModel(**t)
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created
