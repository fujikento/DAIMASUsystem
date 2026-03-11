"""映像生成 & 合成パイプライン ルーター"""

import sys
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import CourseDish, ProjectionConfig, ProjectionConfigUpdate

# ワーカーモジュールをimportできるようにパス追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workers.video_generator import (
    VideoGeneratorService,
    GenerationMode,
    VideoProvider,
    THEME_PROMPTS,
    DAY_TO_THEME,
    COURSE_ORDER,
    _build_prompt,
)
from workers.content_compositor import (
    stitch_unified,
    fit_zone,
    split_for_projectors,
    TABLE_WIDTH,
    TABLE_HEIGHT,
    ZONE_WIDTH,
    ZONE_HEIGHT,
    ZONE_COUNT,
    PJ_REGIONS,
    ZONES,
    PJ_WIDTH,
    PJ_HEIGHT,
    PJ_COUNT,
    BLEND_OVERLAP,
)
from workers.photo_animator import (
    PhotoAnimatorService,
    AnimationProvider,
    BIRTHDAY_TEMPLATES,
)

router = APIRouter(prefix="/api/generation", tags=["generation"])

# サービスインスタンス（シングルトン）
_video_service = VideoGeneratorService()
_photo_service = PhotoAnimatorService()


# ─── Request / Response スキーマ ──────────────────────────────

class VideoGenerateRequest(BaseModel):
    theme: str
    course: str
    mode: str = "unified"          # unified / zone
    provider: str = "runway"       # runway / fal / kling / pika
    zone_id: Optional[int] = None  # zone modeの場合 1-4


class BatchGenerateRequest(BaseModel):
    day: str                       # monday, tuesday, ...
    mode: str = "unified"
    provider: str = "runway"


class StitchRequest(BaseModel):
    left_path: str
    right_path: str
    output_path: Optional[str] = None


class ZoneFitRequest(BaseModel):
    input_path: str
    output_path: Optional[str] = None


class SplitRequest(BaseModel):
    input_path: str
    output_dir: Optional[str] = None


class AnimateRequest(BaseModel):
    reservation_id: Optional[int] = None
    photo_path: Optional[str] = None
    guest_name: str = ""
    template_id: str = "birthday_cake"
    zone_id: int = 1
    provider: str = "liveportrait"   # liveportrait / hedra


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    message: str
    output_path: Optional[str] = None


# ─── ジョブ追跡用（インメモリ） ───────────────────────────────
# Limit dict size to prevent unbounded memory growth.
_MAX_ACTIVE_JOBS = 500
_active_jobs: dict[str, dict] = {}


def _register_job(job_id: str, job_data: dict) -> None:
    """Register a job and evict the oldest entries if the dict exceeds the cap."""
    _active_jobs[job_id] = job_data
    if len(_active_jobs) > _MAX_ACTIVE_JOBS:
        terminal = [k for k, v in _active_jobs.items() if v.get("status") in ("complete", "failed")]
        to_remove = terminal or list(_active_jobs.keys())
        for k in to_remove[: len(_active_jobs) - _MAX_ACTIVE_JOBS]:
            _active_jobs.pop(k, None)


# ─── 映像生成エンドポイント ──────────────────────────────────

@router.get("/themes")
def list_themes(db: Session = Depends(get_db)):
    """利用可能なテーマ・コース・モード一覧"""
    config = db.query(ProjectionConfig).first()
    if config:
        full_width = (config.pj_width * config.pj_count) - (config.blend_overlap * (config.pj_count - 1))
        full_height = config.pj_height
        zone_width = full_width // config.zone_count
        zone_height = full_height
        zone_count = config.zone_count
        table_width_mm = config.table_width_mm if config.table_width_mm is not None else 8120
        table_height_mm = config.table_height_mm if config.table_height_mm is not None else 600
    else:
        full_width = TABLE_WIDTH
        full_height = TABLE_HEIGHT
        zone_width = ZONE_WIDTH
        zone_height = ZONE_HEIGHT
        zone_count = ZONE_COUNT
        table_width_mm = 8120
        table_height_mm = 600

    return {
        "themes": list(THEME_PROMPTS.keys()),
        "courses": COURSE_ORDER,
        "modes": ["unified", "zone"],
        "providers": ["runway", "fal", "kling", "pika"],
        "day_to_theme": DAY_TO_THEME,
        "table_spec": {
            "full_width": full_width,
            "full_height": full_height,
            "zone_width": zone_width,
            "zone_height": zone_height,
            "zone_count": zone_count,
            "table_width_mm": table_width_mm,
            "table_height_mm": table_height_mm,
        },
    }


