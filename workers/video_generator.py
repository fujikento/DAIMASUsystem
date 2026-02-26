"""
AI映像生成ワーカー

2つの生成モード:
  unified  — 全テーブル統一演出 (21:9 × 2セグメント → 5520x1200 合成)
  zone     — 区画別演出 (1:1 → 1380x1200 クロップ)

使い方:
    # 統一モード（全テーブル一体）
    python workers/video_generator.py generate --theme ocean --course appetizer --mode unified

    # 区画モード（個別テーブル）
    python workers/video_generator.py generate --theme ocean --course appetizer --mode zone --zone 2

    # テーマ全コース一括生成
    python workers/video_generator.py batch --day wednesday --mode unified

    # プロンプト確認
    python workers/video_generator.py prompts --mode unified
"""

import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class GenerationStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPOSITING = "compositing"
    COMPLETE = "complete"
    FAILED = "failed"


class VideoProvider(str, Enum):
    RUNWAY = "runway"
    KLING = "kling"
    PIKA = "pika"


class GenerationMode(str, Enum):
    UNIFIED = "unified"   # 全テーブル統一 (21:9 × 2 → 5520x1200)
    ZONE = "zone"         # 区画別 (1:1 → 1380x1200)


# ─── テーブル物理仕様 ─────────────────────────────────────────────
TABLE_FULL_WIDTH = 5520    # 3PJ実効幅 (px)
TABLE_HEIGHT = 1200        # WUXGA高さ
ZONE_COUNT = 4
ZONE_WIDTH = TABLE_FULL_WIDTH // ZONE_COUNT   # 1380px
BLEND_OVERLAP = 120        # エッジブレンド重なり

# ─── 生成仕様 ─────────────────────────────────────────────────────
# 統一モード: Runway 21:9 → 4Kアップスケール 3840x1080
# 2セグメント(L/R)を20%オーバーラップで合成 → 5520x1200
UNIFIED_SEGMENT_W = 3840
UNIFIED_SEGMENT_H = 1080
UNIFIED_OVERLAP_RATIO = 0.20  # 20% overlap

# 区画モード: 1:1 → 4Kアップスケール 2160x2160 → crop 1380x1200
ZONE_NATIVE_SIZE = 2160


@dataclass
class GenerationJob:
    job_id: str
    prompt: str
    provider: VideoProvider = VideoProvider.RUNWAY
    mode: GenerationMode = GenerationMode.UNIFIED
    segment: Optional[str] = None   # "left" / "right" (統一モード時)
    zone_id: Optional[int] = None   # 1-4 (区画モード時)
    status: GenerationStatus = GenerationStatus.QUEUED
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: int = 10
    aspect_ratio: str = "21:9"
    resolution: str = "4k"
    seed_image_path: Optional[str] = None  # シード画像パス (image-to-video用)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# ─── プロンプトテンプレート ────────────────────────────────────────

# 統一モード共通プレフィックス（21:9ワイド構図に最適化）
_UNIFIED_PREFIX = (
    "Ultra-wide panoramic top-down aerial view looking straight down, "
    "horizontal cinematic composition, no horizon line, "
    "designed for projection onto a long table surface, "
    "seamless horizontal flow, 21:9 ultrawide, 4K quality"
)

# 区画モード共通プレフィックス（1:1正方形構図に最適化）
_ZONE_PREFIX = (
    "Overhead bird's-eye view looking straight down at a square surface, "
    "centered intimate composition, no horizon line, "
    "designed for projection onto a dinner table, "
    "1:1 square format, 4K quality"
)

