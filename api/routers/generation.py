"""映像生成 & 合成パイプライン ルーター

精度上の要件 (audit 2026-05-16):
- 同時 POST で job_id が衝突しないように uuid4 を使う。
- _active_jobs の register/update を asyncio.Lock で直列化する。
- processing 中の job は cap 超過 eviction の対象外にする。
- compositor 呼び出しは DB の ProjectionConfig から LayoutSpec を組み立てて注入。
- CompositorError は HTTP 500 で明示的に伝播。empty file fallback はもう存在しない。
"""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
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
    GenerationStatus,
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
    crop_to_table_band,
    LayoutSpec,
    CompositorError,
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

logger = logging.getLogger(__name__)


def _raise_if_jobs_failed(jobs) -> None:
    """generate_*_course から返ってきた GenerationJob/iterable をチェックし、
    1件でも FAILED ならまとめて RuntimeError を投げる。"""
    if jobs is None:
        return
    if not isinstance(jobs, (list, tuple)):
        jobs = [jobs]
    failed = [j for j in jobs if getattr(j, "status", None) == GenerationStatus.FAILED]
    if failed:
        msgs = [f"{getattr(j, 'job_id', '?')}: {getattr(j, 'error', 'unknown')}" for j in failed]
        raise RuntimeError(f"{len(failed)} generation job(s) failed — " + "; ".join(msgs))


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# overnight Phase 8b — codex P1 SEC: seed_image_path はこの root 配下のみ許可。
# .env / config 等の任意ローカルファイルを外部 (fal.ai / Runway) に送信させない。
_DEFAULT_SEED_ROOT = _PROJECT_ROOT / "api" / "uploads" / "seeds"
SEED_IMAGES_ROOT = Path(os.environ.get("SEED_IMAGES_ROOT", str(_DEFAULT_SEED_ROOT))).resolve()
_ALLOWED_SEED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _validate_seed_image_path(path: str) -> None:
    """ultra_wide_i2v 用 seed 画像のフェイル・ファスト検証。

    検証順序:
        1. 空文字でない
        2. SEED_IMAGES_ROOT 配下に resolve できる (path traversal 防止)
        3. 存在する通常ファイル (シンボリックリンク経由のディレクトリも拒否)
        4. 拡張子が許可リスト (.jpg/.jpeg/.png/.webp) に含まれる
        5. サイズが 100 bytes 超 (worker 側 _find_seed_image の閾値と一致)

    codex review 2026-05-16:
        round 2 P2: ``os.path.exists`` だけだとディレクトリ / 0 バイトファイルが通る。
        overnight Phase 8b (codex round 3 P1 SEC): seed_image_path をリクエスト経由で
        受け取る以上、攻撃者は ``/etc/passwd`` や ``.env`` を指定して任意ローカル
        ファイルを base64 化 → 外部 API に送信できてしまう。SEED_IMAGES_ROOT 配下に
        制限する形で path traversal を遮断する。

    Raises:
        HTTPException 400 — 検証失敗。理由 detail 内に明記。
    """
    if not path:
        raise HTTPException(400, "seed_image_path is empty")

    # 入力パス自体が symlink なら拒否 (codex round 5 厳密化)
    input_path = Path(path)
    if input_path.is_symlink():
        raise HTTPException(400, f"seed_image_path is a symlink (not allowed): {path}")

    try:
        resolved = input_path.resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise HTTPException(400, f"seed_image_path cannot be resolved: {path} ({e})")

    # SEED_IMAGES_ROOT 直下のみ許可 (codex round 6 P1: subdir 許可だと親 dir
    # symlink race を完全には閉じられないので、フラット構造を強制する)
    if resolved.parent != SEED_IMAGES_ROOT:
        raise HTTPException(
            400,
            f"seed_image_path must be directly under SEED_IMAGES_ROOT ({SEED_IMAGES_ROOT}), "
            f"no subdirectories allowed: parent was {resolved.parent}",
        )

    if not resolved.exists():
        raise HTTPException(400, f"seed_image_path not found: {path}")
    if not resolved.is_file():
        raise HTTPException(400, f"seed_image_path is not a regular file: {path}")
    if resolved.suffix.lower() not in _ALLOWED_SEED_EXTS:
        raise HTTPException(
            400,
            f"seed_image_path extension not allowed (must be one of "
            f"{sorted(_ALLOWED_SEED_EXTS)}): {path}",
        )
    try:
        size = resolved.stat().st_size
    except OSError as e:
        raise HTTPException(400, f"seed_image_path unreadable: {path} ({e})")
    if size <= 100:
        raise HTTPException(
            400,
            f"seed_image_path too small ({size} bytes, need > 100): {path}",
        )