@router.get("/table-spec")
def get_table_spec(db: Session = Depends(get_db)):
    """テーブルスペック設定を取得"""
    config = db.query(ProjectionConfig).first()
    if not config:
        # デフォルト値でレコード作成
        config = ProjectionConfig(
            pj_width=PJ_WIDTH,
            pj_height=PJ_HEIGHT,
            pj_count=PJ_COUNT,
            blend_overlap=BLEND_OVERLAP,
            zone_count=ZONE_COUNT,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    full_width = (config.pj_width * config.pj_count) - (config.blend_overlap * (config.pj_count - 1))
    full_height = config.pj_height
    zone_width = full_width // config.zone_count
    zone_height = full_height

    return {
        "id": config.id,
        "pj_width": config.pj_width,
        "pj_height": config.pj_height,
        "pj_count": config.pj_count,
        "blend_overlap": config.blend_overlap,
        "zone_count": config.zone_count,
        "table_width_mm": config.table_width_mm if config.table_width_mm is not None else 8120,
        "table_height_mm": config.table_height_mm if config.table_height_mm is not None else 600,
        "full_width": full_width,
        "full_height": full_height,
        "zone_width": zone_width,
        "zone_height": zone_height,
        "updated_at": config.updated_at,
    }


@router.put("/table-spec")
def update_table_spec(req: ProjectionConfigUpdate, db: Session = Depends(get_db)):
    """テーブルスペック設定を更新"""
    config = db.query(ProjectionConfig).first()
    if not config:
        config = ProjectionConfig(
            pj_width=PJ_WIDTH,
            pj_height=PJ_HEIGHT,
            pj_count=PJ_COUNT,
            blend_overlap=BLEND_OVERLAP,
            zone_count=ZONE_COUNT,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    full_width = (config.pj_width * config.pj_count) - (config.blend_overlap * (config.pj_count - 1))
    full_height = config.pj_height
    zone_width = full_width // config.zone_count
    zone_height = full_height

    return {
        "id": config.id,
        "pj_width": config.pj_width,
        "pj_height": config.pj_height,
        "pj_count": config.pj_count,
        "blend_overlap": config.blend_overlap,
        "zone_count": config.zone_count,
        "table_width_mm": config.table_width_mm if config.table_width_mm is not None else 8120,
        "table_height_mm": config.table_height_mm if config.table_height_mm is not None else 600,
        "full_width": full_width,
        "full_height": full_height,
        "zone_width": zone_width,
        "zone_height": zone_height,
        "updated_at": config.updated_at,
    }


@router.post("/prompt-preview")
def preview_prompt(req: VideoGenerateRequest):
    """生成プロンプトをプレビュー（実行はしない）"""
    if req.theme not in THEME_PROMPTS:
        raise HTTPException(400, f"Unknown theme: {req.theme}")
    if req.course not in COURSE_ORDER:
        raise HTTPException(400, f"Unknown course: {req.course}")

    mode = GenerationMode(req.mode)
    try:
        prompt = _build_prompt(req.theme, req.course, mode)
    except ValueError as e:
        raise HTTPException(400, str(e))

    aspect = "21:9" if mode == GenerationMode.UNIFIED else "1:1"
    return {
        "theme": req.theme,
        "course": req.course,
        "mode": req.mode,
        "aspect_ratio": aspect,
        "prompt": prompt,
    }


@router.post("/video", response_model=JobStatusResponse)
async def generate_video(req: VideoGenerateRequest, background_tasks: BackgroundTasks):
    """映像生成をバックグラウンドで開始"""
    if req.theme not in THEME_PROMPTS:
        raise HTTPException(400, f"Unknown theme: {req.theme}")
    if req.course not in COURSE_ORDER:
        raise HTTPException(400, f"Unknown course: {req.course}")

    mode = GenerationMode(req.mode)
    provider = VideoProvider(req.provider)

    async def _run():
        try:
            if mode == GenerationMode.UNIFIED:
                await _video_service.generate_unified_course(req.theme, req.course, provider)
            else:
                await _video_service.generate_zone_course(
                    req.theme, req.course, req.zone_id or 0, provider
                )
            _active_jobs[job_id]["status"] = "complete"
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)

    job_id = f"webgen_{len(_active_jobs)+1}"
    _register_job(job_id, {
        "status": "processing",
        "theme": req.theme,
        "course": req.course,
        "mode": req.mode,
    })
    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"{req.theme}/{req.course} ({req.mode}) の生成を開始しました",
    )


