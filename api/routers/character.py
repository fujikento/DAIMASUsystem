"""キャラクター生成管理ルーター"""

import os
import sys
import uuid
from pathlib import Path
from typing import Optional

try:
    import aiofiles
    _aiofiles_available = True
except ImportError:
    aiofiles = None  # type: ignore[assignment]
    _aiofiles_available = False

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ワーカー読み込み
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from workers.character_generator import (
        CharacterGeneratorService,
        CharacterJobStatus,
        AnimationProvider,
        ALL_TEMPLATES,
        CATEGORY_TEMPLATES,
    )
    _worker_available = True
except ImportError:
    CharacterGeneratorService = None  # type: ignore[assignment,misc]
    CharacterJobStatus = None  # type: ignore[assignment]
    AnimationProvider = None  # type: ignore[assignment]
    ALL_TEMPLATES: dict = {}
    CATEGORY_TEMPLATES: dict = {}
    _worker_available = False

router = APIRouter(prefix="/api/characters", tags=["characters"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "character_photos")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "character_outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

_character_service = CharacterGeneratorService() if _worker_available else None


def _require_worker():
    if not _worker_available or _character_service is None:
        raise HTTPException(
            status_code=503,
            detail="character_generator worker is not available. Check that the workers package is installed.",
        )


def _require_aiofiles():
    if not _aiofiles_available:
        raise HTTPException(
            status_code=503,
            detail="aiofiles package is not installed. Run: pip install aiofiles",
        )


# ── リクエスト/レスポンススキーマ ─────────────────────────────────


class AvatarRequest(BaseModel):
    theme: str = "ocean"
    template_id: str = "welcome_elegant"
    zone_id: int = 1


class AnimationRequest(BaseModel):
    template_id: str = "birthday_cake"
    zone_id: int = 1
    provider: str = "liveportrait"


class MemorialRequest(BaseModel):
    theme: str = "ocean"
    scenes: Optional[list[str]] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    guest_name: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    message: str = ""


class TemplateInfo(BaseModel):
    name: str
    category: str
    description: str
    duration: int


# ── ファイルアップロードヘルパー ──────────────────────────────────


_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


async def _save_upload(photo: UploadFile) -> str:
    """アップロードされた写真を保存してパスを返す"""
    _require_aiofiles()

    # Validate extension to prevent arbitrary file uploads.
    raw_ext = os.path.splitext(photo.filename or "photo.jpg")[1].lower()
    if raw_ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{raw_ext}'. Allowed: {sorted(_ALLOWED_IMAGE_EXTENSIONS)}",
        )

    data = await photo.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data) // 1024} KB). Maximum allowed: {_MAX_UPLOAD_BYTES // 1024} KB",
        )
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Use only the sanitised extension — never trust the full filename.
    filename = f"char_{uuid.uuid4().hex}{raw_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(data)
    return filepath


# ── アバター生成 ─────────────────────────────────────────────────


@router.post("/avatar", response_model=JobStatusResponse, status_code=202)
async def create_avatar(
    background_tasks: BackgroundTasks,
    photo: UploadFile = File(...),
    guest_name: str = Form(""),
    theme: str = Form("ocean"),
    template_id: str = Form("welcome_elegant"),
    zone_id: int = Form(1),
):
    """写真からウェルカムアバターを生成

    写真をアップロードし、テーマに合わせたスタイル変換 + アニメーションを適用。
    ジョブはバックグラウンドで実行され、job_idで進捗を確認可能。
    """
    _require_worker()
    if template_id not in ALL_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {template_id}. Available: {list(ALL_TEMPLATES.keys())}",
        )

    photo_path = await _save_upload(photo)

    job = _character_service.generate_welcome_avatar(
        photo_path=photo_path,
        guest_name=guest_name,
        theme=theme,
        template_id=template_id,
        zone_id=zone_id,
    )

    async def _run():
        await _character_service.process(job)

    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        job_type=job.job_type.value,
        guest_name=guest_name,
        message=f"アバター生成を開始しました (template={template_id})",
    )


# ── アニメーション生成 ───────────────────────────────────────────


@router.post("/animation", response_model=JobStatusResponse, status_code=202)
async def create_animation(
    background_tasks: BackgroundTasks,
    photo: UploadFile = File(...),
    guest_name: str = Form(""),
    template_id: str = Form("birthday_cake"),
    zone_id: int = Form(1),
    provider: str = Form("liveportrait"),
):
    """写真からキャラクターアニメーションを生成

    バースデーやサプライズ用のフルアニメーション。
    LivePortrait (ローカル) または Hedra (API) を選択可能。
    """
    _require_worker()
    if template_id not in ALL_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template: {template_id}. Available: {list(ALL_TEMPLATES.keys())}",
        )

    if provider not in ("liveportrait", "hedra"):
        raise HTTPException(status_code=400, detail="provider must be 'liveportrait' or 'hedra'")

    photo_path = await _save_upload(photo)

    job = _character_service.generate_birthday_animation(
        photo_path=photo_path,
        guest_name=guest_name,
        template_id=template_id,
        zone_id=zone_id,
        provider=AnimationProvider(provider),
    )

    async def _run():
        await _character_service.process(job)

    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        job_type=job.job_type.value,
        guest_name=guest_name,
        message=f"アニメーション生成を開始しました (template={template_id}, provider={provider})",
    )