# テーマ別映像プロンプト
# 各コースに unified / zone 2パターンのプロンプトを定義
THEME_PROMPTS = {
    "zen": {
        "welcome": {
            "unified": "Zen garden with raked sand patterns flowing left to right across the entire surface, cherry blossom petals drifting horizontally, ink wash painting slowly appearing, meditative and serene",
            "zone": "Zen garden with circular raked sand patterns, cherry blossom petals gently falling onto the surface, a single bonsai shadow, ink wash aesthetic",
        },
        "appetizer": {
            "unified": "Fresh sashimi arrangement with flowing water patterns streaming horizontally, miniature landscapes appearing along the surface, bamboo leaves and zen stones, Japanese aesthetic",
            "zone": "Delicate sashimi arrangement on slate, surrounded by gentle water ripples, a single zen stone, bamboo leaf shadows, intimate Japanese aesthetic",
        },
        "soup": {
            "unified": "Steam transforming into misty mountain panorama flowing across the surface, autumn foliage and temple silhouettes, traditional Japanese scenery unfolding left to right",
            "zone": "Steam rising and forming into a miniature mountain landscape, autumn maple leaves floating down, peaceful mist, temple bell impression",
        },
        "main": {
            "unified": "Dynamic ink brush dragon painting itself across the entire surface left to right, transforming into elegant ocean waves, bold calligraphy strokes sweeping horizontally",
            "zone": "Bold ink brush strokes painting a dragon coiling on the surface, transforming into waves, Japanese calligraphy appearing, dramatic and artistic",
        },
        "dessert": {
            "unified": "Massive cherry blossom storm sweeping across the full width, petals forming congratulatory kanji, golden particles flowing horizontally, celebration climax",
            "zone": "Cherry blossom whirlwind centered on the surface, petals forming a congratulatory kanji character, golden light particles, celebration mood",
        },
    },
    "fire": {
        "welcome": {
            "unified": "Embers and sparks igniting into flame patterns flowing left to right, warm amber and red tones spreading across the surface, dramatic theatrical lighting",
            "zone": "Embers slowly igniting into elegant circular flame patterns, warm amber and deep red tones, dramatic intimate lighting",
        },
        "appetizer": {
            "unified": "Volcanic landscape with lava rivers flowing horizontally, creating intricate branching patterns, ember particles drifting across the panorama",
            "zone": "Volcanic surface with lava creating intricate circular patterns, ember particles floating upward, warm passionate glow",
        },
        "soup": {
            "unified": "Hundreds of candlelight flames dancing in formation across the full width, creating mesmerizing wave patterns, golden glow spreading horizontally",
            "zone": "Candlelight flames dancing in a circular formation, creating mesmerizing patterns, intimate romantic atmosphere, warm golden glow",
        },
        "main": {
            "unified": "Epic fire burst erupting from center spreading to both edges, phoenix wings unfurling across the full width, deep reds and oranges, spectacular and powerful",
            "zone": "Dramatic fire burst erupting from center, phoenix rising from flames, epic and powerful, deep reds and oranges swirling",
        },
        "dessert": {
            "unified": "Fireworks display cascading across the entire surface, sparkler trails writing patterns from left to right, grand celebration finale with fire and light",
            "zone": "Fireworks exploding outward from center, sparkler trails writing patterns, celebration with fire and light, spectacular finale",
        },
    },
    "ocean": {
        "welcome": {
            "unified": "Crystal clear ocean water with gentle waves flowing left to right, sunlight caustic patterns on sandy bottom, tropical fish schools swimming across the panorama",
            "zone": "Crystal clear ocean water with gentle circular ripples, sunlight caustic patterns on sandy bottom, a few tropical fish swimming",
        },
        "appetizer": {
            "unified": "Coral reef panorama stretching across the surface, colorful tropical fish migrating horizontally, sea anemones and bioluminescent plankton trails",
            "zone": "Coral reef ecosystem from above, colorful tropical fish, sea anemones swaying gently, bioluminescent plankton dots",
        },
        "soup": {
            "unified": "Deep ocean currents carrying jellyfish across the full width, bioluminescent creatures creating light trails flowing horizontally, ethereal deep blue and purple",
            "zone": "Deep ocean with jellyfish floating gracefully, bioluminescent creatures pulsing, deep blue and purple tones, ethereal atmosphere",
        },
        "main": {
            "unified": "Manta rays gliding across the panorama, whale song vibrations visualized as expanding light rings spanning the full surface, majestic underwater scene",
            "zone": "A manta ray gliding overhead casting shadow, whale song vibrations as expanding light rings, majestic and awe-inspiring",
        },
        "dessert": {
            "unified": "Ocean surface at sunset with dolphins leaping across the width, water transforming into sparkling champagne bubbles flowing horizontally, celebration",
            "zone": "Ocean surface at sunset with a dolphin leaping, water transforming into sparkling champagne bubbles, joyful celebration mood",
        },
    },
    "forest": {
        "welcome": {
            "unified": "Morning mist drifting horizontally through an ancient forest panorama, sunbeams filtering through the canopy, moss-covered stones and dewdrops spanning the surface",
            "zone": "Morning mist in an ancient forest clearing, sunbeams filtering through canopy, moss-covered stones, dewdrops on spider web",
        },
        "appetizer": {
            "unified": "Mushrooms and ferns growing in time-lapse across the full width, small forest creatures appearing and moving horizontally, enchanted forest canopy light",
            "zone": "Mushrooms growing in time-lapse, ferns unfurling, small forest creatures peeking out, dappled sunlight, enchanted atmosphere",
        },
        "soup": {
            "unified": "Gentle rain falling on leaves stretching across the panorama, ripples in forest puddles, foggy green atmosphere flowing left to right",
            "zone": "Gentle rain falling on broad leaves, creating ripples in a forest puddle, foggy green atmosphere, meditative calm",
        },
        "main": {
            "unified": "Thousands of fireflies emerging at twilight, illuminating a row of ancient trees spanning the full width, magical Ghibli-inspired forest",
            "zone": "Fireflies emerging at twilight, illuminating an ancient tree, magical forest scene, Studio Ghibli inspired, whimsical and beautiful",
        },
        "dessert": {
            "unified": "Aurora borealis rippling across the full width above forest canopy, flowers blooming in time-lapse across the surface, magical nature celebration",
            "zone": "Aurora borealis visible through forest canopy, flowers blooming in time-lapse around center, magical celebration of nature",
        },
    },
    "gold": {
        "welcome": {
            "unified": "Liquid gold flowing and forming elegant Art Deco patterns across the full width, diamond dust particles drifting horizontally, opulent luxury atmosphere",
            "zone": "Liquid gold flowing and forming elegant patterns in the center, diamond dust particles, luxury and opulence, glamorous",
        },
        "appetizer": {
            "unified": "Champagne bubbles rising in golden light across the panorama, crystal reflections, Art Deco geometric patterns forming and connecting horizontally",
            "zone": "Champagne bubbles rising in golden light, crystal reflections creating rainbow spots, Art Deco geometric patterns, sophisticated",
        },
        "soup": {
            "unified": "Treasure cascading across the surface, golden light spreading from center to edges, jewels and coins flowing horizontally, rich warm tones",
            "zone": "Treasure chest opening with golden light, jewels scattering outward on the surface, rich and luxurious, warm tones",
        },
        "main": {
            "unified": "Grand chandelier crystals refracting rainbow light across the entire surface, ballroom elegance, Gatsby-era luxury panorama",
            "zone": "Chandelier crystals refracting light into rainbow patterns, ballroom elegance, Gatsby-era luxury, spectacular",
        },
        "dessert": {
            "unified": "Gold leaf confetti and diamond sparkles sweeping across the full width, champagne toast fireworks, peak luxury celebration finale",
            "zone": "Gold leaf confetti and diamond sparkles raining down, champagne toast celebration, fireworks in gold, peak luxury moment",
        },
    },
    "space": {
        "welcome": {
            "unified": "Slow drift through nebula clouds spanning the full panorama, stars appearing across the width, cosmic dust particles, deep space colors and awe",
            "zone": "Descending through nebula clouds, stars appearing one by one, cosmic dust particles swirling, deep space colors, awe-inspiring",
        },
        "appetizer": {
            "unified": "Planetary ring system stretching across the surface, asteroid field with crystalline structures, deep purple and blue cosmic panorama",
            "zone": "Planetary rings from above, asteroid field with crystalline structures, deep purple and blue tones, cosmic wonder",
        },
        "soup": {
            "unified": "Aurora borealis rippling across the entire surface from left to right, cosmic energy waves, ethereal green and purple light show",
            "zone": "Northern lights aurora rippling on the surface, cosmic energy waves pulsing, ethereal greens and purples, mesmerizing",
        },
        "main": {
            "unified": "Supernova explosion expanding from center across the full width, spiral galaxy arms forming, cosmic scale spectacle",
            "zone": "Supernova explosion in slow motion at center, spiral galaxy forming around it, cosmic scale and beauty, spectacular",
        },
        "dessert": {
            "unified": "Shooting stars streaking across the full panorama, constellation patterns forming a celebration message, cosmic fireworks grand finale",
            "zone": "Shooting stars streaking across, constellation patterns forming, cosmic fireworks display, grand finale celebration",
        },
    },
    "fairytale": {
        "welcome": {
            "unified": "Giant storybook pages turning and unfolding across the surface, illustrated castle and landscapes appearing panoramically, fairy dust trailing horizontally",
            "zone": "Storybook opening with pages turning, illustrated castle appearing, fairy dust sparkles, whimsical and magical, warm colors",
        },
        "appetizer": {
            "unified": "Enchanted garden stretching across the panorama, talking flowers and butterflies carrying tiny lanterns flying horizontally, storybook illustration style",
            "zone": "Enchanted garden with talking flowers, butterflies carrying tiny lanterns, storybook illustration style, magical",
        },
        "soup": {
            "unified": "Magical potion ingredients flowing across the surface, swirling colors connecting left to right, wizard's workshop panorama, cozy and mysterious",
            "zone": "Magical potion brewing in cauldron, swirling colors and sparkles, wizard's workshop, cozy and mysterious atmosphere",
        },
        "main": {
            "unified": "Dragon flying across the full width casting dramatic shadow, then revealing friendly smile, magical adventure panorama, epic and playful",
            "zone": "Dragon circling overhead casting shadow, then revealing friendly smile, magical adventure scene, epic and playful",
        },
        "dessert": {
            "unified": "Fairy tale castle at night with fireworks launching across the full panorama, magical creatures celebrating, happy ever after finale",
            "zone": "Fairy tale castle at night with fireworks, happy ever after scene, magical creatures celebrating, joyful ending",
        },
    },
}