@router.post("/video/batch", response_model=JobStatusResponse)
async def generate_batch(req: BatchGenerateRequest, background_tasks: BackgroundTasks):
    """テーマ全コース一括生成"""
    if req.day not in DAY_TO_THEME:
        raise HTTPException(400, f"Unknown day: {req.day}")

    theme = DAY_TO_THEME[req.day]
    mode = GenerationMode(req.mode)
    provider = VideoProvider(req.provider)

    async def _run():
        try:
            await _video_service.generate_theme_batch(theme, mode, provider)
            _active_jobs[job_id]["status"] = "complete"
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)

    job_id = f"webbatch_{len(_active_jobs)+1}"
    _register_job(job_id, {"status": "processing", "day": req.day, "mode": req.mode})
    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"{req.day} ({theme}) 全コース ({req.mode}) の一括生成を開始しました",
    )


@router.post("/video/from-courses", response_model=JobStatusResponse)
async def generate_from_courses(
    req: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """登録済みコース料理に基づいて映像を一括生成

    DBに登録されたコース料理の prompt_hint を活用して、
    料理内容に合わせた映像を生成する。
    """
    if req.day not in DAY_TO_THEME:
        raise HTTPException(400, f"Unknown day: {req.day}")

    theme = DAY_TO_THEME[req.day]
    mode = GenerationMode(req.mode)
    provider = VideoProvider(req.provider)

    # DBからその曜日のコース料理を取得
    dishes = (
        db.query(CourseDish)
        .filter(CourseDish.day_of_week == req.day)
        .order_by(CourseDish.sort_order)
        .all()
    )

    if not dishes:
        raise HTTPException(
            404, f"{req.day} のコース料理が登録されていません。先にコースを登録してください。"
        )

    # コース情報を保存 (バックグラウンドタスク用)
    dish_info = [
        {
            "id": d.id,
            "name": d.name,
            "course_key": d.course_key,
            "prompt_hint": d.prompt_hint or "",
            "description": d.description or "",
        }
        for d in dishes
    ]

    async def _run():
        try:
            completed = 0
            for dish in dish_info:
                course_key = dish["course_key"]
                if course_key not in COURSE_ORDER:
                    # カスタムコースキーの場合、最も近いデフォルトを使用
                    course_key = "main"

                # prompt_hint がある場合、ベースプロンプトに追加
                if mode == GenerationMode.UNIFIED:
                    await _video_service.generate_unified_course(
                        theme, course_key, provider,
                        extra_prompt=dish["prompt_hint"],
                    )
                else:
                    await _video_service.generate_zone_course(
                        theme, course_key, 0, provider,
                        extra_prompt=dish["prompt_hint"],
                    )
                completed += 1
                _active_jobs[job_id]["progress"] = f"{completed}/{len(dish_info)}"

            _active_jobs[job_id]["status"] = "complete"
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)

    job_id = f"webcourse_{len(_active_jobs)+1}"
    _register_job(job_id, {
        "status": "processing",
        "day": req.day,
        "mode": req.mode,
        "dish_count": len(dish_info),
        "progress": f"0/{len(dish_info)}",
        "dishes": [d["name"] for d in dish_info],
    })
    background_tasks.add_task(_run)

    dish_names = ", ".join(d["name"] for d in dish_info)
    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"{req.day} ({theme}) のコース料理 {len(dish_info)}品 ({dish_names}) の映像生成を開始しました",
    )