def _layout_from_db(db: Session) -> LayoutSpec:
    """DB の ProjectionConfig を LayoutSpec に変換する。未設定ならデフォルト。"""
    config = db.query(ProjectionConfig).first()
    if not config:
        return LayoutSpec()
    return LayoutSpec(
        pj_width=config.pj_width,
        pj_height=config.pj_height,
        pj_count=config.pj_count,
        blend_overlap=config.blend_overlap,
        zone_count=config.zone_count,
    )

router = APIRouter(prefix="/api/generation", tags=["generation"])

# サービスインスタンス（シングルトン）
_video_service = VideoGeneratorService()
_photo_service = PhotoAnimatorService()


# ─── Request / Response スキーマ ──────────────────────────────

class VideoGenerateRequest(BaseModel):
    theme: str
    course: str
    mode: str = "unified"          # unified / zone / ultra_wide_i2v
    provider: str = "runway"       # runway / fal / kling / pika
    zone_id: Optional[int] = None  # zone モードの場合 1-4
    # ultra_wide_i2v 用: 外部生成 (MJ --ar 32:9 / Flux など) の超ワイド静止画パス
    seed_image_path: Optional[str] = None


class UltraWideFromStillRequest(BaseModel):
    """Option ③ 専用エンドポイント: 32:9 静止画 → Kling/Runway i2v → 5520x1200 crop。"""

    theme: str
    course: str
    seed_image_path: str           # 必須: 事前生成した 32:9 静止画
    provider: str = "fal"          # fal 推奨 (Kling i2v が input aspect を比較的尊重)
    duration_seconds: int = 10
    crop_after: bool = True        # 生成後に crop_to_table_band で 5520x1200 にする
    output_cropped_path: Optional[str] = None  # 未指定なら "<生成パス>_band.mp4"


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
# audit 2026-05-16: collision-safe な uuid4 ID + asyncio.Lock 直列化。
# processing job は eviction しない (KeyError + 追跡不能になるのを防ぐ)。
_MAX_ACTIVE_JOBS = 500
_active_jobs: dict[str, dict] = {}
_jobs_lock = asyncio.Lock()


def _new_job_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def _register_job(job_id: str, job_data: dict) -> None:
    """Register a job. cap 超過時は terminal jobs (complete/failed) のみ FIFO で
    eviction する。processing 中の job は保護する。"""
    async with _jobs_lock:
        _active_jobs[job_id] = job_data
        if len(_active_jobs) > _MAX_ACTIVE_JOBS:
            terminal = [k for k, v in _active_jobs.items()
                        if v.get("status") in ("complete", "failed")]
            for k in terminal[: len(_active_jobs) - _MAX_ACTIVE_JOBS]:
                _active_jobs.pop(k, None)


