"""曜日テーマに基づくコンテンツスケジューラー"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.schemas import Timeline

# 曜日 → テーマ マッピング
DAY_THEME_MAP: dict[str, str] = {
    "monday":    "ocean",       # 月曜: 海
    "tuesday":   "forest",      # 火曜: 森
    "wednesday": "cosmos",      # 水曜: 宇宙
    "thursday":  "sakura",      # 木曜: 桜
    "friday":    "matsuri",     # 金曜: 祭
    "saturday":  "fantasy",     # 土曜: ファンタジー
    "sunday":    "zen",         # 日曜: 禅
}


def get_today_theme() -> str:
    """今日の曜日テーマを取得"""
    day_name = datetime.now().strftime("%A").lower()
    return DAY_THEME_MAP.get(day_name, "ocean")


def get_today_day_of_week() -> str:
    """今日の曜日名 (小文字) を返す"""
    return datetime.now().strftime("%A").lower()


def get_timeline_for_today(
    db: Session,
    course_type: str = "dinner",
) -> Optional[Timeline]:
    """今日の曜日に対応するタイムラインを自動選択"""
    day = get_today_day_of_week()
    return (
        db.query(Timeline)
        .filter(Timeline.day_of_week == day, Timeline.course_type == course_type)
        .first()
    )


def get_theme_for_day(day_of_week: str) -> str:
    """指定曜日のテーマを返す"""
    return DAY_THEME_MAP.get(day_of_week.lower(), "ocean")
