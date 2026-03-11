"""設定管理ルーター"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    AppSetting, AppSettingResponse, AppSettingUpdate,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Default settings to seed on first load
DEFAULT_SETTINGS = [
    {"key": "ANTHROPIC_API_KEY", "label": "Anthropic Claude API Key (台本AI生成)", "category": "api_keys", "is_secret": True},
    {"key": "GEMINI_API_KEY", "label": "Gemini API Key (Nano Banana)", "category": "api_keys", "is_secret": True},
    {"key": "FAL_API_KEY", "label": "fal.ai API Key (Flux Pro + Kling Video)", "category": "api_keys", "is_secret": True},
    {"key": "RUNWAY_API_KEY", "label": "Runway Gen-4.5 API Key", "category": "api_keys", "is_secret": True},
    {"key": "KLING_API_KEY", "label": "Kling 2.6 API Key", "category": "api_keys", "is_secret": True},
    {"key": "PIKA_API_KEY", "label": "Pika 2.5 API Key", "category": "api_keys", "is_secret": True},
    {"key": "OPENAI_API_KEY", "label": "OpenAI API Key", "category": "api_keys", "is_secret": True},
    {"key": "LIVEPORTRAIT_PATH", "label": "LivePortrait ローカルパス", "category": "paths", "is_secret": False},
]


def _seed_defaults(db: Session):
    """Seed default settings if they don't exist"""
    for item in DEFAULT_SETTINGS:
        existing = db.query(AppSetting).filter(AppSetting.key == item["key"]).first()
        if not existing:
            setting = AppSetting(
                key=item["key"],
                value="",
                label=item["label"],
                category=item["category"],
                is_secret=item["is_secret"],
            )
            db.add(setting)
    db.commit()


def _mask_value(value: str) -> str:
    """Mask secret values for display"""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("", response_model=list[AppSettingResponse])
def list_settings(db: Session = Depends(get_db)):
    _seed_defaults(db)
    settings = db.query(AppSetting).order_by(AppSetting.category, AppSetting.key).all()
    result = []
    for s in settings:
        resp = AppSettingResponse.model_validate(s)
        if s.is_secret and s.value:
            resp.value = _mask_value(s.value)
        result.append(resp)
    return result


@router.put("/{key}", response_model=AppSettingResponse)
def update_setting(key: str, data: AppSettingUpdate, db: Session = Depends(get_db)):
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not setting:
        # Auto-create the setting if it doesn't exist (upsert behaviour)
        default_meta = next((d for d in DEFAULT_SETTINGS if d["key"] == key), None)
        setting = AppSetting(
            key=key,
            value=data.value,
            label=default_meta["label"] if default_meta else key,
            category=default_meta["category"] if default_meta else "api_keys",
            is_secret=default_meta["is_secret"] if default_meta else True,
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    else:
        setting.value = data.value
        db.commit()
        db.refresh(setting)

    resp = AppSettingResponse.model_validate(setting)
    if setting.is_secret and setting.value:
        resp.value = _mask_value(setting.value)
    return resp


@router.get("/{key}/raw")
def get_raw_setting(key: str, db: Session = Depends(get_db)):
    """Get the raw (unmasked) value - for internal use by workers"""
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not setting:
        # Return empty value rather than 404, to match the worker fallback logic
        return {"key": key, "value": ""}
    return {"key": setting.key, "value": setting.value}