# ── メモリアルフォト生成 ─────────────────────────────────────────


@router.post("/memorial", response_model=JobStatusResponse, status_code=202)
async def create_memorial(
    background_tasks: BackgroundTasks,
    photo: UploadFile = File(...),
    guest_name: str = Form(""),
    theme: str = Form("ocean"),
    scenes: str = Form(""),
):
    """退店時のお土産メモリアルフォトを生成

    写真にスタイル変換を適用し、テーマに合わせたフレームと
    ゲスト名・日付を入れた合成画像を生成。
    """
    _require_worker()
    photo_path = await _save_upload(photo)

    scene_list = [s.strip() for s in scenes.split(",") if s.strip()] if scenes else None

    job = _character_service.generate_memorial_photo(
        photo_path=photo_path,
        guest_name=guest_name,
        theme=theme,
        scenes=scene_list,
    )

    async def _run():
        await _character_service.process(job)

    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        job_type=job.job_type.value,
        guest_name=guest_name,
        message=f"メモリアルフォト生成を開始しました (theme={theme})",
    )


# ── テンプレート一覧 ─────────────────────────────────────────────


@router.get("/templates")
def list_templates(category: Optional[str] = None):
    """テンプレート一覧を取得

    category パラメータで絞り込み可能:
    - birthday: バースデー系
    - welcome: ウェルカム系
    - surprise: サプライズ系
    - season: 季節イベント系
    """
    _require_worker()
    if category and category not in CATEGORY_TEMPLATES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category: {category}. Available: {list(CATEGORY_TEMPLATES.keys())}",
        )
    return CharacterGeneratorService.list_templates(category)


@router.get("/templates/{template_id}/preview")
def get_template_preview(template_id: str):
    """テンプレートのプレビュー情報を取得"""
    _require_worker()
    if template_id not in ALL_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}",
        )
    tmpl = ALL_TEMPLATES[template_id]
    return {
        "id": template_id,
        "name": tmpl["name"],
        "category": tmpl["category"],
        "description": tmpl["description"],
        "duration": tmpl["duration"],
        "composite_position": tmpl["composite_position"],
        "text_position": tmpl.get("text_position"),
        "preview_url": f"/static/previews/templates/{template_id}_preview.mp4",
        "thumbnail_url": f"/static/previews/templates/{template_id}_thumb.jpg",
    }


# ── ジョブステータス ─────────────────────────────────────────────


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """キャラクター生成ジョブのステータスを取得"""
    _require_worker()
    job_data = _character_service.get_job_status(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        job_type=job_data["job_type"],
        guest_name=job_data["guest_name"],
        output_path=job_data.get("output_path"),
        error=job_data.get("error"),
        message="",
    )


# ── スタイル変換済みキャラクター画像プレビュー ─────────────────────


@router.get("/preview/styled/{filename}")
def preview_styled_character(filename: str):
    """スタイル変換済みキャラクター画像をブラウザで表示する。

    character_outputs ディレクトリ内の *_styled.jpg ファイルを提供する。
    ジョブ完了後にフロントエンドがプレビュー表示するためのエンドポイント。

    Args:
        filename: ファイル名 (例: avatar_1_1234567890_styled.jpg)

    Returns:
        FileResponse: JPEG 画像ファイル

    Raises:
        400: ファイル名にパストラバーサルの試みが含まれる場合
        404: ファイルが存在しない、またはサイズが 0 バイトの場合
    """
    # パストラバーサル対策: ファイル名のみ許可 (ディレクトリ区切り文字を拒否)
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = Path(OUTPUT_DIR) / safe_name

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Styled image not found: {filename}. "
                   "Generate a character with a theme first.",
        )

    if file_path.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Styled image is empty (generation may still be in progress): {filename}",
        )

    # メディアタイプをファイル拡張子から決定
    ext = file_path.suffix.lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media_type = media_types.get(ext, "image/jpeg")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/preview/styled/{job_id}/by-job")
def preview_styled_by_job(job_id: str):
    """ジョブIDからスタイル変換済み画像のURLを返す。

    フロントエンドがジョブIDしか知らない場合に使う。
    実際の画像バイナリは /preview/styled/{filename} エンドポイントで取得すること。

    Args:
        job_id: generate_welcome_avatar 等が返したジョブID

    Returns:
        dict: styled_url フィールドに画像取得用 URL を含む JSON
    """
    _require_worker()
    job_data = _character_service.get_job_status(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    styled_path = job_data.get("styled_photo_path")
    if not styled_path:
        raise HTTPException(
            status_code=404,
            detail="Styled image not yet generated for this job. "
                   "Check job status first.",
        )

    filename = Path(styled_path).name
    file_path = Path(OUTPUT_DIR) / filename

    return {
        "job_id": job_id,
        "status": job_data["status"],
        "styled_url": f"/api/characters/preview/styled/{filename}",
        "styled_path": styled_path,
        "ready": file_path.exists() and file_path.stat().st_size > 0,
    }
