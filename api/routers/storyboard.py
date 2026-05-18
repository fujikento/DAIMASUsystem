"""ストーリーボード管理ルーター

段階的な映像生成フロー: Script → Image Preview → Video Generation
"""

import asyncio
import datetime
import json
import os
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    AppSetting,
    CourseDish,
    Storyboard,
    StoryboardScene,
    StoryboardCreate,
    StoryboardResponse,
    StoryboardListResponse,
    StoryboardSceneResponse,
    StoryboardSceneUpdate,
    StoryboardSceneCreate,
)

# ワーカーモジュールをimportできるようにパス追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workers.video_generator import (
    VideoGeneratorService,
    GenerationMode,
    VideoProvider,
    DAY_TO_THEME,
    COURSE_ORDER,
    _build_prompt,
)
from workers.image_generator import (
    ImageGeneratorService,
    ImageProvider,
)

router = APIRouter(prefix="/api/storyboards", tags=["storyboards"])

# サービスインスタンス（シングルトン）
_video_service = VideoGeneratorService()
_image_service = ImageGeneratorService()

# ─── ジョブ追跡用（インメモリ） ───────────────────────────────
# Limit dict size to prevent unbounded memory growth.
# Completed/failed jobs older than MAX_JOBS entries are evicted (FIFO).
_MAX_ACTIVE_JOBS = 500
_active_jobs: dict[str, dict] = {}

# ─── SSEイベントバス ──────────────────────────────────────────
# 接続中のSSEクライアントのキューリスト
_sse_clients: list[asyncio.Queue] = []


def _notify_clients(event_type: str, data: dict) -> None:
    """SSE接続中の全クライアントにイベントをプッシュする"""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for queue in _sse_clients:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass  # 遅いクライアントはスキップ


def _register_job(job_id: str, job_data: dict) -> None:
    """Register a job and evict the oldest entries if the dict exceeds the cap."""
    _active_jobs[job_id] = job_data
    if len(_active_jobs) > _MAX_ACTIVE_JOBS:
        # Evict entries whose status is terminal (complete/failed) first, then oldest by insertion.
        terminal = [k for k, v in _active_jobs.items() if v.get("status") in ("complete", "failed")]
        to_remove = terminal or list(_active_jobs.keys())
        for k in to_remove[: len(_active_jobs) - _MAX_ACTIVE_JOBS]:
            _active_jobs.pop(k, None)


# ─── 日本語マッピング ────────────────────────────────────────

COURSE_NAMES_JA = {
    "welcome": "ウェルカム",
    "appetizer": "前菜",
    "soup": "スープ",
    "main": "メイン",
    "dessert": "デザート",
}

# 料理が未登録の曜日用デフォルトシーン
DEFAULT_SCENES = [
    {"course_key": "welcome", "scene_description_ja": "ウェルカムシーン", "sort_order": 0},
    {"course_key": "appetizer", "scene_description_ja": "前菜シーン", "sort_order": 1},
    {"course_key": "soup", "scene_description_ja": "スープシーン", "sort_order": 2},
    {"course_key": "main", "scene_description_ja": "メインシーン", "sort_order": 3},
    {"course_key": "dessert", "scene_description_ja": "デザートシーン", "sort_order": 4},
]

THEME_NAMES_JA = {
    "zen": "禅",
    "fire": "炎",
    "ocean": "海",
    "forest": "森",
    "gold": "黄金",
    "space": "宇宙",
    "fairytale": "童話",
}

DAY_NAMES_JA = {
    "monday": "月曜日",
    "tuesday": "火曜日",
    "wednesday": "水曜日",
    "thursday": "木曜日",
    "friday": "金曜日",
    "saturday": "土曜日",
    "sunday": "日曜日",
}


def _generate_scene_description_ja(theme: str, course_key: str) -> str:
    """コースとテーマからシーンの日本語説明を生成"""
    theme_ja = THEME_NAMES_JA.get(theme, theme)
    course_ja = COURSE_NAMES_JA.get(course_key, course_key)
    return f"{theme_ja}テーマの{course_ja}シーン"


# ─── シーンプリセットライブラリ ───────────────────────────────
# NOTE: This route MUST be declared before /{storyboard_id} so that
# FastAPI does not try to coerce "scene-presets" into an integer.

@router.get("/scene-presets")
def get_scene_presets(
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """シーンプリセットライブラリを取得する。

    事前作成されたシーンテンプレートをカテゴリ・キーワードでフィルターして返す。
    ユーザーがストーリーボードを素早く作成するための出発点として使用する。

    Args:
        category: カテゴリ名でフィルター (例: "自然", "都市", "ファンタジー", "季節", "抽象")。
        search: タグ・名前・説明・プロンプトを対象としたキーワード検索。

    Returns:
        {"presets": [...]} 形式の JSON レスポンス。
    """
    from dataclasses import asdict
    from workers.scene_presets import get_presets
    presets = get_presets(category=category, search=search)
    return {"presets": [asdict(p) for p in presets]}


# ─── ジョブ管理 ──────────────────────────────────────────────
# NOTE: This route MUST be declared before /{storyboard_id} so that
# FastAPI does not try to coerce "jobs" into an integer.

@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """ストーリーボード関連ジョブのステータスを取得"""
    if job_id not in _active_jobs:
        raise HTTPException(404, "Job not found")
    return _active_jobs[job_id]


# ─── SSEエンドポイント ────────────────────────────────────────
# NOTE: This route MUST be declared before /{storyboard_id} so that
# FastAPI does not treat "events" as a storyboard_id integer.

@router.get("/events/stream")
async def storyboard_events():
    """SSEエンドポイント: ストーリーボードのリアルタイム更新をプッシュ配信する

    キューサイズを 50→200 に拡大:
    - バッチ生成(例: 10シーン並列)では短時間に多くのイベントが発生する。
    - Gemini concurrency=3 で 3シーン同時完了すると 3イベントが一瞬で積まれるため、
      バッファが小さいとイベントが欠落する可能性がある。
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _sse_clients.append(queue)

    async def event_generator():
        try:
            # 接続確立の通知
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield message
                except asyncio.TimeoutError:
                    # 30秒ごとにキープアライブを送信して接続を維持
                    yield ": keepalive\n\n"
        finally:
            # クライアント切断時にリストから削除
            try:
                _sse_clients.remove(queue)
            except ValueError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── ストーリーボード CRUD ────────────────────────────────────

@router.post("", response_model=StoryboardResponse)
def create_storyboard(data: StoryboardCreate, db: Session = Depends(get_db)):
    """ストーリーボードを作成する（絵コンテ方式）

    新しいフロー:
    - title が主キー識別子（必須、デフォルト "新しい台本"）
    - day_of_week / theme はオプション（後から設定可）
    - auto_generate_scenes=False がデフォルト（空の台本からスタート）
    - auto_generate_scenes=True の場合のみ、曜日テーマからシーンを自動生成（後方互換性）
    """
    title = data.title or "新しい台本"

    # テーマ・曜日の決定（オプション）
    day = data.day_of_week
    theme = data.theme

    # auto_generate_scenes=True かつ day_of_week が必要な場合のみ曜日を自動検出
    if data.auto_generate_scenes and not day:
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        day = days[datetime.date.today().weekday()]

    if day and day not in DAY_TO_THEME:
        raise HTTPException(400, f"Unknown day_of_week: {day}. Valid values: {list(DAY_TO_THEME.keys())}")

    # テーマを曜日から自動解決（day が指定されていて theme が未指定の場合）
    if day and not theme:
        theme = DAY_TO_THEME[day]

    # ストーリーボードを作成（day/theme は nullable）
    storyboard = Storyboard(
        title=title,
        day_of_week=day,
        theme=theme,
        mode="unified",
        provider=data.provider,
        status="draft",
        style_seed=data.style_seed,
    )
    db.add(storyboard)
    db.flush()  # IDを確定させる

    if data.auto_generate_scenes and day and theme:
        # DBからコース料理を取得
        dishes = (
            db.query(CourseDish)
            .filter(CourseDish.day_of_week == day)
            .order_by(CourseDish.sort_order)
            .all()
        )

        mode = GenerationMode.UNIFIED
        aspect_ratio = "21:9"

        # コース一覧を決定
        if dishes:
            course_items = [
                {
                    "course_key": d.course_key,
                    "dish_id": d.id,
                    "extra_prompt": d.prompt_hint or "",
                    "scene_description_ja": None,
                }
                for d in dishes
            ]
        else:
            # 料理が0件の場合: デフォルト5シーンをフォールバック生成
            course_items = [
                {
                    "course_key": s["course_key"],
                    "dish_id": None,
                    "extra_prompt": "",
                    "scene_description_ja": s["scene_description_ja"],
                }
                for s in DEFAULT_SCENES
            ]

        # シーンを生成
        for i, item in enumerate(course_items):
            course_key = item["course_key"]
            prompt_course_key = course_key if course_key in COURSE_ORDER else "main"

            try:
                prompt = _build_prompt(theme, prompt_course_key, mode)
            except ValueError:
                try:
                    prompt = _build_prompt(theme, "main", mode)
                except ValueError:
                    theme_name = THEME_NAMES_JA.get(theme, theme)
                    prompt = (
                        f"Ultra-wide panoramic top-down aerial view looking straight down, "
                        f"horizontal cinematic composition, no horizon line, designed for projection "
                        f"onto a long table surface, seamless horizontal flow, 21:9 ultrawide, 4K quality, "
                        f"{theme_name} themed {course_key} scene for immersive dining projection"
                    )

            scene_desc = item.get("scene_description_ja") or _generate_scene_description_ja(theme, course_key)

            scene = StoryboardScene(
                storyboard_id=storyboard.id,
                course_key=course_key,
                course_dish_id=item["dish_id"],
                sort_order=i,
                scene_description_ja=scene_desc,
                prompt=prompt,
                extra_prompt=item["extra_prompt"] or None,
                aspect_ratio=aspect_ratio,
                projection_mode="unified",
                duration_seconds=120,
            )
            db.add(scene)

    db.commit()
    db.refresh(storyboard)
    return storyboard


@router.get("", response_model=list[StoryboardListResponse])
def list_storyboards(db: Session = Depends(get_db)):
    """ストーリーボード一覧を取得"""
    return db.query(Storyboard).order_by(Storyboard.created_at.desc()).all()


@router.get("/{storyboard_id}/scenes/status")
def get_scenes_status(storyboard_id: int, db: Session = Depends(get_db)):
    """シーンのステータスのみを返す軽量エンドポイント（ポーリング最適化用）"""
    scenes = db.query(StoryboardScene).filter(
        StoryboardScene.storyboard_id == storyboard_id
    ).all()
    return {
        "scenes": [
            {
                "id": s.id,
                "image_status": s.image_status,
                "image_path": s.image_path,
                "video_status": s.video_status,
                "video_path": s.video_path,
            }
            for s in scenes
        ]
    }


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
def get_storyboard(storyboard_id: int, db: Session = Depends(get_db)):
    """ストーリーボード詳細（シーン含む）を取得"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")
    return sb


