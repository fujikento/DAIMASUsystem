"""
AI画像生成ワーカー

ストーリーボードのシーンごとにプレビュー画像を生成する。
生成フロー: Script → Image Preview → Video Generation

対応プロバイダー:
  gemini     — Nano Banana (Gemini 2.5 Flash Image) - fast, cheap
  gemini_pro — Nano Banana Pro (Gemini 3 Pro Image) - higher quality
  imagen     — Imagen 4 Fast (imagen-4.0-fast-generate-001) - fastest (3-5s)
  flux       — Flux Pro (placeholder)
  runway     — Runway (placeholder)

物理テーブルサイズ: 8120mm × 600mm
有効解像度: 5520×1200px (3プロジェクター × 1920px、オーバーラップ除く、高さ1200px)
アスペクト比: ~4.6:1 (ultra-wide)

使い方:
    service = ImageGeneratorService()
    job = service.create_job(prompt="...", scene_id=1)
    await service.generate(job)

Speed optimisations applied:
  Opt-1: Top-level PIL import to avoid per-call import-lock contention
  Opt-2: Module-level font cache for template generation
  Opt-3: Unified post-processing eliminates redundant canvas+paste for unified/zone
  Opt-4: Gemini response_modalities=["IMAGE"] only (no TEXT generation overhead)
  Opt-5: Parallel post-processing + metadata save via asyncio.gather
  Opt-6: Template JPEG quality 60 (layout guide, not final output)
  Opt-7: Imagen output_compression_quality 80 (preview, saves transfer bytes)
  Opt-8: DB import cached at module level; sys.path.insert runs once
  Opt-9: Use _API_THREAD_POOL consistently for post-processing
  Opt-10: Gemini sampling params removed (temperature/top_p/top_k default is fine for images)
"""

import asyncio
import concurrent.futures
import functools
import io
import json
import os
import time
import time as _time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Union

# Opt-1: Top-level PIL import to avoid repeated import-lock acquisition
# under concurrent thread-pool execution.  Python caches modules, but the
# import machinery still acquires the GIL + import lock each time.
from PIL import Image as _PILImage

# Module-level ThreadPoolExecutor shared across all ImageGeneratorService instances.
# Limits the number of OS threads used for blocking API calls to avoid thread explosion
# when multiple concurrent image generation requests arrive simultaneously.
# max_workers=8: supports up to 3 Gemini + 5 Imagen concurrent calls with headroom.
_API_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="imggen")

# ── API key cache (Change 4) ──────────────────────────────────────────────────
_api_key_cache: dict[str, tuple[str, float]] = {}
_API_KEY_TTL = 30.0  # seconds

# ── Opt-8: Lazy DB imports cached at module level ─────────────────────────────
_db_imports_ready = False
_SessionLocal = None
_AppSetting = None


def _ensure_db_imports():
    """One-time import of DB models.  Avoids sys.path.insert + import on every call."""
    global _db_imports_ready, _SessionLocal, _AppSetting
    if _db_imports_ready:
        return
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from api.models.database import SessionLocal
        from api.models.schemas import AppSetting
        _SessionLocal = SessionLocal
        _AppSetting = AppSetting
    except Exception:
        pass
    _db_imports_ready = True


# ── Opt-2: Module-level font cache ───────────────────────────────────────────
_cached_font: Optional[object] = None
_font_resolved = False


def _get_template_font():
    """Return a cached font object for template zone labels.

    Resolves the font once on first call and caches the result at module level.
    Subsequent calls return immediately without any filesystem probing.
    """
    global _cached_font, _font_resolved
    if _font_resolved:
        return _cached_font

    from PIL import ImageFont
    _FONT_CANDIDATES = [
        "/System/Library/Fonts/Helvetica.ttc",             # macOS
        "/System/Library/Fonts/SFNSMono.ttf",              # macOS alternative
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux
    ]
    font = ImageFont.load_default()
    for _fp in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(_fp, size=18)
            break
        except Exception:
            continue
    _cached_font = font
    _font_resolved = True
    return _cached_font


class ImageProvider(str, Enum):
    GEMINI = "gemini"           # Nano Banana (Gemini 2.5 Flash Image) - fast, cheap
    GEMINI_PRO = "gemini_pro"   # Nano Banana Pro (Gemini 3 Pro Image) - higher quality
    IMAGEN = "imagen"           # Imagen 4 Fast - fastest (3-5s)
    IMAGEN_FAST = "imagen_fast" # Alias for Imagen 4 Fast
    FLUX = "flux"               # Flux Pro (placeholder)
    RUNWAY = "runway"           # Runway (placeholder)


class ImageStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


# Table physical constants
TABLE_FULL_WIDTH: int = 5520    # pixels (3 × 1920px projectors minus overlaps)
TABLE_FULL_HEIGHT: int = 1200   # pixels
TABLE_ZONE_COUNT: int = 4
TABLE_ZONE_WIDTH: int = TABLE_FULL_WIDTH // TABLE_ZONE_COUNT  # 1380px per zone
TABLE_SEAT_COUNT: int = 8
TABLE_SEAT_WIDTH: int = TABLE_FULL_WIDTH // TABLE_SEAT_COUNT  # 690px per seat


@dataclass
class ImageGenerationJob:
    job_id: str
    prompt: str
    scene_id: int
    provider: ImageProvider = ImageProvider.GEMINI
    status: ImageStatus = ImageStatus.QUEUED
    output_path: Optional[str] = None
    error: Optional[str] = None
    aspect_ratio: str = "21:9"
    projection_mode: str = "unified"
    target_zones: Optional[str] = None
    mood: Optional[str] = None         # calm/dramatic/mysterious/festive/romantic/epic
    camera_angle: Optional[str] = None  # bird_eye/wide/close_up/pan/dynamic
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    preview_only: bool = True