# 曜日→テーママッピング
DAY_TO_THEME = {
    "monday": "zen",
    "tuesday": "fire",
    "wednesday": "ocean",
    "thursday": "forest",
    "friday": "gold",
    "saturday": "space",
    "sunday": "fairytale",
}

COURSE_ORDER = ["welcome", "appetizer", "soup", "main", "dessert"]


def _build_prompt(
    theme: str,
    course: str,
    mode: GenerationMode,
    segment: Optional[str] = None,
    extra_prompt: Optional[str] = None,
    color_tone: str = "neutral",
    brightness: str = "normal",
    animation_speed: str = "normal",
    prompt_modifier: Optional[str] = None,
) -> str:
    """モードに応じた最終プロンプトを組み立て（ステージングパラメータ対応）"""
    base = THEME_PROMPTS.get(theme, {}).get(course, {})
    # Accept both GenerationMode enum instances and raw strings
    if isinstance(mode, GenerationMode):
        mode_key = mode.value
    else:
        mode_key = str(mode)

    scene_desc = base.get(mode_key, "")
    if not scene_desc:
        raise ValueError(f"No prompt for theme={theme}, course={course}, mode={mode_key}")

    # 料理の追加プロンプトヒントがあれば付加
    if extra_prompt:
        scene_desc = f"{scene_desc}, inspired by the dish: {extra_prompt}"

    if mode == GenerationMode.UNIFIED:
        prefix = _UNIFIED_PREFIX
        if segment == "left":
            suffix = ", left portion of a continuous panoramic scene, content flows toward the right edge"
        elif segment == "right":
            suffix = ", right portion of a continuous panoramic scene, content flows from the left edge"
        else:
            suffix = ""
        prompt = f"{prefix}, {scene_desc}{suffix}"
    else:
        prompt = f"{_ZONE_PREFIX}, {scene_desc}"

    # Color tone staging modifier
    tone_map = {
        "warm": "warm golden tones, amber lighting",
        "cool": "cool blue tones, moonlit atmosphere",
        "vivid": "vibrant saturated colors, high contrast",
    }
    if color_tone and color_tone != "neutral" and color_tone in tone_map:
        prompt += f", {tone_map[color_tone]}"

    # Brightness staging modifier
    bright_map = {
        "dark": "dramatic low-key lighting, deep shadows, moody atmosphere",
        "bright": "bright ethereal lighting, luminous glow, radiant",
    }
    if brightness and brightness != "normal" and brightness in bright_map:
        prompt += f", {bright_map[brightness]}"

    # Animation speed staging modifier
    speed_map = {
        "slow": "slow graceful movement, gentle flowing motion",
        "fast": "dynamic energetic motion, rapid flowing movement",
    }
    if animation_speed and animation_speed != "normal" and animation_speed in speed_map:
        prompt += f", {speed_map[animation_speed]}"

    # Custom prompt modifier (free-text)
    if prompt_modifier:
        prompt += f", {prompt_modifier}"

    return prompt