class StoryboardUpdate(PydanticBaseModel):
    day_of_week: Optional[str] = None
    theme: Optional[str] = None
    provider: Optional[str] = None
    title: Optional[str] = None
    style_seed: Optional[int] = None


@router.patch("/{storyboard_id}", response_model=StoryboardResponse)
def update_storyboard(storyboard_id: int, data: StoryboardUpdate, db: Session = Depends(get_db)):
    """ストーリーボードのメタデータ（タイトル・曜日・テーマ・プロバイダー）を更新する"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    if data.day_of_week is not None:
        if data.day_of_week and data.day_of_week not in DAY_TO_THEME:
            raise HTTPException(400, f"不明な曜日です: {data.day_of_week}. 有効値: {list(DAY_TO_THEME.keys())}")
        sb.day_of_week = data.day_of_week or None
        # If day is set and no explicit theme, auto-resolve theme from day
        if data.day_of_week and data.theme is None:
            sb.theme = DAY_TO_THEME.get(data.day_of_week)

    if data.theme is not None:
        sb.theme = data.theme or None

    if data.provider is not None:
        sb.provider = data.provider

    if data.title is not None:
        sb.title = data.title

    if data.style_seed is not None:
        sb.style_seed = data.style_seed

    db.commit()
    db.refresh(sb)
    return sb


@router.post("/{storyboard_id}/style-reference")
async def upload_style_reference(
    storyboard_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """スタイルリファレンス画像をアップロードし、ストーリーボードに紐付ける

    fal.ai プロバイダーで画像生成する際、このリファレンス画像のスタイルを
    参考にして一貫性のあるビジュアルを生成する。
    """
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "JPEG、PNG、または WebP 画像のみアップロード可能です")

    # Save to uploads directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(project_root, "api", "uploads", "style_references")
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"style_ref_{storyboard_id}.{ext}"
    file_path = os.path.join(upload_dir, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    sb.style_reference_path = file_path
    db.commit()
    db.refresh(sb)

    return {
        "ok": True,
        "style_reference_path": file_path,
        "file_size_kb": round(len(content) / 1024, 1),
    }


@router.delete("/{storyboard_id}")
def delete_storyboard(storyboard_id: int, db: Session = Depends(get_db)):
    """ストーリーボードを削除"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")
    db.delete(sb)
    db.commit()
    return {"ok": True}


# ─── シーン編集 ───────────────────────────────────────────────

class ReorderRequest(PydanticBaseModel):
    scene_ids: list[int]


@router.put("/{storyboard_id}/scenes/reorder", response_model=StoryboardResponse)
def reorder_scenes(storyboard_id: int, data: ReorderRequest, db: Session = Depends(get_db)):
    """シーンの順序を変更する"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "Storyboard not found")
    for i, scene_id in enumerate(data.scene_ids):
        scene = db.query(StoryboardScene).filter(
            StoryboardScene.id == scene_id,
            StoryboardScene.storyboard_id == storyboard_id
        ).first()
        if scene:
            scene.sort_order = i
    db.commit()
    db.refresh(sb)
    return sb


@router.put("/{storyboard_id}/scenes/{scene_id}", response_model=StoryboardSceneResponse)
def update_scene(
    storyboard_id: int,
    scene_id: int,
    data: StoryboardSceneUpdate,
    db: Session = Depends(get_db),
):
    """シーンを編集する（プロンプト・説明・ステージング設定を更新）"""
    scene = (
        db.query(StoryboardScene)
        .filter(
            StoryboardScene.id == scene_id,
            StoryboardScene.storyboard_id == storyboard_id,
        )
        .first()
    )
    if not scene:
        raise HTTPException(404, "シーンが見つかりません")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scene, key, value)

    db.commit()
    db.refresh(scene)
    return scene


class SceneCreateWithCourse(StoryboardSceneCreate):
    """シーン作成 + コース料理情報を統合したリクエストモデル"""
    # 統合コース情報フィールド
    course_name: Optional[str] = None         # 料理名
    course_description: Optional[str] = None  # 料理の説明
    prompt_hint: Optional[str] = None         # 映像プロンプトヒント
    save_course: bool = False                  # DBにコース料理を保存するか


@router.post("/{storyboard_id}/scenes", response_model=StoryboardResponse)
def add_scene(storyboard_id: int, scene_data: SceneCreateWithCourse, db: Session = Depends(get_db)):
    """ストーリーボードにシーンを追加する（コース料理情報も一緒に保存可能）"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "Storyboard not found")

    # Calculate sort_order (append to end)
    max_order = db.query(func.max(StoryboardScene.sort_order)).filter(
        StoryboardScene.storyboard_id == storyboard_id
    ).scalar() or -1

    # コース料理情報がある場合はDBに保存し、course_dish_idをリンク
    course_dish_id = None
    extra_prompt = None
    if scene_data.save_course and scene_data.course_name:
        dish = CourseDish(
            name=scene_data.course_name,
            course_key=scene_data.course_key,
            description=scene_data.course_description or None,
            day_of_week=sb.day_of_week,
            sort_order=max_order + 1,
            prompt_hint=scene_data.prompt_hint or None,
        )
        db.add(dish)
        db.flush()
        course_dish_id = dish.id
        extra_prompt = scene_data.prompt_hint or None

    # Auto-generate prompt if not provided
    prompt = scene_data.prompt
    if not prompt:
        theme = sb.theme
        if theme:
            mode = GenerationMode(scene_data.projection_mode) if scene_data.projection_mode != "custom" else GenerationMode.UNIFIED
            course_key = scene_data.course_key if scene_data.course_key in COURSE_ORDER else "main"
            try:
                prompt = _build_prompt(theme, course_key, mode)
            except ValueError:
                try:
                    prompt = _build_prompt(theme, "main", GenerationMode.UNIFIED)
                except ValueError:
                    prompt = (
                        "Ultra-wide panoramic top-down aerial view looking straight down, "
                        "horizontal cinematic composition, no horizon line, designed for projection "
                        "onto a long table surface, seamless horizontal flow, 21:9 ultrawide, 4K quality, "
                        "immersive dining table projection"
                    )
        else:
            # No theme — use scene description as the base prompt
            scene_desc = scene_data.scene_description_ja or "immersive dining scene"
            prompt = (
                f"Ultra-wide panoramic top-down aerial view looking straight down, "
                f"horizontal cinematic composition, no horizon line, designed for projection "
                f"onto a long table surface, seamless horizontal flow, 21:9 ultrawide, 4K quality, "
                f"{scene_desc}"
            )

    # Determine aspect_ratio from projection_mode
    if scene_data.projection_mode == "zone":
        aspect_ratio = "1:1"
    else:
        aspect_ratio = "21:9"

    scene = StoryboardScene(
        storyboard_id=storyboard_id,
        course_key=scene_data.course_key,
        course_dish_id=course_dish_id,
        sort_order=max_order + 1,
        scene_title=scene_data.scene_title,
        scene_description_ja=scene_data.scene_description_ja,
        mood=scene_data.mood,
        camera_angle=scene_data.camera_angle,
        prompt=prompt,
        extra_prompt=extra_prompt,
        duration_seconds=scene_data.duration_seconds,
        transition=scene_data.transition,
        aspect_ratio=aspect_ratio,
        projection_mode=scene_data.projection_mode,
        target_zones=scene_data.target_zones,
        color_tone=scene_data.color_tone,
        brightness=scene_data.brightness,
        animation_speed=scene_data.animation_speed,
        prompt_modifier=scene_data.prompt_modifier,
    )
    db.add(scene)
    db.commit()
    db.refresh(sb)
    return sb