def _fit_to_canvas(img: "_PILImage.Image", target_w: int, target_h: int) -> "_PILImage.Image":
    """Resize and center-crop an image to fill target dimensions exactly.

    Scales the image so that it fully covers the target canvas (crop-to-fill),
    then center-crops any excess. The returned image is exactly target_w x target_h.

    Uses BILINEAR resampling for ~3x faster resize vs LANCZOS with equivalent
    visual quality for screen display.

    Args:
        img: Source PIL Image object.
        target_w: Target canvas width in pixels.
        target_h: Target canvas height in pixels.

    Returns:
        A new PIL Image of exactly target_w x target_h.
    """
    orig_w, orig_h = img.size
    ratio_w = target_w / orig_w
    ratio_h = target_h / orig_h

    # Use the larger ratio so the image fully covers the canvas (crop-to-fill)
    scale = max(ratio_w, ratio_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    # BILINEAR is ~3x faster than LANCZOS and visually equivalent for screen display
    resized = img.resize((new_w, new_h), _PILImage.BILINEAR)

    # Center-crop to exact target size
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    cropped = resized.crop((left, top, left + target_w, top + target_h))

    return cropped


def _get_api_key(key_name: str) -> str:
    """Get API key from database, falling back to environment variable.

    Results are cached for _API_KEY_TTL seconds to avoid a DB round-trip on
    every call while still picking up key rotations within ~30 s.

    Opt-8: DB imports are cached at module level so sys.path.insert and
    from-imports execute only once across all calls.
    """
    # Check cache first (Change 4)
    if key_name in _api_key_cache:
        cached_value, cached_at = _api_key_cache[key_name]
        if _time.monotonic() - cached_at < _API_KEY_TTL:
            return cached_value

    # Opt-8: Use module-level cached imports
    _ensure_db_imports()

    value = ""
    if _SessionLocal is not None and _AppSetting is not None:
        try:
            db = _SessionLocal()
            try:
                setting = db.query(_AppSetting).filter(_AppSetting.key == key_name).first()
                value = setting.value if (setting and setting.value) else ""
            finally:
                db.close()
        except Exception:
            value = os.environ.get(key_name, "")
    else:
        value = os.environ.get(key_name, "")

    if not value:
        value = os.environ.get(key_name, "")

    _api_key_cache[key_name] = (value, _time.monotonic())
    return value


def _default_output_dir() -> str:
    """Return the previews directory relative to the project root."""
    # workers/ -> project root -> touchdesigner/content/previews
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "touchdesigner", "content", "previews")