async def _update_job(job_id: str, **fields) -> None:
    """Existing job のフィールドを atomic に更新。job が消えていれば no-op。"""
    async with _jobs_lock:
        job = _active_jobs.get(job_id)
        if job is None:
            return
        job.update(fields)


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

    # overnight Phase 8c — codex P1 FUNC: audit 後 unified mode は全 provider で raise する。
    # backgrond task が必ず failed になる前に同期的に 400 を返し、有効な代替を案内する。
    if mode == GenerationMode.UNIFIED:
        raise HTTPException(
            400,
            "unified mode (21:9 segments → 5520x1200 stitch) は現行 provider "
            f"({req.provider}) では生成不可です。代替: "
            "(1) mode='zone' で 1:1 × 4 zone 並列生成、"
            "(2) mode='ultra_wide_i2v' + seed_image_path で MJ/Flux 32:9 → i2v → crop、"
            "または専用エンドポイント POST /api/generation/video/ultra-wide を使用してください。",
        )

    if mode == GenerationMode.ULTRA_WIDE_I2V:
        if not req.seed_image_path:
            raise HTTPException(
                400,
                "ultra_wide_i2v モードには seed_image_path (事前生成の 32:9 静止画) が必須です。",
            )
        # codex review 2026-05-16 P2 (round 1+2): 存在しない / ディレクトリ / 0 バイト
        # ファイルを silent fallback (placeholder / t2v) に流して別物の成果物を出すのを防ぐ。
        _validate_seed_image_path(req.seed_image_path)

    job_id = _new_job_id("webgen")

    async def _run():
        try:
            if mode == GenerationMode.UNIFIED:
                jobs = await _video_service.generate_unified_course(req.theme, req.course, provider)
            elif mode == GenerationMode.ULTRA_WIDE_I2V:
                jobs = await _video_service.generate_ultra_wide_from_still(
                    req.theme,
                    req.course,
                    seed_image_path=req.seed_image_path,  # type: ignore[arg-type]  # validated above
                    provider=provider,
                )
            else:
                jobs = await _video_service.generate_zone_course(
                    req.theme, req.course, req.zone_id or 0, provider
                )
            _raise_if_jobs_failed(jobs)
            await _update_job(job_id, status="complete")
        except Exception as e:
            logger.exception("[generate_video] job %s failed", job_id)
            await _update_job(job_id, status="failed", error=str(e))

    await _register_job(job_id, {
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


@router.post("/video/ultra-wide", response_model=JobStatusResponse)
async def generate_ultra_wide_video(
    req: UltraWideFromStillRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Option ③: 事前生成の 32:9 静止画 → Kling/Runway i2v → 中央帯 crop → 5520x1200。

    フロー:
      1. seed_image_path (MJ/Flux などで作った超ワイド静止画) を i2v に投入
      2. provider native 最大 (16:9) で動画化
      3. crop_after=True なら crop_to_table_band で table_width x table_height に切り出す

    実機検証ポイント:
      - Kling i2v が input image の超ワイド構図をどこまで保ってくれるか
        (Kling Omni 系を使うとさらに input aspect を尊重しやすい)
      - 保たれなかった場合でも、後段 crop で破綻なく 5520x1200 が出るか
    """
    if req.theme not in THEME_PROMPTS:
        raise HTTPException(400, f"Unknown theme: {req.theme}")
    if req.course not in COURSE_ORDER:
        raise HTTPException(400, f"Unknown course: {req.course}")
    # codex review 2026-05-16 P2 (round 2): existence だけでは directory/0byte が通ってしまう
    _validate_seed_image_path(req.seed_image_path)

    provider = VideoProvider(req.provider)
    job_id = _new_job_id("webuw")

    async def _run():
        try:
            gen_job = await _video_service.generate_ultra_wide_from_still(
                req.theme,
                req.course,
                seed_image_path=req.seed_image_path,
                provider=provider,
                duration_seconds=req.duration_seconds,
            )
            _raise_if_jobs_failed(gen_job)

            final_path = gen_job.output_path
            if req.crop_after and gen_job.output_path:
                layout = _layout_from_db(db)
                cropped = req.output_cropped_path or gen_job.output_path.replace(".mp4", "_band.mp4")
                final_path = await crop_to_table_band(gen_job.output_path, cropped, layout=layout)
            await _update_job(job_id, status="complete", output_path=final_path)
        except Exception as e:
            logger.exception("[generate_ultra_wide_video] job %s failed", job_id)
            await _update_job(job_id, status="failed", error=str(e))

    await _register_job(job_id, {
        "status": "processing",
        "theme": req.theme,
        "course": req.course,
        "mode": "ultra_wide_i2v",
        "provider": req.provider,
        "seed_image_path": req.seed_image_path,
        "crop_after": req.crop_after,
    })
    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"{req.theme}/{req.course} ultra-wide i2v 生成を開始しました (seed={req.seed_image_path})",
    )


@router.post("/video/batch", response_model=JobStatusResponse)
async def generate_batch(req: BatchGenerateRequest, background_tasks: BackgroundTasks):
    """テーマ全コース一括生成"""
    if req.day not in DAY_TO_THEME:
        raise HTTPException(400, f"Unknown day: {req.day}")

    theme = DAY_TO_THEME[req.day]
    mode = GenerationMode(req.mode)
    provider = VideoProvider(req.provider)

    # overnight Phase 8c — codex P1 FUNC: unified mode は generation 不可 (上記参照)
    if mode == GenerationMode.UNIFIED:
        raise HTTPException(
            400,
            "unified mode は現行 provider で生成不可。mode='zone' を指定するか、"
            "個別シーン単位で POST /api/generation/video/ultra-wide を使用してください。",
        )

    job_id = _new_job_id("webbatch")

    async def _run():
        try:
            await _video_service.generate_theme_batch(theme, mode, provider)
            await _update_job(job_id, status="complete")
        except Exception as e:
            logger.exception("[generate_batch] job %s failed", job_id)
            await _update_job(job_id, status="failed", error=str(e))

    await _register_job(job_id, {"status": "processing", "day": req.day, "mode": req.mode})
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

    # overnight Phase 8 round 4 — codex P2: unified mode は background で必ず failed に
    # なるので、同期 400 で fail-fast。
    if mode == GenerationMode.UNIFIED:
        raise HTTPException(
            400,
            "unified mode は現行 provider で生成不可。mode='zone' を指定するか、"
            "個別シーン単位で POST /api/generation/video/ultra-wide を使用してください。",
        )

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

    job_id = _new_job_id("webcourse")

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
                    jobs = await _video_service.generate_unified_course(
                        theme, course_key, provider,
                        extra_prompt=dish["prompt_hint"],
                    )
                else:
                    jobs = await _video_service.generate_zone_course(
                        theme, course_key, 0, provider,
                        extra_prompt=dish["prompt_hint"],
                    )
                _raise_if_jobs_failed(jobs)
                completed += 1
                await _update_job(job_id, progress=f"{completed}/{len(dish_info)}")

            await _update_job(job_id, status="complete")
        except Exception as e:
            logger.exception("[generate_from_courses] job %s failed", job_id)
            await _update_job(job_id, status="failed", error=str(e))

    await _register_job(job_id, {
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
async def composite_stitch(req: StitchRequest, db: Session = Depends(get_db)):
    """統一モード: L+R → table_width x table_height 合成"""
    output = req.output_path or req.left_path.replace("_left.", "_stitched.")
    layout = _layout_from_db(db)
    try:
        result = await stitch_unified(req.left_path, req.right_path, output, layout=layout)
        return JobStatusResponse(
            job_id=_new_job_id("stitch"),
            status="complete",
            message="合成完了",
            output_path=result,
        )
    except CompositorError as e:
        raise HTTPException(500, f"Stitch failed: {e}")


@router.post("/composite/zone-fit", response_model=JobStatusResponse)
async def composite_zone_fit(req: ZoneFitRequest, db: Session = Depends(get_db)):
    """区画モード: 1:1 → zone_width x zone_height"""
    output = req.output_path or req.input_path.replace(".mp4", "_fitted.mp4")
    layout = _layout_from_db(db)
    try:
        result = await fit_zone(req.input_path, output, layout=layout)
        return JobStatusResponse(
            job_id=_new_job_id("zone-fit"),
            status="complete",
            message="区画フィット完了",
            output_path=result,
        )
    except CompositorError as e:
        raise HTTPException(500, f"Zone fit failed: {e}")


@router.post("/composite/split", response_model=JobStatusResponse)
async def composite_split(req: SplitRequest, db: Session = Depends(get_db)):
    """3プロジェクター分割"""
    output_dir = req.output_dir or str(os.path.dirname(req.input_path))
    layout = _layout_from_db(db)
    try:
        results = await split_for_projectors(req.input_path, output_dir, layout=layout)
        return JobStatusResponse(
            job_id=_new_job_id("split"),
            status="complete",
            message=f"3PJ分割完了: {len(results)}ファイル",
            output_path=", ".join(results),
        )
    except CompositorError as e:
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

    job_id = _new_job_id("webanim")

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
            await _update_job(
                job_id,
                status=result.status.value,
                output_path=result.final_output_path,
            )
        except Exception as e:
            logger.exception("[generate_animation] job %s failed", job_id)
            await _update_job(job_id, status="failed", error=str(e))

    await _register_job(job_id, {"status": "processing", "template": req.template_id})
    background_tasks.add_task(_run)

    return JobStatusResponse(
        job_id=job_id,
        status="processing",
        message=f"アニメーション生成開始 (テンプレート: {BIRTHDAY_TEMPLATES[req.template_id]['name']})",
    )


# ─── ジョブ管理 ──────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs():
    """アクティブジョブ一覧"""
    async with _jobs_lock:
        return dict(_active_jobs)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """ジョブステータス取得"""
    async with _jobs_lock:
        job = _active_jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return dict(job)