class SceneCourseUpdate(PydanticBaseModel):
    """シーンに紐づくコース料理情報の更新リクエスト"""
    course_name: Optional[str] = None
    course_description: Optional[str] = None
    prompt_hint: Optional[str] = None
    course_key: Optional[str] = None
    day_of_week: Optional[str] = None
    sort_order: Optional[int] = None


@router.put("/{storyboard_id}/scenes/{scene_id}/course")
def update_scene_course(
    storyboard_id: int,
    scene_id: int,
    data: SceneCourseUpdate,
    db: Session = Depends(get_db),
):
    """シーンのコース料理情報を更新または作成し、DBに保存する"""
    scene = (
        db.query(StoryboardScene)
        .filter(
            StoryboardScene.id == scene_id,
            StoryboardScene.storyboard_id == storyboard_id,
        )
        .first()
    )
    if not scene:
        raise HTTPException(404, "シーンが見つかりません")

    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()

    dish = None
    if data.course_name:
        if scene.course_dish_id:
            # 既存コース料理を更新
            dish = db.query(CourseDish).filter(CourseDish.id == scene.course_dish_id).first()
        if not dish:
            # 新しいコース料理を作成
            dish = CourseDish(
                day_of_week=data.day_of_week or (sb.day_of_week if sb else "monday"),
                sort_order=data.sort_order if data.sort_order is not None else scene.sort_order,
            )
            db.add(dish)

        dish.name = data.course_name
        if data.course_key is not None:
            dish.course_key = data.course_key
        elif not dish.course_key:
            dish.course_key = scene.course_key
        if data.course_description is not None:
            dish.description = data.course_description or None
        if data.prompt_hint is not None:
            dish.prompt_hint = data.prompt_hint or None
        if data.day_of_week is not None:
            dish.day_of_week = data.day_of_week
        if data.sort_order is not None:
            dish.sort_order = data.sort_order

        db.flush()
        scene.course_dish_id = dish.id
        # プロンプトヒントをextra_promptにも反映
        if data.prompt_hint is not None:
            scene.extra_prompt = data.prompt_hint or None

    if data.course_key is not None:
        scene.course_key = data.course_key

    db.commit()
    db.refresh(scene)

    scene_resp = {
        "id": scene.id,
        "storyboard_id": scene.storyboard_id,
        "course_key": scene.course_key,
        "course_dish_id": scene.course_dish_id,
        "sort_order": scene.sort_order,
        # 絵コンテ fields
        "scene_title": scene.scene_title,
        "scene_description_ja": scene.scene_description_ja,
        "mood": scene.mood,
        "camera_angle": scene.camera_angle,
        "prompt": scene.prompt,
        "prompt_edited": scene.prompt_edited,
        "extra_prompt": scene.extra_prompt,
        "duration_seconds": scene.duration_seconds,
        "transition": scene.transition,
        "aspect_ratio": scene.aspect_ratio,
        "projection_mode": scene.projection_mode,
        "target_zones": scene.target_zones,
        "color_tone": scene.color_tone,
        "brightness": scene.brightness,
        "animation_speed": scene.animation_speed,
        "prompt_modifier": scene.prompt_modifier,
        "image_status": scene.image_status,
        "image_path": scene.image_path,
        "video_status": scene.video_status,
        "video_path": scene.video_path,
        "created_at": scene.created_at,
        "updated_at": scene.updated_at,
    }
    dish_resp = None
    if dish:
        db.refresh(dish)
        dish_resp = {
            "id": dish.id,
            "name": dish.name,
            "course_key": dish.course_key,
            "description": dish.description,
            "day_of_week": dish.day_of_week,
            "sort_order": dish.sort_order,
            "prompt_hint": dish.prompt_hint,
            "created_at": dish.created_at,
        }

    return {"scene": scene_resp, "course": dish_resp}


@router.delete("/{storyboard_id}/scenes/{scene_id}", response_model=StoryboardResponse)
def delete_scene(storyboard_id: int, scene_id: int, db: Session = Depends(get_db)):
    """ストーリーボードからシーンを削除し、残りのシーンを再番号付けする"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "Storyboard not found")
    scene = db.query(StoryboardScene).filter(
        StoryboardScene.id == scene_id,
        StoryboardScene.storyboard_id == storyboard_id
    ).first()
    if not scene:
        raise HTTPException(404, "Scene not found")
    db.delete(scene)
    # Reorder remaining scenes
    remaining = db.query(StoryboardScene).filter(
        StoryboardScene.storyboard_id == storyboard_id
    ).order_by(StoryboardScene.sort_order).all()
    for i, s in enumerate(remaining):
        s.sort_order = i
    db.commit()
    db.refresh(sb)
    return sb


# ─── スクリプト自動生成（Gemini） ────────────────────────────

class DishConcept(PydanticBaseModel):
    name: str       # e.g. "1品目 前菜"
    concept: str    # e.g. "千と千尋の神隠し風"

class GenerateScriptRequest(PydanticBaseModel):
    concept: str | None = None              # full_course mode
    mode: str = "full_course"               # "full_course" | "per_dish"
    dishes: list[DishConcept] | None = None  # per_dish mode


def _build_full_course_prompt(concept: str) -> str:
    return f"""あなたはバーカウンターの天面にプロジェクションマッピングで映像を投影する、イマーシブダイニング体験の演出プロデューサーです。

ゲストから以下のコンセプトを受け取りました：

「{concept}」

このコンセプトの世界観を最大限に活かした、12〜20シーンの映像ストーリーボードを作成してください。

## 重要な前提
- 映像はバーカウンターの天面（横長）に上から投影されます
- ゲストはカウンターの周りに座り、上から見下ろして鑑賞します
- つまり全ての映像は「俯瞰（真上から見下ろした構図）」で設計してください
- コース料理の提供中に流れる映像です（全体で20〜30分）
- 1シーンは30〜60秒の演出単位（動画はループ再生で尺を調整）

## ストーリーの流れ
- 序盤: 静かに世界が現れる導入
- 中盤: 「{concept}」の世界観を深く展開、色彩や動きが豊かに
- クライマックス: 最も印象的で感動的なビジュアル
- 終盤: 余韻を残して静かに閉じる