def _get_api_key(key_name: str) -> str:
    """Get API key from database, falling back to environment variable."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from api.models.database import SessionLocal
        from api.models.schemas import AppSetting
        db = SessionLocal()
        try:
            setting = db.query(AppSetting).filter(AppSetting.key == key_name).first()
            if setting and setting.value:
                return setting.value
        finally:
            db.close()
    except Exception:
        pass
    return os.environ.get(key_name, "")


def _default_video_output_dir() -> str:
    """Return the themes content directory relative to the project root."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "touchdesigner", "content", "themes")


class VideoGeneratorService:
    """AI映像生成サービス"""

    # Runway API constants
    RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
    RUNWAY_POLL_INTERVAL = 5    # seconds between status checks
    RUNWAY_POLL_TIMEOUT = 180   # max seconds to wait for generation

    def __init__(self, output_dir: str = ""):
        if not output_dir:
            output_dir = _default_video_output_dir()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, GenerationJob] = {}
        self._job_counter = 0

        self.runway_api_key = _get_api_key("RUNWAY_API_KEY")
        self.kling_api_key = _get_api_key("KLING_API_KEY")

    def create_job(
        self,
        theme: str,
        course: str,
        mode: GenerationMode = GenerationMode.UNIFIED,
        provider: VideoProvider = VideoProvider.RUNWAY,
        segment: Optional[str] = None,
        zone_id: Optional[int] = None,
        duration_seconds: int = 10,
        extra_prompt: Optional[str] = None,
        seed_image_path: Optional[str] = None,
        color_tone: str = "neutral",
        brightness: str = "normal",
        animation_speed: str = "normal",
        prompt_modifier: Optional[str] = None,
    ) -> GenerationJob:
        """映像生成ジョブを作成"""
        self._job_counter += 1
        job_id = f"gen_{self._job_counter}_{int(time.time())}"

        prompt = _build_prompt(
            theme, course, mode, segment, extra_prompt,
            color_tone=color_tone,
            brightness=brightness,
            animation_speed=animation_speed,
            prompt_modifier=prompt_modifier,
        )

        # 出力パス
        if mode == GenerationMode.UNIFIED:
            seg_label = f"_{segment}" if segment else ""
            filename = f"{course}{seg_label}.mp4"
            aspect_ratio = "21:9"
        else:
            zone_label = f"_zone{zone_id}" if zone_id else ""
            filename = f"{course}{zone_label}.mp4"
            aspect_ratio = "1:1"

        output_path = str(self.output_dir / theme / mode.value / filename)

        job = GenerationJob(
            job_id=job_id,
            prompt=prompt,
            provider=provider,
            mode=mode,
            segment=segment,
            zone_id=zone_id,
            output_path=output_path,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            resolution="4k",
            seed_image_path=seed_image_path,
        )
        self.jobs[job_id] = job
        return job

    async def generate(self, job: GenerationJob) -> GenerationJob:
        """映像を生成（APIコール）"""
        job.status = GenerationStatus.GENERATING
        print(f"[VideoGen] Starting: {job.job_id}")
        print(f"[VideoGen] Mode: {job.mode.value} | Aspect: {job.aspect_ratio} | Provider: {job.provider.value}")
        print(f"[VideoGen] Prompt: {job.prompt[:100]}...")

        try:
            if job.provider == VideoProvider.RUNWAY:
                await self._generate_runway(job)
            elif job.provider == VideoProvider.KLING:
                await self._generate_kling(job)
            elif job.provider == VideoProvider.PIKA:
                await self._generate_pika(job)

            job.status = GenerationStatus.COMPLETE
            job.completed_at = time.time()
            print(f"[VideoGen] Complete: {job.job_id} → {job.output_path}")

        except Exception as e:
            job.status = GenerationStatus.FAILED
            job.error = str(e)
            print(f"[VideoGen] Failed: {job.job_id} - {e}")

        return job

    async def _generate_runway(self, job: GenerationJob):
        """Runway Gen-4.5 Turbo API — text-to-video or image-to-video generation.

        Supports two modes:
        - Text-to-video: generates from prompt only.
        - Image-to-video: uses a seed image (from storyboard preview) plus
          a motion prompt for higher quality results.

        The seed image path is resolved from the previews directory using the
        job's scene context.  If no seed image is found, falls back to
        text-to-video.

        Flow:
        1. Submit generation task to Runway API.
        2. Poll for completion (max RUNWAY_POLL_TIMEOUT seconds).
        3. Download the finished MP4.
        4. Save to output_path.
        """
        # Re-fetch key in case it was saved via Settings UI after init
        api_key = _get_api_key("RUNWAY_API_KEY") or self.runway_api_key
        if not api_key:
            await self._create_placeholder(job)
            return

        import httpx

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

        # Try to find a seed image for image-to-video mode
        seed_image_b64 = await self._find_seed_image(job)

        # Runway only supports 16:9, 9:16, 1:1 — map 21:9 → 16:9
        runway_ratio = job.aspect_ratio
        if runway_ratio == "21:9":
            runway_ratio = "16:9"

        # Build the request payload
        if seed_image_b64:
            # Image-to-video mode: use the generated preview as seed
            endpoint = f"{self.RUNWAY_API_BASE}/image_to_video"
            payload = {
                "model": "gen4_turbo",
                "promptImage": f"data:image/jpeg;base64,{seed_image_b64}",
                "promptText": job.prompt,
                "duration": job.duration_seconds,
                "ratio": runway_ratio,
            }
            print(f"[VideoGen] Runway i2v mode (seed image provided) | ratio={runway_ratio}")
        else:
            # Text-to-video fallback
            endpoint = f"{self.RUNWAY_API_BASE}/text_to_video"
            payload = {
                "model": "gen4_turbo",
                "promptText": job.prompt,
                "duration": job.duration_seconds,
                "ratio": runway_ratio,
            }
            print(f"[VideoGen] Runway t2v mode (no seed image) | ratio={runway_ratio}")

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0)) as client:
            # Step 1: Submit generation task
            response = await client.post(endpoint, headers=headers, json=payload)
            if response.status_code != 200:
                error_detail = response.text[:500]
                raise RuntimeError(
                    f"Runway API returned {response.status_code}: {error_detail}"
                )
            task_data = response.json()
            task_id = task_data["id"]
            print(f"[VideoGen] Runway task submitted: {task_id}")

            # Step 2: Poll for completion
            video_url = await self._poll_runway_task(client, headers, task_id)

            # Step 3: Download the video
            Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)
            video_resp = await client.get(video_url)
            if video_resp.status_code != 200:
                raise RuntimeError(
                    f"Failed to download Runway video: HTTP {video_resp.status_code}"
                )
            with open(job.output_path, "wb") as f:
                f.write(video_resp.content)

            video_size_mb = len(video_resp.content) / (1024 * 1024)
            print(f"[VideoGen] Runway video saved: {job.output_path} ({video_size_mb:.1f}MB)")

        # Save metadata alongside the video
        self._save_video_metadata(job, "gen4_turbo", seed_image=bool(seed_image_b64))

    async def _poll_runway_task(
        self,
        client: "httpx.AsyncClient",
        headers: dict[str, str],
        task_id: str,
    ) -> str:
        """Poll a Runway task until it succeeds, fails, or times out.

        Args:
            client: Active httpx AsyncClient.
            headers: Authorization headers for Runway API.
            task_id: The Runway task ID to poll.

        Returns:
            The URL of the generated video.

        Raises:
            RuntimeError: If the task fails or times out.
        """
        poll_url = f"{self.RUNWAY_API_BASE}/tasks/{task_id}"
        elapsed = 0.0

        while elapsed < self.RUNWAY_POLL_TIMEOUT:
            await asyncio.sleep(self.RUNWAY_POLL_INTERVAL)
            elapsed += self.RUNWAY_POLL_INTERVAL

            status_resp = await client.get(poll_url, headers=headers)
            if status_resp.status_code != 200:
                print(f"[VideoGen] Runway poll error: HTTP {status_resp.status_code}")
                continue

            result = status_resp.json()
            status = result.get("status", "UNKNOWN")
            print(f"[VideoGen] Runway task {task_id}: {status} ({elapsed:.0f}s)")

            if status == "SUCCEEDED":
                output = result.get("output", [])
                if not output:
                    raise RuntimeError("Runway task succeeded but returned no output URLs")
                return output[0]
            elif status == "FAILED":
                error_msg = result.get("failure", result.get("error", "Unknown error"))
                raise RuntimeError(f"Runway generation failed: {error_msg}")

        raise RuntimeError(
            f"Runway task {task_id} timed out after {self.RUNWAY_POLL_TIMEOUT}s"
        )

    async def _find_seed_image(self, job: GenerationJob) -> Optional[str]:
        """Look for a seed image to use for image-to-video generation.

        Priority:
        1. Explicit seed_image_path set on the job.
        2. Most recent preview image from the previews directory.

        Returns the image as a base64-encoded JPEG string, or None if not found.
        """
        seed_path: Optional[Path] = None

        # Priority 1: explicit seed image path from the job
        if job.seed_image_path:
            p = Path(job.seed_image_path)
            if p.exists() and p.stat().st_size > 100:
                seed_path = p

        # Priority 2: scan previews directory
        if seed_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            previews_dir = Path(project_root) / "touchdesigner" / "content" / "previews"
            if previews_dir.exists():
                candidates = sorted(
                    previews_dir.glob("*.jpg"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for c in candidates:
                    if c.stat().st_size > 100:
                        seed_path = c
                        break

        if seed_path is None:
            return None

        try:
            with open(seed_path, "rb") as f:
                image_bytes = f.read()
            print(f"[VideoGen] Using seed image: {seed_path.name} ({len(image_bytes) / 1024:.0f}KB)")
            return base64.b64encode(image_bytes).decode("ascii")
        except Exception as e:
            print(f"[VideoGen] Failed to read seed image: {e}")
            return None

    def _save_video_metadata(
        self,
        job: GenerationJob,
        model: str,
        seed_image: bool = False,
    ) -> None:
        """Save metadata JSON alongside the generated video."""
        output = Path(job.output_path)
        meta_path = output.with_suffix(".json")
        metadata = {
            "job_id": job.job_id,
            "prompt": job.prompt,
            "provider": job.provider.value,
            "model": model,
            "mode": job.mode.value,
            "segment": job.segment,
            "zone_id": job.zone_id,
            "aspect_ratio": job.aspect_ratio,
            "resolution": job.resolution,
            "duration": job.duration_seconds,
            "seed_image_used": seed_image,
            "status": "complete",
            "generated_at": time.time(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    async def _generate_kling(self, job: GenerationJob):
        """Kling API — 16:9 or 1:1（21:9非対応のため統一モードは非推奨）"""
        if job.mode == GenerationMode.UNIFIED:
            print("[VideoGen] Warning: Kling does not support 21:9. Falling back to 16:9.")
            job.aspect_ratio = "16:9"

        if not self.kling_api_key:
            await self._create_placeholder(job)
            return
        await self._create_placeholder(job)

    async def _generate_pika(self, job: GenerationJob):
        """Pika API — 16:9 or 1:1"""
        if job.mode == GenerationMode.UNIFIED:
            print("[VideoGen] Warning: Pika does not support 21:9. Falling back to 16:9.")
            job.aspect_ratio = "16:9"
        await self._create_placeholder(job)

    async def _create_placeholder(self, job: GenerationJob):
        """プレースホルダ作成（API未設定時のデモ用）"""
        output = Path(job.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        meta_path = output.with_suffix('.json')
        metadata = {
            "job_id": job.job_id,
            "prompt": job.prompt,
            "provider": job.provider.value,
            "mode": job.mode.value,
            "segment": job.segment,
            "zone_id": job.zone_id,
            "aspect_ratio": job.aspect_ratio,
            "resolution": job.resolution,
            "duration": job.duration_seconds,
            "status": "placeholder",
            "note": "APIキーを設定すると実際の映像が生成されます",
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        output.touch()
        print(f"[VideoGen] Placeholder: {meta_path}")

    # ─── バッチ生成 ───────────────────────────────────────────────

    async def generate_unified_course(
        self,
        theme: str,
        course: str,
        provider: VideoProvider = VideoProvider.RUNWAY,
        extra_prompt: Optional[str] = None,
    ) -> list[GenerationJob]:
        """統一モード: 左右2セグメントを並列生成"""
        print(f"\n[Unified] Generating {theme}/{course} (L + R segments)")

        job_left = self.create_job(theme, course, GenerationMode.UNIFIED, provider, segment="left", extra_prompt=extra_prompt)
        job_right = self.create_job(theme, course, GenerationMode.UNIFIED, provider, segment="right", extra_prompt=extra_prompt)

        results = await asyncio.gather(
            self.generate(job_left),
            self.generate(job_right),
        )
        return list(results)

    async def generate_zone_course(
        self,
        theme: str,
        course: str,
        zone_id: int = 0,
        provider: VideoProvider = VideoProvider.RUNWAY,
        extra_prompt: Optional[str] = None,
    ) -> GenerationJob:
        """区画モード: 指定区画の映像を生成（zone_id=0で全4区画）"""
        if zone_id > 0:
            job = self.create_job(theme, course, GenerationMode.ZONE, provider, zone_id=zone_id, extra_prompt=extra_prompt)
            return await self.generate(job)
        else:
            # 全4区画を並列生成
            jobs = [
                self.create_job(theme, course, GenerationMode.ZONE, provider, zone_id=z, extra_prompt=extra_prompt)
                for z in range(1, ZONE_COUNT + 1)
            ]
            results = await asyncio.gather(*[self.generate(j) for j in jobs])
            return results[0]  # 最初のジョブを返す

    async def generate_theme_batch(
        self,
        theme: str,
        mode: GenerationMode = GenerationMode.UNIFIED,
        provider: VideoProvider = VideoProvider.RUNWAY,
    ):
        """テーマの全コース映像を一括生成"""
        print(f"\n{'='*60}")
        print(f"[Batch] Theme: {theme} | Mode: {mode.value}")
        print(f"{'='*60}")

        for course in COURSE_ORDER:
            if mode == GenerationMode.UNIFIED:
                await self.generate_unified_course(theme, course, provider)
            else:
                await self.generate_zone_course(theme, course, 0, provider)

        print(f"\n[Batch] Done: {theme} ({mode.value})")

    async def generate_all_themes(
        self,
        mode: GenerationMode = GenerationMode.UNIFIED,
        provider: VideoProvider = VideoProvider.RUNWAY,
    ):
        """全テーマ一括生成"""
        for theme in THEME_PROMPTS:
            await self.generate_theme_batch(theme, mode, provider)

    def get_job_status(self, job_id: str) -> Optional[dict]:
        job = self.jobs.get(job_id)
        return asdict(job) if job else None

    def list_available_content(self) -> dict:
        content = {}
        for theme_dir in self.output_dir.iterdir():
            if theme_dir.is_dir():
                for mode_dir in theme_dir.iterdir():
                    if mode_dir.is_dir():
                        files = list(mode_dir.glob("*.mp4"))
                        key = f"{theme_dir.name}/{mode_dir.name}"
                        content[key] = [f.stem for f in files]
        return content


# ====================================================================
# CLI
# ====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="AI映像生成ワーカー (v2: unified/zone対応)")
    subparsers = parser.add_subparsers(dest="command")

    # 単体生成
    gen_parser = subparsers.add_parser("generate", help="単体映像生成")
    gen_parser.add_argument("--theme", required=True, choices=list(THEME_PROMPTS.keys()))
    gen_parser.add_argument("--course", required=True, choices=COURSE_ORDER)
    gen_parser.add_argument("--mode", default="unified", choices=["unified", "zone"])
    gen_parser.add_argument("--zone", type=int, default=0, help="区画番号 1-4 (zone mode)")
    gen_parser.add_argument("--provider", default="runway", choices=["runway", "kling", "pika"])

    # バッチ生成
    batch_parser = subparsers.add_parser("batch", help="テーマ一括生成")
    batch_parser.add_argument("--day", required=True, choices=list(DAY_TO_THEME.keys()))
    batch_parser.add_argument("--mode", default="unified", choices=["unified", "zone"])
    batch_parser.add_argument("--provider", default="runway", choices=["runway", "kling", "pika"])

    # 全テーマ
    all_parser = subparsers.add_parser("all", help="全テーマ一括生成")
    all_parser.add_argument("--mode", default="unified", choices=["unified", "zone"])

    # プロンプト一覧
    prompts_parser = subparsers.add_parser("prompts", help="プロンプト一覧表示")
    prompts_parser.add_argument("--mode", default="unified", choices=["unified", "zone"])

    args = parser.parse_args()
    service = VideoGeneratorService()

    if args.command == "generate":
        mode = GenerationMode(args.mode)
        if mode == GenerationMode.UNIFIED:
            asyncio.run(service.generate_unified_course(
                args.theme, args.course, VideoProvider(args.provider)
            ))
        else:
            asyncio.run(service.generate_zone_course(
                args.theme, args.course, args.zone, VideoProvider(args.provider)
            ))

    elif args.command == "batch":
        theme = DAY_TO_THEME[args.day]
        asyncio.run(service.generate_theme_batch(theme, GenerationMode(args.mode), VideoProvider(args.provider)))

    elif args.command == "all":
        asyncio.run(service.generate_all_themes(GenerationMode(args.mode)))

    elif args.command == "prompts":
        mode = GenerationMode(args.mode)
        for theme, courses in THEME_PROMPTS.items():
            print(f"\n{'='*60}")
            print(f"Theme: {theme} | Mode: {args.mode}")
            print(f"{'='*60}")
            for course, prompts in courses.items():
                full_prompt = _build_prompt(theme, course, mode)
                print(f"\n  [{course}]")
                print(f"  {full_prompt[:120]}...")
    else:
        parser.print_help()