class ImageGeneratorService:
    """AI画像生成サービス（ストーリーボードプレビュー用）"""

    def __init__(
        self,
        output_dir: str = "",
    ):
        if not output_dir:
            output_dir = _default_output_dir()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, ImageGenerationJob] = {}
        self._job_counter = 0

        self.gemini_api_key = _get_api_key("GEMINI_API_KEY")
        self.flux_api_key = _get_api_key("FLUX_API_KEY")
        self.runway_api_key = _get_api_key("RUNWAY_API_KEY")

        # Cached Gemini client — lazily initialised on first use.
        # Storing the key that was used to build the client lets us detect
        # when the user has rotated the key in Settings and rebuild accordingly.
        self._gemini_api_key: Optional[str] = None
        self._gemini_client: Optional[object] = None

        # Cache for template guide images keyed by (projection_mode, target_zones).
        # Each entry stores (PIL Image, JPEG bytes) so the JPEG encoding step is
        # also skipped on repeated calls (Change 5).
        self._template_cache: dict[tuple[str, Optional[str]], tuple["_PILImage.Image", bytes]] = {}

    def _get_gemini_client(self) -> object:
        """Return a cached genai.Client, rebuilding only when the API key changes.

        The key is re-fetched from the database each call so that a key saved
        via the Settings UI takes effect on the very next generation without
        requiring a service restart.  The expensive Client object is reused as
        long as the key stays the same.

        Returns:
            An initialised genai.Client instance.

        Raises:
            RuntimeError: If no Gemini API key is available.
        """
        from google import genai

        current_key = _get_api_key("GEMINI_API_KEY")
        if not current_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        if self._gemini_client is None or self._gemini_api_key != current_key:
            self._gemini_api_key = current_key
            self._gemini_client = genai.Client(api_key=current_key)

        return self._gemini_client

    def create_job(
        self,
        prompt: str,
        scene_id: int,
        provider: ImageProvider = ImageProvider.GEMINI,
        aspect_ratio: str = "21:9",
        projection_mode: str = "unified",
        target_zones: Optional[str] = None,
        mood: Optional[str] = None,
        camera_angle: Optional[str] = None,
        preview_only: bool = True,
    ) -> ImageGenerationJob:
        """画像生成ジョブを作成"""
        self._job_counter += 1
        job_id = f"img_{self._job_counter}_{int(time.time())}"

        # Imagen provider outputs JPEG; all others default to jpg for preview_only
        # and jpg for post-processed output as well (smaller, faster).
        ext = "jpg"
        filename = f"scene_{scene_id}_{job_id}.{ext}"
        output_path = str(self.output_dir / filename)

        job = ImageGenerationJob(
            job_id=job_id,
            prompt=prompt,
            scene_id=scene_id,
            provider=provider,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            projection_mode=projection_mode,
            target_zones=target_zones,
            mood=mood,
            camera_angle=camera_angle,
            preview_only=preview_only,
        )
        self.jobs[job_id] = job
        return job

    async def generate(self, job: ImageGenerationJob) -> ImageGenerationJob:
        """画像を生成（APIコール）"""
        job.status = ImageStatus.GENERATING
        print(f"[ImageGen] Starting: {job.job_id}")
        print(f"[ImageGen] Provider: {job.provider.value} | Aspect: {job.aspect_ratio} | Mode: {job.projection_mode} | preview_only: {job.preview_only}")
        print(f"[ImageGen] Prompt: {job.prompt[:100]}...")

        try:
            if job.provider == ImageProvider.GEMINI:
                await self._generate_gemini(job)
            elif job.provider == ImageProvider.GEMINI_PRO:
                await self._generate_gemini_pro(job)
            elif job.provider in (ImageProvider.IMAGEN, ImageProvider.IMAGEN_FAST):
                await self._generate_imagen(job)
            elif job.provider == ImageProvider.FLUX:
                await self._generate_flux(job)
            elif job.provider == ImageProvider.RUNWAY:
                await self._generate_runway(job)

            job.status = ImageStatus.COMPLETE
            job.completed_at = time.time()
            print(f"[ImageGen] Complete: {job.job_id} -> {job.output_path}")

        except Exception as e:
            job.status = ImageStatus.FAILED
            job.error = str(e)
            print(f"[ImageGen] Failed: {job.job_id} - {e}")

        return job

    async def generate_batch(
        self,
        jobs: list[ImageGenerationJob],
        concurrency: int = 3,
        stagger_interval: float = 0.3,
    ) -> list[ImageGenerationJob]:
        """複数シーンの画像を並列生成（セマフォ+初期バーストストラガー方式）

        改善点:
        - 旧実装: delay = 500ms x index で最後のシーンが O(n) 待機 (10シーンなら4.5秒の純粋な待機)
        - 新実装: 最初の `concurrency` タスクのみストラガー、残りはセマフォで自然に制御
          => 初期バースト分散 + 最大並列度を維持

        Args:
            jobs: 生成対象ジョブのリスト。
            concurrency: 同時実行数の上限 (デフォルト: 3)。
            stagger_interval: 初期バーストのスロット間隔秒数 (デフォルト: 0.3秒)。
        """
        n = len(jobs)
        effective_concurrency = min(concurrency, n)
        print(
            f"\n[ImageGen] Batch: {n} scenes | "
            f"concurrency={effective_concurrency} | "
            f"stagger={stagger_interval*1000:.0f}ms/slot (initial burst only)"
        )

        sem = asyncio.Semaphore(effective_concurrency)

        async def _run_with_sem(job: ImageGenerationJob, idx: int) -> ImageGenerationJob:
            # Only stagger the first `effective_concurrency` tasks to spread the initial burst.
            # Subsequent tasks wait on the semaphore naturally (no artificial delay).
            if idx < effective_concurrency and idx > 0:
                await asyncio.sleep(stagger_interval * idx)
            async with sem:
                return await self.generate(job)

        results = await asyncio.gather(*[_run_with_sem(j, i) for i, j in enumerate(jobs)])
        return list(results)

    # Mapping from camera_angle preset value to composition instruction
    _CAMERA_ANGLE_INSTRUCTIONS: dict[str, str] = {
        "bird_eye": "Top-down aerial view looking straight down, bird's-eye perspective",
        "wide": "Ultra-wide panoramic landscape view stretching to the horizon",
        "close_up": "Detailed close-up macro view with intimate scale and fine texture",
        "pan": "Sweeping panoramic view with dramatic horizontal sweep from edge to edge",
        "dynamic": "Dynamic perspective with strong depth cues, foreshortening, and layered planes",
    }

    # Mapping from mood preset value to additional prompt modifiers
    _MOOD_INSTRUCTIONS: dict[str, str] = {
        "calm": (
            "soft diffused lighting, gentle tonal range, tranquil atmosphere, "
            "slow serene pacing, no harsh contrasts"
        ),
        "dramatic": (
            "high contrast dramatic lighting, deep shadows and intense highlights, "
            "cinematic tension, powerful and striking visual impact"
        ),
        "mysterious": (
            "ethereal moody atmosphere, subtle darkness with selective illumination, "
            "sense of hidden depth and wonder, otherworldly quality"
        ),
        "festive": (
            "bright celebratory lighting, vibrant saturated colors, "
            "energetic and joyful visual rhythm, warm festive glow"
        ),
        "romantic": (
            "warm soft backlighting, golden and rose tonal warmth, "
            "intimate scale, dreamy soft focus at edges"
        ),
        "epic": (
            "massive scale composition, heroic dramatic lighting, "
            "awe-inspiring grandeur, cinematic widescreen energy"
        ),
    }

    def _build_aspect_prompt(
        self,
        base_prompt: str,
        aspect_ratio: str,
        projection_mode: str = "unified",
        target_zones: Optional[str] = None,
        mood: Optional[str] = None,
        camera_angle: Optional[str] = None,
    ) -> str:
        """アスペクト比・投影モード・ムード・カメラアングルに応じたプロンプトを構築する。

        物理テーブル解像度 5520x1200px (4.6:1) に合わせたレイアウトを
        プロンプト自体で AI に指示する。後処理はピクセル精度保証の
        セーフティネットとして残す。

        Args:
            base_prompt: 元のシーン説明プロンプト。
            aspect_ratio: アスペクト比文字列 ("21:9", "1:1" など)。
            projection_mode: 投影モード ("unified", "zone", "custom")。
            target_zones: custom モード時の使用ゾーン番号 (例: "2,3")。
                          1〜4 の 1-indexed カンマ区切り文字列。
            mood: シーンの雰囲気 ("calm", "dramatic", "mysterious", "festive", "romantic", "epic")。
                  プロンプトに照明・コントラスト・雰囲気の指示を追加する。
            camera_angle: カメラアングルプリセット ("bird_eye", "wide", "close_up", "pan", "dynamic")。
                          具体的な構図指示に変換して追加する。

        Returns:
            APIに送信する完成プロンプト文字列。
        """
        # Resolve mood and camera_angle modifiers
        mood_modifier = self._MOOD_INSTRUCTIONS.get(mood or "", "")
        angle_instruction = self._CAMERA_ANGLE_INSTRUCTIONS.get(
            camera_angle or "", ""
        )

        # Build supplemental context string
        extra_parts: list[str] = []
        if angle_instruction:
            extra_parts.append(angle_instruction)
        if mood_modifier:
            extra_parts.append(mood_modifier)
        extra_context = (". " + ", ".join(extra_parts)) if extra_parts else ""

        # Physical surface reminder — always included for non-zone modes
        surface_note = (
            "This image will be projected onto a long narrow dining counter surface "
            "(5520x1200px, 4.6:1 ultra-wide ratio). "
            "Design all visual elements to work beautifully across this extreme horizontal format."
        )

        if projection_mode == "zone":
            angle_note = angle_instruction or "Top-down aerial view looking straight down"
            mood_note = f", {mood_modifier}" if mood_modifier else ""
            return (
                f"{angle_note} at a single dining plate area. "
                f"Bird's-eye view composition, no horizon, no sky{mood_note}. "
                f"Scene content: {base_prompt}"
            )

        if projection_mode == "custom" and target_zones:
            # Parse selected zone numbers (1-based, 1-4)
            selected = sorted(
                {int(z.strip()) for z in target_zones.split(",") if z.strip().isdigit()}
            )
            if not selected:
                selected = [1, 2, 3, 4]

            all_zones = {1, 2, 3, 4}
            unused = sorted(all_zones - set(selected))

            unused_label = ", ".join(str(z) for z in unused) if unused else "none"
            selected_label = ", ".join(str(z) for z in selected)

            return (
                f"Top-down aerial view looking straight down, bird's-eye perspective. "
                f"Generate an image divided into exactly 4 equal vertical columns from left to right. "
                f"This represents a long dining counter divided into 4 projection zones "
                f"(5520x1200px total, 4.6:1 ultra-wide). "
                f"Zone column{'s' if len(unused) != 1 else ''} {unused_label} "
                f"must be COMPLETELY FILLED with solid black (#000000), "
                f"with absolutely no content, no texture, no gradients - pure black. "
                f"Zone column{'s' if len(selected) != 1 else ''} {selected_label} "
                f"should contain the visual content. "
                f"All content should be concentrated in a narrow horizontal band across the center. "
                f"{surface_note}{extra_context}. "
                f"Content for the active zones: {base_prompt}"
            )

        # unified (default) and seat mode — seat mode generates the same image,
        # then post-processing handles tiling at the system level.
        return (
            f"{base_prompt}. "
            f"Ultra-wide panoramic horizontal composition, top-down aerial view{extra_context}. "
            f"21:9 ultrawide cinematic format, 4K quality"
        )

    def _postprocess_from_pil(
        self,
        pil_image: "_PILImage.Image",
        output_path: str,
        aspect_ratio: str,
        projection_mode: str = "unified",
        target_zones: Optional[str] = None,
    ) -> None:
        """Post-process a PIL Image object to exact table dimensions and save as JPEG.

        Accepts an in-memory PIL Image directly, eliminating the disk write/read
        round-trip that ``_postprocess_image`` requires.

        Opt-3: For unified and zone modes, _fit_to_canvas already returns an image
        of the exact target size, so we save it directly without creating an
        intermediate black canvas and pasting.  This eliminates one full-size
        allocation + copy per image.

        Each mode:
          - unified: crop-to-fill 5520x1200 and save directly.
          - zone   : crop-to-fill 1380x1200 and save directly.
          - custom : crop-to-fill into selected zones and composite onto a
                     5520x1200 all-black canvas; unselected zones stay black.

        Args:
            pil_image: In-memory source PIL Image.
            output_path: Destination file path (extension should be .jpg).
            aspect_ratio: Job aspect ratio string.
            projection_mode: Projection mode ("unified", "zone", "custom").
            target_zones: Zone spec for custom mode (e.g. "2,3").
        """
        img = pil_image
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return

        if projection_mode == "custom" and target_zones:
            zones = sorted(
                [int(z.strip()) for z in target_zones.split(",") if z.strip().isdigit()]
            )
            if not zones:
                zones = [1, 2, 3, 4]

            content_width = TABLE_ZONE_WIDTH * len(zones)
            content_height = TABLE_FULL_HEIGHT

            content_img = _fit_to_canvas(img, content_width, content_height)

            canvas = _PILImage.new("RGB", (TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT), (0, 0, 0))
            for i, zone_num in enumerate(zones):
                src_x = i * TABLE_ZONE_WIDTH
                chunk = content_img.crop(
                    (src_x, 0, src_x + TABLE_ZONE_WIDTH, content_height)
                )
                dest_x = (zone_num - 1) * TABLE_ZONE_WIDTH
                canvas.paste(chunk, (dest_x, 0))

            canvas.save(output_path, format="JPEG", quality=85)
            print(
                f"[ImageGen] Post-processed custom zones {zones} on "
                f"{TABLE_FULL_WIDTH}x{TABLE_FULL_HEIGHT} black canvas: {output_path}"
            )

        elif projection_mode == "zone":
            # Opt-3: _fit_to_canvas returns exact target size; save directly
            fitted = _fit_to_canvas(img, TABLE_ZONE_WIDTH, TABLE_FULL_HEIGHT)
            fitted.save(output_path, format="JPEG", quality=85)
            print(
                f"[ImageGen] Post-processed zone {TABLE_ZONE_WIDTH}x{TABLE_FULL_HEIGHT}: {output_path}"
            )

        elif projection_mode == "seat":
            seat_img = _fit_to_canvas(img, TABLE_SEAT_WIDTH, TABLE_FULL_HEIGHT)
            canvas = _PILImage.new("RGB", (TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT), (0, 0, 0))
            for i in range(TABLE_SEAT_COUNT):
                canvas.paste(seat_img, (i * TABLE_SEAT_WIDTH, 0))
            canvas.save(output_path, format="JPEG", quality=85)
            print(
                f"[ImageGen] Post-processed seat 690x1200 tiled x8 on 5520x1200: {output_path}"
            )

        else:
            # Opt-3: Unified (default): crop-to-fill 5520x1200, save directly
            fitted = _fit_to_canvas(img, TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT)
            print(
                f"[ImageGen] Post-process: {orig_w}x{orig_h} -> {TABLE_FULL_WIDTH}x{TABLE_FULL_HEIGHT} "
                f"(keeping {min(100, round(TABLE_FULL_HEIGHT / orig_h * orig_w / TABLE_FULL_WIDTH * 100))}% of original content)"
            )
            fitted.save(output_path, format="JPEG", quality=85)
            print(
                f"[ImageGen] Post-processed unified {TABLE_FULL_WIDTH}x{TABLE_FULL_HEIGHT}: {output_path}"
            )

    def _postprocess_image(
        self,
        image_path: str,
        aspect_ratio: str,
        projection_mode: str = "unified",
        target_zones: Optional[str] = None,
    ) -> None:
        """生成画像を物理テーブル寸法に合わせてブラックキャンバス方式で変換する。

        各モードの動作:
          - unified: 5520x1200 の黒キャンバスに画像をクロップ・フィル配置。
          - zone   : 1380x1200 の黒キャンバスに画像をクロップ・フィル配置。
          - custom : 選択ゾーン分の領域にクロップ・フィルした後、
                     5520x1200 の全黒キャンバスの正しいゾーン位置に貼り付け。
                     未選択ゾーンは黒のまま。

        Args:
            image_path: 処理対象の画像ファイルパス。
            aspect_ratio: ジョブのアスペクト比文字列。
            projection_mode: 投影モード ("unified", "zone", "custom")。
            target_zones: カスタムモード時のゾーン指定 (例: "2,3")。
        """
        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            print(f"[ImageGen] Post-process skipped: empty or missing file {image_path}")
            return

        try:
            img = _PILImage.open(image_path)
        except Exception as e:
            print(f"[ImageGen] Cannot open image for post-processing: {e}")
            return

        self._postprocess_from_pil(img, image_path, aspect_ratio, projection_mode, target_zones)

    def _save_metadata(self, job: ImageGenerationJob, model: str) -> None:
        """メタデータJSONをJPGの隣に保存"""
        output = Path(job.output_path)
        meta_path = output.with_suffix(".json")

        # Resolve target dimensions for this job
        if job.projection_mode == "unified" or job.aspect_ratio == "21:9":
            target_w, target_h = TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT
        elif job.projection_mode == "zone":
            target_w, target_h = TABLE_ZONE_WIDTH, TABLE_FULL_HEIGHT
        elif job.projection_mode == "custom" and job.target_zones:
            zone_count = len([z for z in job.target_zones.split(",") if z.strip()])
            target_w = TABLE_ZONE_WIDTH * zone_count
            target_h = TABLE_FULL_HEIGHT
        elif job.projection_mode == "seat":
            target_w, target_h = TABLE_SEAT_WIDTH, TABLE_FULL_HEIGHT
        else:
            target_w, target_h = TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT

        metadata = {
            "job_id": job.job_id,
            "scene_id": job.scene_id,
            "prompt": job.prompt,
            "provider": job.provider.value,
            "model": model,
            "aspect_ratio": job.aspect_ratio,
            "projection_mode": job.projection_mode,
            "target_zones": job.target_zones,
            "preview_only": job.preview_only,
            "target_dimensions": {
                "width": target_w,
                "height": target_h,
                "aspect_ratio_float": round(target_w / target_h, 4),
            },
            "table_physical_mm": {
                "width": 8120,
                "height": 600,
            },
            "status": "complete",
            "generated_at": time.time(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _create_template_image(
        self,
        projection_mode: str = "unified",
        target_zones: Optional[str] = None,
    ) -> "_PILImage.Image":
        """Build a spatial layout guide image to anchor Gemini's generation.

        The template is drawn at 1456x316 px (= 1/3.8 of the real 5520x1200
        table canvas).  It communicates to the AI:

        - The extreme 4.6:1 wide-format shape.
        - The four zone columns and their dividers.
        - Plate positions (two circles per zone) at the bottom edge.
        - Which zones are active (bright) vs. inactive (solid black) when
          ``projection_mode == "custom"``.
        - A rectangular content-area border slightly inset from the edges.

        Callers are responsible for caching the result (including JPEG bytes)
        via ``self._template_cache``.  This method always builds a fresh Image
        and never touches the cache itself (Change 5).

        Opt-2: Uses module-level cached font via _get_template_font().

        Args:
            projection_mode: "unified", "zone", or "custom".
            target_zones: Active zone numbers for custom mode (e.g. "2,3").

        Returns:
            A PIL Image object in RGB mode.  The caller is responsible for
            encoding it and storing ``(image, bytes)`` in ``_template_cache``.
        """
        from PIL import ImageDraw

        # Template dimensions -- scaled down ~1/3.8 from real 5520x1200
        TMPL_W = 1456
        TMPL_H = 316
        ZONE_W = TMPL_W // 4  # 364 px per zone

        # Determine which zones are active (1-indexed, 1-4)
        if projection_mode == "custom" and target_zones:
            active_zones = sorted(
                {int(z.strip()) for z in target_zones.split(",") if z.strip().isdigit()}
            )
            if not active_zones:
                active_zones = [1, 2, 3, 4]
        else:
            active_zones = [1, 2, 3, 4]

        # Colours
        COL_BG_ACTIVE   = (26, 26, 26)    # dark gray -- table surface
        COL_BG_INACTIVE = (0, 0, 0)        # pure black -- unlit zones
        COL_DIVIDER     = (200, 200, 200)  # white-ish zone dividers
        COL_BORDER      = (255, 220, 50)   # golden content-area border
        COL_BOTTOM_BAND = (40, 40, 40)     # slightly lighter bottom edge
        COL_PLATE       = (180, 180, 180)  # plate circle outline
        COL_LABEL       = (220, 220, 220)  # zone label text

        img = _PILImage.new("RGB", (TMPL_W, TMPL_H), COL_BG_INACTIVE)
        draw = ImageDraw.Draw(img)

        # --- Per-zone background fill ---
        bottom_band_h = TMPL_H // 5  # ~63 px bottom band
        for zone_idx in range(4):
            zone_num = zone_idx + 1
            x0 = zone_idx * ZONE_W
            x1 = x0 + ZONE_W

            if zone_num in active_zones:
                draw.rectangle([x0, 0, x1, TMPL_H], fill=COL_BG_ACTIVE)
                # Slightly lighter bottom band for guest/plate area
                draw.rectangle(
                    [x0, TMPL_H - bottom_band_h, x1, TMPL_H],
                    fill=COL_BOTTOM_BAND,
                )

        # --- Zone dividers (dashed vertical lines) ---
        dash_on = 8
        dash_off = 5
        for zone_idx in range(1, 4):
            x = zone_idx * ZONE_W
            y = 0
            while y < TMPL_H:
                y_end = min(y + dash_on, TMPL_H)
                draw.line([(x, y), (x, y_end)], fill=COL_DIVIDER, width=1)
                y += dash_on + dash_off

        # --- Plate circles (2 per active zone, centred horizontally) ---
        plate_r = 12          # radius in template pixels
        plate_y_centre = TMPL_H - bottom_band_h // 2
        plate_spacing = ZONE_W // 3  # distance between the two plate centres

        for zone_idx in range(4):
            zone_num = zone_idx + 1
            if zone_num not in active_zones:
                continue
            zone_cx = zone_idx * ZONE_W + ZONE_W // 2
            for offset in (-plate_spacing // 2, plate_spacing // 2):
                cx = zone_cx + offset
                draw.ellipse(
                    [cx - plate_r, plate_y_centre - plate_r,
                     cx + plate_r, plate_y_centre + plate_r],
                    outline=COL_PLATE,
                    width=2,
                )

        # --- Content-area border (inset 6 px from edges, stops above bottom band) ---
        border_inset = 6
        border_bottom = TMPL_H - bottom_band_h - border_inset
        draw.rectangle(
            [border_inset, border_inset, TMPL_W - border_inset, border_bottom],
            outline=COL_BORDER,
            width=2,
        )

        # --- Zone labels ("Z1" ... "Z4") near top of each zone ---
        # Opt-2: Use module-level cached font
        label_y = border_inset + 6
        font = _get_template_font()

        for zone_idx in range(4):
            zone_num = zone_idx + 1
            if zone_num not in active_zones:
                continue
            label = f"Z{zone_num}"
            label_x = zone_idx * ZONE_W + 8
            draw.text((label_x, label_y), label, fill=COL_LABEL, font=font)

        return img

    async def _generate_gemini(self, job: ImageGenerationJob):
        """Nano Banana -- Gemini 2.0 Flash Image API による画像生成"""
        import time as _t
        t_total_start = _t.monotonic()

        try:
            from google.genai import types
        except ImportError:
            print("[ImageGen] google-genai SDK not installed. Run: pip install google-genai")
            await self._create_placeholder(job)
            return

        t0 = _t.monotonic()
        try:
            client = self._get_gemini_client()
        except RuntimeError:
            await self._create_placeholder(job)
            return
        t_client = _t.monotonic() - t0

        # gemini-2.5-flash-image: Nano Banana (旧 gemini-2.0-flash-exp-image-generation は廃止)
        model = "gemini-2.5-flash-image"
        base_prompt = self._build_aspect_prompt(
            job.prompt, job.aspect_ratio, job.projection_mode, job.target_zones,
            mood=job.mood, camera_angle=job.camera_angle,
        )

        print(f"[ImageGen] Gemini model: {model}")
        print("[ImageGen] Using template-guided generation")

        # Build the template guide image and encode to JPEG bytes (Change 5: cache both)
        # Opt-6: Template quality=60 (layout guide for AI, not final output)
        t0 = _t.monotonic()
        cache_key = (job.projection_mode, job.target_zones)
        if cache_key in self._template_cache:
            template_img, template_bytes = self._template_cache[cache_key]
        else:
            template_img = self._create_template_image(job.projection_mode, job.target_zones)
            template_buf = io.BytesIO()
            template_img.save(template_buf, format="JPEG", quality=60)
            template_buf.seek(0)
            template_bytes = template_buf.read()
            self._template_cache[cache_key] = (template_img, template_bytes)
        t_template = _t.monotonic() - t0

        # Compose the multimodal prompt text
        if job.projection_mode == "custom" and job.target_zones:
            inactive_note = (
                "\n- 黒い部分はプロジェクションされません。"
                "コンテンツは明るいゾーンにのみ生成してください"
            )
        else:
            inactive_note = ""

        prompt_text = (
            "以下のテンプレート画像は、テーブル投影用の映像フレームのレイアウトを示しています。\n"
            "このフレームの枠内に収まるように、以下のテーマで映像を生成してください。\n\n"
            "- アスペクト比: 超ワイド（約4.6:1）を必ず守ること\n"
            "- 下部の小さな円はお皿の位置です。お皿の上に重要なビジュアル要素を配置しないでください\n"
            "- ゾーン分割線は参考用です。映像は全体で一つのシームレスなパノラマにしてください\n"
            "- 真上から見下ろした鳥瞰図の構図で生成してください"
            f"{inactive_note}\n\n"
            f"テーマ: {base_prompt}"
        )

        print(f"[TIMING] scene={job.scene_id} | client={t_client*1000:.0f}ms | template={t_template*1000:.0f}ms | payload={len(template_bytes)}bytes")

        # Run the synchronous Gemini SDK call in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()

        def _call_api():
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=template_bytes, mime_type="image/jpeg"),
                    prompt_text,
                ],
                config=types.GenerateContentConfig(
                    # Opt-4: Request IMAGE only -- no TEXT generation overhead.
                    # The model may still return a text part but won't be prompted
                    # to generate a lengthy textual description alongside the image.
                    response_modalities=["IMAGE"],
                    # Opt-10: Omit temperature/top_p/top_k -- defaults are fine
                    # for image generation and avoids unnecessary server-side
                    # text-sampling configuration.
                ),
            )
            return response

        t0 = _t.monotonic()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(_API_THREAD_POOL, _call_api),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Gemini API call timed out after 60 seconds")
        t_api = _t.monotonic() - t0

        # Extract image bytes from response parts
        t0 = _t.monotonic()
        image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break
        t_extract = _t.monotonic() - t0

        if image_data is None:
            raise RuntimeError("Gemini returned no image data in the response")

        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Opt-5 + Opt-9: Run post-processing and metadata save in parallel
        # using _API_THREAD_POOL consistently.
        t0 = _t.monotonic()
        pil_image = _PILImage.open(io.BytesIO(image_data))

        postprocess_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(
                self._postprocess_from_pil,
                pil_image,
                job.output_path,
                job.aspect_ratio,
                job.projection_mode,
                job.target_zones,
            ),
        )
        metadata_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(self._save_metadata, job, model),
        )
        await asyncio.gather(postprocess_future, metadata_future)
        t_save = _t.monotonic() - t0

        t_total = _t.monotonic() - t_total_start
        img_size_kb = len(image_data) / 1024
        print(
            f"[TIMING] scene={job.scene_id} GEMINI DONE | "
            f"api={t_api*1000:.0f}ms | extract={t_extract*1000:.1f}ms | "
            f"save+meta={t_save*1000:.0f}ms | "
            f"TOTAL={t_total*1000:.0f}ms | img={img_size_kb:.0f}KB"
        )

    async def _generate_gemini_pro(self, job: ImageGenerationJob):
        """Nano Banana Pro -- Gemini Pro Image API による高品質画像生成"""
        import time as _t
        t_total_start = _t.monotonic()

        try:
            from google.genai import types
        except ImportError:
            print("[ImageGen] google-genai SDK not installed. Run: pip install google-genai")
            await self._create_placeholder(job)
            return

        t0 = _t.monotonic()
        try:
            client = self._get_gemini_client()
        except RuntimeError:
            await self._create_placeholder(job)
            return
        t_client = _t.monotonic() - t0

        # gemini-3-pro-image-preview: Nano Banana Pro (高品質画像生成モデル)
        # 旧 gemini-2.0-flash-exp-image-generation は廃止済み
        model = "gemini-3-pro-image-preview"
        base_prompt = self._build_aspect_prompt(
            job.prompt, job.aspect_ratio, job.projection_mode, job.target_zones,
            mood=job.mood, camera_angle=job.camera_angle,
        )

        print(f"[ImageGen] Gemini Pro model: {model}")
        print("[ImageGen] Using template-guided generation")

        # Build the template guide image and encode to JPEG bytes (cache both)
        # Opt-6: Template quality=60 (layout guide for AI, not final output)
        t0 = _t.monotonic()
        cache_key = (job.projection_mode, job.target_zones)
        if cache_key in self._template_cache:
            template_img, template_bytes = self._template_cache[cache_key]
        else:
            template_img = self._create_template_image(job.projection_mode, job.target_zones)
            template_buf = io.BytesIO()
            template_img.save(template_buf, format="JPEG", quality=60)
            template_buf.seek(0)
            template_bytes = template_buf.read()
            self._template_cache[cache_key] = (template_img, template_bytes)
        t_template = _t.monotonic() - t0

        # Compose the multimodal prompt text
        if job.projection_mode == "custom" and job.target_zones:
            inactive_note = (
                "\n- 黒い部分はプロジェクションされません。"
                "コンテンツは明るいゾーンにのみ生成してください"
            )
        else:
            inactive_note = ""

        prompt_text = (
            "以下のテンプレート画像は、テーブル投影用の映像フレームのレイアウトを示しています。\n"
            "このフレームの枠内に収まるように、以下のテーマで映像を生成してください。\n\n"
            "- アスペクト比: 超ワイド（約4.6:1）を必ず守ること\n"
            "- 下部の小さな円はお皿の位置です。お皿の上に重要なビジュアル要素を配置しないでください\n"
            "- ゾーン分割線は参考用です。映像は全体で一つのシームレスなパノラマにしてください\n"
            "- 真上から見下ろした鳥瞰図の構図で生成してください"
            f"{inactive_note}\n\n"
            f"テーマ: {base_prompt}"
        )

        print(f"[TIMING] scene={job.scene_id} GEMINI-PRO | client={t_client*1000:.0f}ms | template={t_template*1000:.0f}ms | payload={len(template_bytes)}bytes")

        loop = asyncio.get_running_loop()

        def _call_api():
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=template_bytes, mime_type="image/jpeg"),
                    prompt_text,
                ],
                config=types.GenerateContentConfig(
                    # Opt-4: Request IMAGE only -- no TEXT generation overhead
                    response_modalities=["IMAGE"],
                    # Opt-10: Omit temperature/top_p/top_k -- defaults are fine
                ),
            )
            return response

        t0 = _t.monotonic()
        # wrap API call with a 60-second timeout
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(_API_THREAD_POOL, _call_api),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Gemini Pro API call timed out after 60 seconds")
        t_api = _t.monotonic() - t0

        # Extract image bytes from response parts
        t0 = _t.monotonic()
        image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break
        t_extract = _t.monotonic() - t0

        if image_data is None:
            raise RuntimeError("Gemini Pro returned no image data in the response")

        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Opt-5 + Opt-9: Run post-processing and metadata save in parallel
        t0 = _t.monotonic()
        pil_image = _PILImage.open(io.BytesIO(image_data))

        postprocess_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(
                self._postprocess_from_pil,
                pil_image,
                job.output_path,
                job.aspect_ratio,
                job.projection_mode,
                job.target_zones,
            ),
        )
        metadata_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(self._save_metadata, job, model),
        )
        await asyncio.gather(postprocess_future, metadata_future)
        t_save = _t.monotonic() - t0

        t_total = _t.monotonic() - t_total_start
        img_size_kb = len(image_data) / 1024
        print(
            f"[TIMING] scene={job.scene_id} GEMINI-PRO DONE | "
            f"api={t_api*1000:.0f}ms | extract={t_extract*1000:.1f}ms | "
            f"save+meta={t_save*1000:.0f}ms | "
            f"TOTAL={t_total*1000:.0f}ms | img={img_size_kb:.0f}KB"
        )

    async def _generate_imagen(self, job: ImageGenerationJob):
        """Imagen 4 Fast -- Google Imagen 4 Fast API による高速画像生成 (3-5s)"""
        import time as _t
        t_total_start = _t.monotonic()

        try:
            from google.genai import types
        except ImportError:
            print("[ImageGen] google-genai SDK not installed. Run: pip install google-genai")
            await self._create_placeholder(job)
            return

        t0 = _t.monotonic()
        try:
            client = self._get_gemini_client()
        except RuntimeError:
            await self._create_placeholder(job)
            return
        t_client = _t.monotonic() - t0

        model = "imagen-4.0-fast-generate-001"
        imagen_aspect_ratio = "16:9"

        t0 = _t.monotonic()
        prompt = self._build_aspect_prompt(
            job.prompt, job.aspect_ratio, job.projection_mode, job.target_zones,
            mood=job.mood, camera_angle=job.camera_angle,
        )
        t_prompt = _t.monotonic() - t0

        print(f"[ImageGen] Imagen model: {model} | API aspect ratio: {imagen_aspect_ratio}")
        print(f"[TIMING] scene={job.scene_id} | client={t_client*1000:.0f}ms | prompt_build={t_prompt*1000:.1f}ms")

        loop = asyncio.get_running_loop()

        def _call_api():
            response = client.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=imagen_aspect_ratio,
                    output_mime_type="image/jpeg",
                    # Opt-7: quality=80 for preview (saves ~15% transfer bytes vs 85)
                    output_compression_quality=80,
                ),
            )
            return response

        t0 = _t.monotonic()
        # Change 6: wrap API call with a 60-second timeout
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(_API_THREAD_POOL, _call_api),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Imagen API call timed out after 60 seconds")
        t_api = _t.monotonic() - t0

        t0 = _t.monotonic()
        generated = response.generated_images
        if not generated:
            raise RuntimeError("Imagen returned no generated images in the response")

        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        image_bytes = generated[0].image.image_bytes
        t_extract = _t.monotonic() - t0

        # Opt-5 + Opt-9: Run post-processing and metadata save in parallel
        t0 = _t.monotonic()
        pil_image = _PILImage.open(io.BytesIO(image_bytes))

        postprocess_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(
                self._postprocess_from_pil,
                pil_image,
                job.output_path,
                job.aspect_ratio,
                job.projection_mode,
                job.target_zones,
            ),
        )
        metadata_future = loop.run_in_executor(
            _API_THREAD_POOL,
            functools.partial(self._save_metadata, job, model),
        )
        await asyncio.gather(postprocess_future, metadata_future)
        t_save = _t.monotonic() - t0

        t_total = _t.monotonic() - t_total_start
        img_size_kb = len(image_bytes) / 1024
        print(
            f"[TIMING] scene={job.scene_id} IMAGEN DONE | "
            f"api={t_api*1000:.0f}ms | extract={t_extract*1000:.1f}ms | "
            f"save+meta={t_save*1000:.0f}ms | "
            f"TOTAL={t_total*1000:.0f}ms | img={img_size_kb:.0f}KB"
        )

    async def _generate_flux(self, job: ImageGenerationJob):
        """Flux.1 API -- 画像生成"""
        if not self.flux_api_key:
            await self._create_placeholder(job)
            return

        # --- Flux API呼び出し（APIキー取得後に有効化） ---
        # import httpx
        # async with httpx.AsyncClient(timeout=120) as client:
        #     response = await client.post(
        #         "https://api.bfl.ml/v1/flux-pro-1.1",
        #         headers={
        #             "x-key": self.flux_api_key,
        #             "Content-Type": "application/json",
        #         },
        #         json={
        #             "prompt": job.prompt,
        #             "width": 1344 if job.aspect_ratio == "21:9" else 1024,
        #             "height": 576 if job.aspect_ratio == "21:9" else 1024,
        #         },
        #     )
        #     task_id = response.json()["id"]
        #
        #     # ポーリング
        #     while True:
        #         status_resp = await client.get(
        #             f"https://api.bfl.ml/v1/get_result?id={task_id}",
        #             headers={"x-key": self.flux_api_key},
        #         )
        #         result = status_resp.json()
        #         if result["status"] == "Ready":
        #             image_url = result["result"]["sample"]
        #             break
        #         elif result["status"] in ("Error", "Content Moderated"):
        #             raise Exception(f"Flux failed: {result.get('status')}")
        #         await asyncio.sleep(3)
        #
        #     img_resp = await client.get(image_url)
        #     Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)
        #     with open(job.output_path, "wb") as f:
        #         f.write(img_resp.content)

        await self._create_placeholder(job)

    async def _generate_runway(self, job: ImageGenerationJob):
        """Runway Gen-4 Image API -- 画像生成"""
        if not self.runway_api_key:
            await self._create_placeholder(job)
            return

        # --- Runway Image API呼び出し（APIキー取得後に有効化） ---
        # import httpx
        # async with httpx.AsyncClient(timeout=120) as client:
        #     response = await client.post(
        #         "https://api.dev.runwayml.com/v1/text_to_image",
        #         headers={"Authorization": f"Bearer {self.runway_api_key}"},
        #         json={
        #             "promptText": job.prompt,
        #             "model": "gen4_image",
        #             "ratio": job.aspect_ratio,
        #         },
        #     )
        #     task_id = response.json()["id"]
        #
        #     while True:
        #         status_resp = await client.get(
        #             f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
        #             headers={"Authorization": f"Bearer {self.runway_api_key}"},
        #         )
        #         result = status_resp.json()
        #         if result["status"] == "SUCCEEDED":
        #             image_url = result["output"][0]
        #             break
        #         elif result["status"] == "FAILED":
        #             raise Exception(f"Runway image failed: {result.get('error')}")
        #         await asyncio.sleep(3)
        #
        #     img_resp = await client.get(image_url)
        #     Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)
        #     with open(job.output_path, "wb") as f:
        #         f.write(img_resp.content)

        await self._create_placeholder(job)

    async def _create_placeholder(self, job: ImageGenerationJob):
        """プレースホルダ作成（API未設定時のデモ用）"""
        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if job.projection_mode == "unified" or job.aspect_ratio == "21:9":
            target_w, target_h = TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT
        elif job.projection_mode == "zone":
            target_w, target_h = TABLE_ZONE_WIDTH, TABLE_FULL_HEIGHT
        elif job.projection_mode == "custom" and job.target_zones:
            zone_count = len([z for z in job.target_zones.split(",") if z.strip()])
            target_w = TABLE_ZONE_WIDTH * zone_count
            target_h = TABLE_FULL_HEIGHT
        else:
            target_w, target_h = TABLE_FULL_WIDTH, TABLE_FULL_HEIGHT

        meta_path = output.with_suffix(".json")
        metadata = {
            "job_id": job.job_id,
            "scene_id": job.scene_id,
            "prompt": job.prompt,
            "provider": job.provider.value,
            "aspect_ratio": job.aspect_ratio,
            "projection_mode": job.projection_mode,
            "target_zones": job.target_zones,
            "target_dimensions": {
                "width": target_w,
                "height": target_h,
                "aspect_ratio_float": round(target_w / target_h, 4),
            },
            "status": "placeholder",
            "note": "APIキーを設定すると実際の画像が生成されます",
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 空のファイルを作成（TouchDesignerが参照できるように）
        output.touch()
        print(f"[ImageGen] Placeholder: {meta_path}")

    def get_job_status(self, job_id: str) -> Optional[dict]:
        job = self.jobs.get(job_id)
        return asdict(job) if job else None