## scene_description_ja について（最重要）
この項目は画像生成AI（Google Imagen）のプロンプトとしてそのまま使われます。
「{concept}」の世界観に忠実で、かつ視覚的に美しい画像が生成されるよう、以下を意識してください：
- 「何が見えるか」を具体的に書く（抽象的な感情ではなく、目に映るものを描写）
- 俯瞰視点であることを明記する
- 色、光、質感、動きを具体的に含める
- 人物の顔やテキストは含めない（風景・環境・抽象表現に徹する）
- 画像生成に有効な英語キーワード（top-down view, cinematic lighting, ultra detailed 等）を適宜混ぜてOK

## 出力形式
以下のJSON配列のみを返してください。他のテキストは一切不要です：

[
  {{
    "scene_title": "シーンの短いタイトル（日本語）",
    "scene_description_ja": "画像生成プロンプトとして使える詳細なビジュアル描写（150〜300文字）",
    "narration": "映画のト書き風の演出説明（このシーンで何が起きているか、ゲストは何を感じるか）",
    "mood": "calm | dramatic | mysterious | festive | romantic | epic",
    "camera_angle": "bird_eye | wide | close_up | dynamic",
    "transition": "crossfade | fade_black | cut | dissolve",
    "duration_seconds": 30〜60
  }}
]
"""


def _build_dish_prompt(dish_name: str, dish_concept: str) -> str:
    return f"""あなたはバーカウンターの天面にプロジェクションマッピングで映像を投影する、イマーシブダイニング体験の演出プロデューサーです。

料理「{dish_name}」の提供に合わせて投影する映像台本を作成します。
この料理のテーマは「{dish_concept}」です。

「{dish_concept}」の世界観を最大限に活かした、5〜10シーンの映像ストーリーボードを作成してください。

## 重要な前提
- 映像はバーカウンターの天面（横長）に上から投影されます
- ゲストはカウンターの周りに座り、上から見下ろして鑑賞します
- つまり全ての映像は「俯瞰（真上から見下ろした構図）」で設計してください
- この料理の提供〜次の料理までの約3〜5分間を映像で演出します
- 1シーンは30〜60秒の演出単位（動画はループ再生で尺を調整）

## ストーリーの流れ
- 導入: 「{dish_concept}」の世界が静かに現れる
- 展開: テーマの世界観を豊かに広げる
- 結び: 美しく締めくくり、次の料理への余韻を残す

## scene_description_ja について（最重要）
この項目は画像生成AI（Google Imagen）のプロンプトとしてそのまま使われます。
「{dish_concept}」の世界観に忠実で、かつ視覚的に美しい画像が生成されるよう、以下を意識してください：
- 「何が見えるか」を具体的に書く（抽象的な感情ではなく、目に映るものを描写）
- 俯瞰視点であることを明記する
- 色、光、質感、動きを具体的に含める
- 人物の顔やテキストは含めない（風景・環境・抽象表現に徹する）
- 画像生成に有効な英語キーワード（top-down view, cinematic lighting, ultra detailed 等）を適宜混ぜてOK

## 出力形式
以下のJSON配列のみを返してください。他のテキストは一切不要です：