# ─── 合成パイプライン ────────────────────────────────────────

@router.post("/composite/stitch", response_model=JobStatusResponse)
async def composite_stitch(req: StitchRequest):
    """統一モード: L+R → 5520x1200 合成"""
    output = req.output_path or req.left_path.replace("_left.", "_stitched.")
    try:
        result = await stitch_unified(req.left_path, req.right_path, output)
        return JobStatusResponse(job_id="stitch", status="complete", message="合成完了", output_path=result)
    except Exception as e:
        raise HTTPException(500, f"Stitch failed: {e}")


@router.post("/composite/zone-fit", response_model=JobStatusResponse)
async def composite_zone_fit(req: ZoneFitRequest):
    """区画モード: 1:1 → 1380x1200"""
    output = req.output_path or req.input_path.replace(".mp4", "_fitted.mp4")
    try:
        result = await fit_zone(req.input_path, output)
        return JobStatusResponse(job_id="zone-fit", status="complete", message="区画フィット完了", output_path=result)
    except Exception as e:
        raise HTTPException(500, f"Zone fit failed: {e}")


@router.post("/composite/split", response_model=JobStatusResponse)
async def composite_split(req: SplitRequest):
    """3プロジェクター分割"""
    output_dir = req.output_dir or str(os.path.dirname(req.input_path))
    try:
        results = await split_for_projectors(req.input_path, output_dir)
        return JobStatusResponse(
            job_id="split",
            status="complete",
            message=f"3PJ分割完了: {len(results)}ファイル",
            output_path=", ".join(results),
        )
    except Exception as e:
        raise HTTPException(500, f"Split failed: {e}")


@router.get("/composite/info")
def composite_info():
    """テーブル・プロジェクターレイアウト情報"""
    return {
        "table": {
            "width": TABLE_WIDTH,
            "height": TABLE_HEIGHT,
        },
        "zones": ZONES,
        "projectors": PJ_REGIONS,
        "zone_count": ZONE_COUNT,
    }


# ─── アニメーション生成 ──────────────────────────────────────

@router.get("/animation/templates")
def list_animation_templates():
    """誕生日アニメーションテンプレート一覧"""
    return {
        k: {
            "name": v["name"],
            "description": v["description"],
            "duration": v["duration"],
        }
        for k, v in BIRTHDAY_TEMPLATES.items()
    }


@router.post("/animation", response_model=JobStatusResponse)
async def generate_animation(req: AnimateRequest, background_tasks: BackgroundTasks):
    """写真→キャラクターアニメーション生成"""
    if req.template_id not in BIRTHDAY_TEMPLATES:
        raise HTTPException(400, f"Unknown template: {req.template_id}")

    photo_path = req.photo_path
    if not photo_path:
        raise HTTPException(400, "photo_path is required")

    provider = AnimationProvider(req.provider)

    async def _run():
        try:
            job = _photo_service.create_job(
                photo_path=photo_path,
                template_id=req.template_id,
                guest_name=req.guest_name,
                zone_id=req.zone_id,
                provider=provider,
            )
            result = await _photo_service.process(job)
            _active_jobs[job_id]["status"] = result.status.value
            _active_jobs[job_id]["output_path"] = result.final_output_path
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)

    job_id = f"webanim_{len(_active_jobs)+1}"
    _register_job(job_id, {"status": "processing", "template": req.template_id})
    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"アニメーション生成開始 (テンプレート: {BIRTHDAY_TEMPLATES[req.template_id]['name']})",
    )


# ─── ジョブ管理 ──────────────────────────────────────────────

@router.get("/jobs")
def list_jobs():
    """アクティブジョブ一覧"""
    return _active_jobs


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """ジョブステータス取得"""
    if job_id not in _active_jobs:
        raise HTTPException(404, "Job not found")
    return _active_jobs[job_id]