[
  {{
    "scene_title": "シーンの短いタイトル（日本語）",
    "scene_description_ja": "画像生成プロンプトとして使える詳細なビジュアル描写（150〜300文字）",
    "narration": "映画のト書き風の演出説明",
    "mood": "calm | dramatic | mysterious | festive | romantic | epic",
    "camera_angle": "bird_eye | wide | close_up | dynamic",
    "transition": "crossfade | fade_black | cut | dissolve",
    "duration_seconds": 30〜60
  }}
]
"""


async def _call_gemini(prompt: str, db: Session) -> list[dict]:
    """Gemini APIを呼び出してシーンデータのリストを返す"""
    import google.genai as genai

    # DBの設定テーブルから取得し、なければ環境変数にフォールバック
    setting = db.query(AppSetting).filter(AppSetting.key == "GEMINI_API_KEY").first()
    api_key = (setting.value if setting and setting.value else "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "GEMINI_API_KEY が設定されていません")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw_text = response.text
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Gemini API 呼び出しに失敗しました: {exc}") from exc

    # JSONレスポンスをパース（マークダウンのコードブロックを除去）
    text = raw_text.strip()
    if text.startswith("```"):
        # ```json ... ``` または ``` ... ``` 形式を除去
        lines = text.splitlines()
        # 先頭行（```json など）と末尾行（```）を取り除く
        inner_lines = []
        in_block = False
        for line in lines:
            if not in_block and line.startswith("```"):
                in_block = True
                continue
            if in_block and line.strip() == "```":
                in_block = False
                continue
            if in_block:
                inner_lines.append(line)
        text = "\n".join(inner_lines).strip()

    try:
        scenes_data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(502, f"Geminiのレスポンスをパースできませんでした: {exc}\n生レスポンス: {raw_text[:500]}") from exc

    if not isinstance(scenes_data, list):
        raise HTTPException(502, "Geminiのレスポンスがリスト形式ではありません")

    return scenes_data


@router.post("/{storyboard_id}/generate-script", response_model=StoryboardResponse)
async def generate_script(
    storyboard_id: int,
    request: GenerateScriptRequest,
    db: Session = Depends(get_db),
):
    """Geminiを使用してコンセプトからシーンを自動生成し、ストーリーボードを更新する"""

    # 1. ストーリーボードを取得
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "Storyboard not found")

    # 2. 既存シーンを削除（Geminiで置き換える）
    db.query(StoryboardScene).filter(
        StoryboardScene.storyboard_id == storyboard_id
    ).delete()
    db.flush()

    # 3. モードに応じてGeminiでシーン描写を生成
    if request.mode == "per_dish" and request.dishes:
        all_scenes: list[dict] = []
        for dish_idx, dish in enumerate(request.dishes):
            prompt = _build_dish_prompt(dish.name, dish.concept)
            scenes = await _call_gemini(prompt, db)
            for scene in scenes:
                scene["dish_index"] = dish_idx
                scene["dish_name"] = dish.name
            all_scenes.extend(scenes)
    else:
        prompt = _build_full_course_prompt(request.concept or "")
        all_scenes = await _call_gemini(prompt, db)

    # 4. StoryboardSceneレコードを作成
    for i, item in enumerate(all_scenes):
        dish_idx = item.get("dish_index")
        course_key = f"dish_{dish_idx + 1}" if dish_idx is not None else "custom"

        scene = StoryboardScene(
            storyboard_id=storyboard_id,
            course_key=course_key,
            sort_order=i,
            scene_title=item.get("scene_title", f"シーン {i + 1}"),
            scene_description_ja=item.get("scene_description_ja", ""),
            mood=item.get("mood"),
            camera_angle=item.get("camera_angle", "bird_eye"),
            prompt=item.get("scene_description_ja", ""),
            extra_prompt=item.get("narration", ""),
            duration_seconds=item.get("duration_seconds", 45),
            transition=item.get("transition", "crossfade"),
            aspect_ratio="21:9",
            projection_mode="unified",
            color_tone="neutral",
            brightness="normal",
            animation_speed="normal",
        )
        db.add(scene)

    # 5. ストーリーボードのステータスを "script_ready" に更新
    sb.status = "script_ready"
    db.commit()
    db.refresh(sb)

    # 6. 完全なストーリーボードレスポンスを返す
    return sb


# ─── 画像生成 ────────────────────────────────────────────────

class GenerateImagesRequest(PydanticBaseModel):
    # provider=None (省略) → endpoint 側で key の有無を見て smart fallback:
    #   OPENAI_API_KEY 有 → gpt_image_2 (最高品質、新 default)
    #   OPENAI_API_KEY 無 → imagen (既存 default、後方互換性維持)
    # 明示指定 (provider="gpt_image_2" 等) はそのまま尊重。
    provider: Optional[str] = None
    # gpt-image-2 で scene[N+1] を生成する際に scene[N] の出力を style reference として
    # 渡すか。default True (gpt-image-2 のとき有効)。他の provider では無視される。
    chain_style: bool = True


@router.post("/{storyboard_id}/generate-images")
async def generate_images(
    storyboard_id: int,
    background_tasks: BackgroundTasks,
    body: GenerateImagesRequest = GenerateImagesRequest(),
    db: Session = Depends(get_db),
):
    """全ペンディング・失敗シーンの画像を一括生成（バックグラウンド実行）"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    # Include both "pending" and "failed" scenes so that:
    # 1. A fresh Generate All works on new (pending) scenes.
    # 2. After an orphaned/failed generation, users can click Generate All
    #    again to retry without needing to manually reset each scene.
    pending_scenes = [s for s in sb.scenes if s.image_status in ("pending", "failed")]
    if not pending_scenes:
        raise HTTPException(400, "生成対象のペンディングシーンがありません")

    # Capture storyboard-level style_seed for fal.ai consistency
    storyboard_style_seed = sb.style_seed

    # ジョブ情報をシリアライズ可能な形式で保存
    scene_data = [
        {
            "id": s.id,
            "storyboard_id": storyboard_id,  # SSE通知用
            "prompt": s.prompt_edited or s.prompt,
            "extra_prompt": s.extra_prompt,
            "scene_description_ja": s.scene_description_ja,
            "aspect_ratio": s.aspect_ratio,
            "projection_mode": s.projection_mode or "unified",
            "target_zones": s.target_zones,
            "mood": s.mood,
            "camera_angle": s.camera_angle,
            "color_tone": s.color_tone or "neutral",
            "brightness": s.brightness or "normal",
            "animation_speed": s.animation_speed or "normal",
            "prompt_modifier": s.prompt_modifier,
            "style_seed": storyboard_style_seed,
        }
        for s in pending_scenes
    ]

    # ステータスを更新
    for scene in pending_scenes:
        scene.image_status = "generating"
    sb.status = "images_generating"
    db.commit()

    # provider 解決:
    #   - 明示指定 (body.provider != None): そのまま使う (無効値なら ValueError → imagen にフォールバック)
    #   - 省略 (body.provider is None): OPENAI_API_KEY の有無で smart default
    #     * 有 → gpt_image_2 (最高品質)
    #     * 無 → imagen (既存 default、後方互換性維持)
    #   The storyboard's `provider` field is for VIDEO generation only and must not be
    #   used here to avoid silently falling back to a placeholder-only provider (runway).
    from api.models.schemas import AppSetting as _AppSetting  # local import to avoid cycles
    if body.provider is None:
        _has_openai = bool(
            os.environ.get("OPENAI_API_KEY")
            or (db.query(_AppSetting)
                .filter(_AppSetting.key == "OPENAI_API_KEY")
                .first()
                and (
                    db.query(_AppSetting)
                    .filter(_AppSetting.key == "OPENAI_API_KEY")
                    .first().value
                ))
        )
        image_provider_str = "gpt_image_2" if _has_openai else "imagen"
        print(f"[ImageGen] Default provider resolved to '{image_provider_str}' (OPENAI_API_KEY {'present' if _has_openai else 'absent'})")
    else:
        image_provider_str = body.provider
    try:
        provider = ImageProvider(image_provider_str)
    except ValueError:
        # 無効な provider 名なら既存 default の imagen に落とす (gpt_image_2 ではなく)
        provider = ImageProvider.IMAGEN
        image_provider_str = "imagen"

    # gpt-image-2 + chain_style 有効時のみ scene-to-scene style chain を serial 実行する。
    # 前シーンの出力が次の reference 入力になるので並列化できないが、style 一貫性を最大化。
    use_style_chain = body.chain_style and provider == ImageProvider.GPT_IMAGE_2

    job_id = f"imgbatch_{storyboard_id}_{len(_active_jobs) + 1}"
    _register_job(job_id, {
        "status": "processing",
        "storyboard_id": storyboard_id,
        "scene_count": len(scene_data),
        "progress": f"0/{len(scene_data)}",
        "started_at": datetime.datetime.now().timestamp(),
        "scenes_completed": 0,
        "total_scenes": len(scene_data),
        "avg_time_per_scene": None,
        "estimated_remaining_seconds": None,
    })

    async def _run():
        import time as _time
        import asyncio as _asyncio
        from api.models.database import SessionLocal
        _batch_wall_start = _time.monotonic()
        print(f"[TIMING] ===== BATCH START: {len(scene_data)} scenes, provider={image_provider_str} =====")

        tone_map = {
            "warm": "warm golden tones, amber lighting",
            "cool": "cool blue tones, moonlit atmosphere",
            "vivid": "vibrant saturated colors, high contrast",
        }
        bright_map = {
            "dark": "dramatic low-key lighting, deep shadows, moody atmosphere",
            "bright": "bright ethereal lighting, luminous glow, radiant",
        }
        speed_map = {
            "slow": "slow graceful movement, gentle flowing motion",
            "fast": "dynamic energetic motion, rapid flowing movement",
        }

        # Timestamp when the parallel batch starts — used for remaining-time estimate.
        batch_start = _time.monotonic()
        _active_jobs[job_id]["batch_start"] = batch_start
        # scenes_completed is updated atomically from each parallel task.
        _active_jobs[job_id]["scenes_completed"] = 0

        async def _generate_one(scene_info: dict, reference_image_paths: Optional[list[str]] = None) -> None:
            """Generate image for a single scene in its own DB session.

            Change 7: DB session is opened AFTER the image generation call so
            that expensive API time does not hold an open connection.

            chain_style (gpt-image-2 のみ): reference_image_paths が渡された場合、
            client.images.edit() で前シーンの style を引き継いで生成する。
            """
            scene_start = _time.monotonic()
            # scene_description_ja がある場合はそれをメインプロンプトとして使用。
            # _build_aspect_prompt が投影・レイアウト指示を追加するため、
            # 技術テンプレートの二重追加を避ける。
            scene_description_ja = scene_info.get("scene_description_ja")
            if scene_description_ja:
                prompt = scene_description_ja
            else:
                prompt = scene_info["prompt"]
            if scene_info.get("extra_prompt"):
                prompt = f"{prompt}, inspired by the dish: {scene_info['extra_prompt']}"

            color_tone = scene_info.get("color_tone", "neutral")
            brightness = scene_info.get("brightness", "normal")
            animation_speed = scene_info.get("animation_speed", "normal")
            prompt_modifier = scene_info.get("prompt_modifier")
            if color_tone and color_tone != "neutral" and color_tone in tone_map:
                prompt += f", {tone_map[color_tone]}"
            if brightness and brightness != "normal" and brightness in bright_map:
                prompt += f", {bright_map[brightness]}"
            if animation_speed and animation_speed != "normal" and animation_speed in speed_map:
                prompt += f", {speed_map[animation_speed]}"
            if prompt_modifier:
                prompt += f", {prompt_modifier}"

            img_job = _image_service.create_job(
                prompt=prompt,
                scene_id=scene_info["id"],
                provider=provider,
                aspect_ratio=scene_info["aspect_ratio"],
                projection_mode=scene_info.get("projection_mode", "unified"),
                target_zones=scene_info.get("target_zones"),
                mood=scene_info.get("mood"),
                camera_angle=scene_info.get("camera_angle"),
                style_seed=scene_info.get("style_seed"),
                reference_image_paths=reference_image_paths,
            )
            # Run image generation BEFORE opening a DB session (Change 7)
            await _image_service.generate(img_job)

            # Open DB session only for the status-update write
            _db = SessionLocal()
            try:
                scene = _db.query(StoryboardScene).filter(StoryboardScene.id == scene_info["id"]).first()
                if scene:
                    if img_job.status.value == "complete":
                        # Treat 0-byte output files as failures (placeholder, no real API key)
                        if (
                            img_job.output_path
                            and os.path.exists(img_job.output_path)
                            and os.path.getsize(img_job.output_path) == 0
                        ):
                            scene.image_status = "failed"
                            scene.image_path = None
                        else:
                            scene.image_status = "complete"
                            # Store web-accessible relative URL, not the filesystem path
                            filename = os.path.basename(img_job.output_path)
                            scene.image_path = f"/static/previews/{filename}"
                    else:
                        scene.image_status = "failed"
                        scene.image_path = None
                    scene.image_job_id = img_job.job_id
                    _db.commit()

                    # シーン更新イベントをSSEクライアントにプッシュ
                    _notify_clients("scene_updated", {
                        "storyboard_id": scene_info["storyboard_id"],
                        "scene_id": scene_info["id"],
                        "image_status": scene.image_status,
                        "image_path": scene.image_path,
                    })
            finally:
                _db.close()

            # Atomically increment completed count and update progress tracking.
            scene_elapsed = _time.monotonic() - scene_start
            completed = _active_jobs[job_id]["scenes_completed"] + 1
            _active_jobs[job_id]["scenes_completed"] = completed
            _active_jobs[job_id]["progress"] = f"{completed}/{len(scene_data)}"
            # For parallel execution: estimated remaining is based on wall-clock
            # time elapsed since the batch started and how many scenes are left.
            elapsed_since_batch_start = _time.monotonic() - batch_start
            remaining_scenes = len(scene_data) - completed
            if completed > 0 and remaining_scenes > 0:
                # avg wall-clock time per completed scene (some ran concurrently)
                avg_wall = elapsed_since_batch_start / completed
                estimated_remaining = avg_wall * remaining_scenes
            else:
                estimated_remaining = 0.0
            _active_jobs[job_id]["avg_time_per_scene"] = round(scene_elapsed, 2)
            _active_jobs[job_id]["estimated_remaining_seconds"] = round(estimated_remaining, 1)

        try:
            # use_style_chain (gpt-image-2 のみ): serial 実行で scene[N-1] の出力を
            # scene[N] の reference に渡す。並列化できないが style 一貫性を最大化。
            if use_style_chain:
                print(f"[ImageGen] Batch strategy: STYLE CHAIN (serial) | provider={image_provider_str} | scenes={len(scene_data)}")
                # PROJECT_ROOT/api/uploads/previews 配下の絶対パスに resolved する。
                # scene.image_path は "/static/previews/<filename>" (web 用 url) の形なので、
                # filesystem ref に変換するため _image_service.output_dir を流用する。
                previous_fs_path: Optional[str] = None
                results: list[Optional[Exception]] = [None] * len(scene_data)
                for i, scene_info in enumerate(scene_data):
                    refs = [previous_fs_path] if previous_fs_path else None
                    try:
                        await _generate_one(scene_info, reference_image_paths=refs)
                        # 次の iteration のために最新の output_path を web ref に変換せず
                        # filesystem 絶対パスのまま保持する。DB 経由で再取得する。
                        _db_lookup = SessionLocal()
                        try:
                            scene_obj = _db_lookup.query(StoryboardScene).filter(
                                StoryboardScene.id == scene_info["id"]
                            ).first()
                            if scene_obj and scene_obj.image_path:
                                # image_path は "/static/previews/<filename>" なので
                                # _image_service.output_dir 配下の実パスに変換する
                                filename = os.path.basename(scene_obj.image_path)
                                fs_path = str(_image_service.output_dir / filename)
                                if os.path.isfile(fs_path) and os.path.getsize(fs_path) > 100:
                                    previous_fs_path = fs_path
                                else:
                                    # 失敗 / placeholder の場合は chain をリセット
                                    previous_fs_path = None
                            else:
                                previous_fs_path = None
                        finally:
                            _db_lookup.close()
                    except Exception as e:
                        results[i] = e
                        print(f"[ImageGen] Style-chain scene {scene_info['id']} failed: {e}")
                        # 失敗時は chain をリセット (壊れた参照を引き継がない)
                        previous_fs_path = None
            else:
                # Provider-specific concurrency strategy (既存): 5 concurrent + stagger.
                is_gemini = image_provider_str in ("gemini", "gemini_pro")
                concurrency = min(5, len(scene_data)) if is_gemini else min(5, len(scene_data))
                sem = _asyncio.Semaphore(concurrency)
                stagger_interval = 0.2 if is_gemini else 0.2
                print(f"[ImageGen] Batch strategy: provider={image_provider_str}, concurrency={concurrency}, scenes={len(scene_data)}, stagger={stagger_interval*1000:.0f}ms/slot")

                async def _generate_one_with_sem(scene_info: dict, scene_index: int) -> None:
                    if scene_index < concurrency and scene_index > 0:
                        await _asyncio.sleep(stagger_interval * scene_index)
                    async with sem:
                        await _generate_one(scene_info)

                tasks = [_generate_one_with_sem(si, i) for i, si in enumerate(scene_data)]
                results = await _asyncio.gather(*tasks, return_exceptions=True)

            # Log any per-scene exceptions (they don't abort sibling tasks).
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"[ImageGen] Scene {scene_data[i]['id']} failed: {result}")

            # 全シーン完了後にストーリーボードステータスを更新
            _db_final = SessionLocal()
            try:
                _sb = _db_final.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
                if _sb:
                    all_done = all(
                        s.image_status in ("complete", "failed") for s in _sb.scenes
                    )
                    if all_done:
                        _sb.status = "images_ready"
                        _db_final.commit()
                        # ストーリーボードのステータス変更をSSEクライアントにプッシュ
                        _notify_clients("storyboard_updated", {
                            "storyboard_id": storyboard_id,
                            "status": "images_ready",
                        })
            finally:
                _db_final.close()

            _batch_wall_elapsed = _time.monotonic() - _batch_wall_start
            print(f"[TIMING] ===== BATCH DONE: {len(scene_data)} scenes in {_batch_wall_elapsed*1000:.0f}ms ({_batch_wall_elapsed:.1f}s) =====")
            _active_jobs[job_id]["status"] = "complete"
        except Exception as e:
            _batch_wall_elapsed = _time.monotonic() - _batch_wall_start
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)
            print(f"[ImageGen] Batch _run() failed after {_batch_wall_elapsed:.1f}s: {e}")
            # Reset any scenes still stuck at "generating" to "failed"
            # so the UI does not hang indefinitely on those scenes
            try:
                _db_cleanup = SessionLocal()
                try:
                    for scene_info in scene_data:
                        stuck = _db_cleanup.query(StoryboardScene).filter(
                            StoryboardScene.id == scene_info["id"],
                            StoryboardScene.image_status == "generating",
                        ).first()
                        if stuck:
                            stuck.image_status = "failed"
                            # 失敗シーンをSSEクライアントに通知
                            _notify_clients("scene_updated", {
                                "storyboard_id": scene_info["storyboard_id"],
                                "scene_id": scene_info["id"],
                                "image_status": "failed",
                                "image_path": None,
                            })
                    _sb = _db_cleanup.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
                    if _sb and _sb.status == "images_generating":
                        _sb.status = "images_ready"
                        _notify_clients("storyboard_updated", {
                            "storyboard_id": storyboard_id,
                            "status": "images_ready",
                        })
                    _db_cleanup.commit()
                finally:
                    _db_cleanup.close()
            except Exception as cleanup_err:
                print(f"[ImageGen] Cleanup after failure also failed: {cleanup_err}")

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"{len(scene_data)}シーンの画像生成を開始しました",
        "scene_count": len(scene_data),
    }


class GenerateSingleImageRequest(PydanticBaseModel):
    # provider=None (省略) → backend smart-default (generate_images と同じロジック)
    provider: Optional[str] = None


@router.post("/{storyboard_id}/scenes/{scene_id}/generate-image")
async def generate_single_image(
    storyboard_id: int,
    scene_id: int,
    background_tasks: BackgroundTasks,
    body: GenerateSingleImageRequest = GenerateSingleImageRequest(),
    db: Session = Depends(get_db),
):
    """単一シーンの画像を再生成（バックグラウンド実行）"""
    scene = (
        db.query(StoryboardScene)
        .filter(
            StoryboardScene.id == scene_id,
            StoryboardScene.storyboard_id == storyboard_id,
        )
        .first()
    )
    if not scene:
        raise HTTPException(404, "シーンが見つかりません")

    # provider 解決 — generate_images と同じ smart-default ロジックを共有:
    #   省略時: OPENAI_API_KEY 有 → gpt_image_2 / 無 → imagen
    #   明示指定: そのまま (無効値は imagen にフォールバック)
    from api.models.schemas import AppSetting as _AppSetting
    if body.provider is None:
        _setting = (
            db.query(_AppSetting)
            .filter(_AppSetting.key == "OPENAI_API_KEY")
            .first()
        )
        _has_openai = bool(
            os.environ.get("OPENAI_API_KEY") or (_setting and _setting.value)
        )
        image_provider_str = "gpt_image_2" if _has_openai else "imagen"
    else:
        image_provider_str = body.provider
    try:
        provider = ImageProvider(image_provider_str)
    except ValueError:
        provider = ImageProvider.IMAGEN
        image_provider_str = "imagen"

    # Fetch storyboard-level style_seed
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()

    scene.image_status = "generating"
    db.commit()

    scene_info = {
        "id": scene.id,
        "storyboard_id": storyboard_id,  # SSE通知用
        "prompt": scene.prompt_edited or scene.prompt,
        "extra_prompt": scene.extra_prompt,
        "scene_description_ja": scene.scene_description_ja,
        "aspect_ratio": scene.aspect_ratio,
        "projection_mode": scene.projection_mode or "unified",
        "target_zones": scene.target_zones,
        "mood": scene.mood,
        "camera_angle": scene.camera_angle,
        "color_tone": scene.color_tone or "neutral",
        "brightness": scene.brightness or "normal",
        "animation_speed": scene.animation_speed or "normal",
        "prompt_modifier": scene.prompt_modifier,
        "style_seed": sb.style_seed if sb else None,
    }

    job_id = f"imgscene_{scene_id}_{len(_active_jobs) + 1}"
    _register_job(job_id, {
        "status": "processing",
        "storyboard_id": storyboard_id,
        "scene_id": scene_id,
    })

    async def _run():
        from api.models.database import SessionLocal

        tone_map = {
            "warm": "warm golden tones, amber lighting",
            "cool": "cool blue tones, moonlit atmosphere",
            "vivid": "vibrant saturated colors, high contrast",
        }
        bright_map = {
            "dark": "dramatic low-key lighting, deep shadows, moody atmosphere",
            "bright": "bright ethereal lighting, luminous glow, radiant",
        }
        speed_map = {
            "slow": "slow graceful movement, gentle flowing motion",
            "fast": "dynamic energetic motion, rapid flowing movement",
        }

        try:
            scene_description_ja = scene_info.get("scene_description_ja")
            if scene_description_ja:
                prompt = scene_description_ja
            else:
                prompt = scene_info["prompt"]
            if scene_info.get("extra_prompt"):
                prompt = f"{prompt}, inspired by the dish: {scene_info['extra_prompt']}"
            # Apply staging modifiers to the prompt
            color_tone = scene_info.get("color_tone", "neutral")
            brightness = scene_info.get("brightness", "normal")
            animation_speed = scene_info.get("animation_speed", "normal")
            prompt_modifier = scene_info.get("prompt_modifier")
            if color_tone and color_tone != "neutral" and color_tone in tone_map:
                prompt += f", {tone_map[color_tone]}"
            if brightness and brightness != "normal" and brightness in bright_map:
                prompt += f", {bright_map[brightness]}"
            if animation_speed and animation_speed != "normal" and animation_speed in speed_map:
                prompt += f", {speed_map[animation_speed]}"
            if prompt_modifier:
                prompt += f", {prompt_modifier}"

            img_job = _image_service.create_job(
                prompt=prompt,
                scene_id=scene_info["id"],
                provider=provider,
                aspect_ratio=scene_info["aspect_ratio"],
                projection_mode=scene_info.get("projection_mode", "unified"),
                target_zones=scene_info.get("target_zones"),
                mood=scene_info.get("mood"),
                camera_angle=scene_info.get("camera_angle"),
                style_seed=scene_info.get("style_seed"),
            )
            # Run image generation BEFORE opening a DB session (same as batch _generate_one)
            # so that the expensive API call does not hold an open DB connection.
            await _image_service.generate(img_job)

            # Open DB session only for the status-update write
            _db = SessionLocal()
            try:
                _scene = _db.query(StoryboardScene).filter(StoryboardScene.id == scene_info["id"]).first()
                if _scene:
                    if img_job.status.value == "complete":
                        # Treat 0-byte output files as failures (placeholder, no real API key)
                        if (
                            img_job.output_path
                            and os.path.exists(img_job.output_path)
                            and os.path.getsize(img_job.output_path) == 0
                        ):
                            _scene.image_status = "failed"
                            _scene.image_path = None
                        else:
                            _scene.image_status = "complete"
                            # Store web-accessible relative URL, not the filesystem path
                            filename = os.path.basename(img_job.output_path)
                            _scene.image_path = f"/static/previews/{filename}"
                    else:
                        _scene.image_status = "failed"
                        _scene.image_path = None
                    _scene.image_job_id = img_job.job_id
                    _db.commit()

                    # シーン更新イベントをSSEクライアントにプッシュ
                    _notify_clients("scene_updated", {
                        "storyboard_id": scene_info["storyboard_id"],
                        "scene_id": scene_info["id"],
                        "image_status": _scene.image_status,
                        "image_path": _scene.image_path,
                    })
            finally:
                _db.close()

            _active_jobs[job_id]["status"] = "complete"
            _active_jobs[job_id]["output_path"] = img_job.output_path
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)
            print(f"[ImageGen] Single-scene _run() failed for scene {scene_id}: {e}")
            # Reset scene stuck at "generating" to "failed"
            # so the UI does not hang indefinitely
            try:
                _db_cleanup = SessionLocal()
                try:
                    stuck = _db_cleanup.query(StoryboardScene).filter(
                        StoryboardScene.id == scene_info["id"],
                        StoryboardScene.image_status == "generating",
                    ).first()
                    if stuck:
                        stuck.image_status = "failed"
                        _db_cleanup.commit()
                        # 失敗をSSEクライアントに通知
                        _notify_clients("scene_updated", {
                            "storyboard_id": scene_info["storyboard_id"],
                            "scene_id": scene_info["id"],
                            "image_status": "failed",
                            "image_path": None,
                        })
                finally:
                    _db_cleanup.close()
            except Exception as cleanup_err:
                print(f"[ImageGen] Cleanup after failure also failed: {cleanup_err}")

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"シーン {scene_id} の画像再生成を開始しました",
    }


@router.post("/{storyboard_id}/approve-images", response_model=StoryboardResponse)
def approve_images(storyboard_id: int, db: Session = Depends(get_db)):
    """画像を承認し、ビデオ生成フェーズへ進める"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    if sb.status not in ("images_ready", "images_generating"):
        raise HTTPException(
            400,
            f"画像承認はimages_readyまたはimages_generatingステータスでのみ可能です（現在: {sb.status}）",
        )

    sb.status = "images_ready"
    db.commit()
    db.refresh(sb)

    return sb


# ─── 映像生成 ────────────────────────────────────────────────

@router.post("/{storyboard_id}/generate-videos")
async def generate_videos(
    storyboard_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """全シーンのビデオを一括生成（バックグラウンド実行）"""
    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    pending_scenes = [s for s in sb.scenes if s.video_status == "pending"]
    if not pending_scenes:
        raise HTTPException(400, "生成対象のペンディングシーンがありません")

    scene_data = [
        {
            "id": s.id,
            "course_key": s.course_key,
            "prompt": s.prompt_edited or s.prompt,
            "extra_prompt": s.extra_prompt,
            "duration_seconds": s.duration_seconds,
            "aspect_ratio": s.aspect_ratio,
            "projection_mode": s.projection_mode or "unified",
            "color_tone": s.color_tone or "neutral",
            "brightness": s.brightness or "normal",
            "animation_speed": s.animation_speed or "normal",
            "prompt_modifier": s.prompt_modifier,
        }
        for s in pending_scenes
    ]

    for scene in pending_scenes:
        scene.video_status = "generating"
    sb.status = "video_generating"
    db.commit()

    try:
        provider = VideoProvider(sb.provider)
    except ValueError:
        provider = VideoProvider.RUNWAY

    job_id = f"vidbatch_{storyboard_id}_{len(_active_jobs) + 1}"
    _register_job(job_id, {
        "status": "processing",
        "storyboard_id": storyboard_id,
        "scene_count": len(scene_data),
        "progress": f"0/{len(scene_data)}",
    })

    async def _run():
        from api.models.database import SessionLocal
        _db = SessionLocal()
        try:
            completed = 0
            for scene_info in scene_data:
                scene_mode_str = scene_info.get("projection_mode", "unified")
                try:
                    scene_mode = GenerationMode(scene_mode_str)
                except ValueError:
                    scene_mode = GenerationMode.UNIFIED
                vid_job = _video_service.create_job(
                    theme=sb.theme,
                    course=scene_info["course_key"] if scene_info["course_key"] in COURSE_ORDER else "main",
                    mode=scene_mode,
                    provider=provider,
                    duration_seconds=scene_info["duration_seconds"],
                    extra_prompt=scene_info.get("extra_prompt"),
                    color_tone=scene_info.get("color_tone", "neutral"),
                    brightness=scene_info.get("brightness", "normal"),
                    animation_speed=scene_info.get("animation_speed", "normal"),
                    prompt_modifier=scene_info.get("prompt_modifier"),
                )
                await _video_service.generate(vid_job)

                _scene = _db.query(StoryboardScene).filter(StoryboardScene.id == scene_info["id"]).first()
                if _scene:
                    _scene.video_status = vid_job.status.value
                    _scene.video_path = vid_job.output_path if vid_job.status.value == "complete" else None
                    _scene.video_job_id = vid_job.job_id
                    _db.commit()
                    # ビデオシーン更新をSSEクライアントにプッシュ
                    _notify_clients("scene_updated", {
                        "storyboard_id": storyboard_id,
                        "scene_id": scene_info["id"],
                        "video_status": _scene.video_status,
                        "video_path": _scene.video_path,
                    })

                completed += 1
                _active_jobs[job_id]["progress"] = f"{completed}/{len(scene_data)}"

            _sb = _db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
            if _sb:
                all_done = all(
                    s.video_status in ("complete", "failed") for s in _sb.scenes
                )
                if all_done:
                    _sb.status = "video_ready"
                    _db.commit()
                    # ストーリーボードのビデオ完了をSSEクライアントにプッシュ
                    _notify_clients("storyboard_updated", {
                        "storyboard_id": storyboard_id,
                        "status": "video_ready",
                    })

            _active_jobs[job_id]["status"] = "complete"
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)
            print(f"[VideoGen] Batch _run() failed: {e}")
            # Reset any scenes still stuck at "generating" to "failed"
            # so the UI does not hang indefinitely on those scenes
            try:
                _db_cleanup = SessionLocal()
                try:
                    for scene_info in scene_data:
                        stuck = _db_cleanup.query(StoryboardScene).filter(
                            StoryboardScene.id == scene_info["id"],
                            StoryboardScene.video_status == "generating",
                        ).first()
                        if stuck:
                            stuck.video_status = "failed"
                    _sb = _db_cleanup.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
                    if _sb and _sb.status == "video_generating":
                        _sb.status = "video_ready"
                        _notify_clients("storyboard_updated", {
                            "storyboard_id": storyboard_id,
                            "status": "video_ready",
                        })
                    _db_cleanup.commit()
                finally:
                    _db_cleanup.close()
            except Exception as cleanup_err:
                print(f"[VideoGen] Cleanup after failure also failed: {cleanup_err}")
        finally:
            _db.close()

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"{len(scene_data)}シーンのビデオ生成を開始しました",
        "scene_count": len(scene_data),
    }


@router.post("/{storyboard_id}/scenes/{scene_id}/generate-video")
async def generate_single_video(
    storyboard_id: int,
    scene_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """単一シーンのビデオを再生成（バックグラウンド実行）"""
    scene = (
        db.query(StoryboardScene)
        .filter(
            StoryboardScene.id == scene_id,
            StoryboardScene.storyboard_id == storyboard_id,
        )
        .first()
    )
    if not scene:
        raise HTTPException(404, "シーンが見つかりません")

    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()

    try:
        provider = VideoProvider(sb.provider)
    except (ValueError, AttributeError):
        provider = VideoProvider.RUNWAY

    scene.video_status = "generating"
    db.commit()

    scene_info = {
        "id": scene.id,
        "course_key": scene.course_key,
        "prompt": scene.prompt_edited or scene.prompt,
        "extra_prompt": scene.extra_prompt,
        "duration_seconds": scene.duration_seconds,
        "aspect_ratio": scene.aspect_ratio,
        "theme": sb.theme if sb else "ocean",
        "projection_mode": scene.projection_mode or "unified",
        "color_tone": scene.color_tone or "neutral",
        "brightness": scene.brightness or "normal",
        "animation_speed": scene.animation_speed or "normal",
        "prompt_modifier": scene.prompt_modifier,
    }

    job_id = f"vidscene_{scene_id}_{len(_active_jobs) + 1}"
    _register_job(job_id, {
        "status": "processing",
        "storyboard_id": storyboard_id,
        "scene_id": scene_id,
    })

    async def _run():
        from api.models.database import SessionLocal
        _db = SessionLocal()
        try:
            course_key = scene_info["course_key"]
            if course_key not in COURSE_ORDER:
                course_key = "main"

            scene_mode_str = scene_info.get("projection_mode", "unified")
            try:
                scene_mode = GenerationMode(scene_mode_str)
            except ValueError:
                scene_mode = GenerationMode.UNIFIED

            vid_job = _video_service.create_job(
                theme=scene_info["theme"],
                course=course_key,
                mode=scene_mode,
                provider=provider,
                duration_seconds=scene_info["duration_seconds"],
                extra_prompt=scene_info.get("extra_prompt"),
                color_tone=scene_info.get("color_tone", "neutral"),
                brightness=scene_info.get("brightness", "normal"),
                animation_speed=scene_info.get("animation_speed", "normal"),
                prompt_modifier=scene_info.get("prompt_modifier"),
            )
            await _video_service.generate(vid_job)

            _scene = _db.query(StoryboardScene).filter(StoryboardScene.id == scene_info["id"]).first()
            if _scene:
                _scene.video_status = vid_job.status.value
                _scene.video_path = vid_job.output_path if vid_job.status.value == "complete" else None
                _scene.video_job_id = vid_job.job_id
                _db.commit()

            _active_jobs[job_id]["status"] = "complete"
            _active_jobs[job_id]["output_path"] = vid_job.output_path
        except Exception as e:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = str(e)
        finally:
            _db.close()

    background_tasks.add_task(_run)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": f"シーン {scene_id} のビデオ再生成を開始しました",
    }


@router.get("/{storyboard_id}/generation-status")
def get_generation_status(storyboard_id: int, db: Session = Depends(get_db)):
    """画像生成の進捗・残り時間を返す

    Returns:
        status: generating | complete | idle
        total_scenes: 総シーン数
        completed_scenes: 完了シーン数
        elapsed_seconds: 開始からの経過秒数
        avg_seconds_per_scene: 1シーンあたりの平均処理秒数
        estimated_remaining_seconds: 残り推定秒数
    """
    import time as _time

    sb = db.query(Storyboard).filter(Storyboard.id == storyboard_id).first()
    if not sb:
        raise HTTPException(404, "ストーリーボードが見つかりません")

    # アクティブなバッチジョブを検索
    active_job = None
    for job in _active_jobs.values():
        if (
            job.get("storyboard_id") == storyboard_id
            and job.get("status") == "processing"
            and "total_scenes" in job
        ):
            active_job = job
            break

    if active_job is None or sb.status != "images_generating":
        # No active in-memory job found.  If the storyboard is still marked
        # "images_generating" it means the server restarted (clearing _active_jobs)
        # while generation was in progress.  Auto-heal: reset any scenes still
        # stuck at "generating" to "failed" and update the storyboard status so
        # the frontend can proceed instead of spinning forever.
        if active_job is None and sb.status == "images_generating":
            any_stuck = False
            for s in sb.scenes:
                if s.image_status == "generating":
                    s.image_status = "failed"
                    any_stuck = True
            if any_stuck:
                print(
                    f"[GenStatus] Orphaned generation detected for storyboard {storyboard_id}. "
                    "Resetting stuck 'generating' scenes to 'failed'."
                )
            sb.status = "images_ready"
            db.commit()
            db.refresh(sb)

        # 生成中でない場合はDBからシーン数を集計
        all_scenes = sb.scenes
        completed = sum(1 for s in all_scenes if s.image_status in ("complete", "failed"))
        return {
            "status": "idle",
            "total_scenes": len(all_scenes),
            "completed_scenes": completed,
            "elapsed_seconds": None,
            "avg_seconds_per_scene": None,
            "estimated_remaining_seconds": None,
        }

    started_at = active_job.get("started_at")
    elapsed = round(_time.time() - started_at, 1) if started_at else None

    return {
        "status": "generating",
        "total_scenes": active_job.get("total_scenes", 0),
        "completed_scenes": active_job.get("scenes_completed", 0),
        "elapsed_seconds": elapsed,
        "avg_seconds_per_scene": active_job.get("avg_time_per_scene"),
        "estimated_remaining_seconds": active_job.get("estimated_remaining_seconds"),
    }
