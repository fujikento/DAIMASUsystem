"""
汎用AIキャラクター生成サービス

バースデー以外にも使える汎用的なキャラクター生成:
- ウェルカムアバター（来店時）
- リアクションキャラ（料理提供時）
- メモリアルフォト（退店時のお土産画像）

技術: LivePortrait (ローカル) / Hedra AI (API) / Stable Diffusion (スタイル変換)
出力: 区画サイズ 1380x1200 に最適化

使い方:
    python workers/character_generator.py avatar --photo /path/to/photo.jpg --name ゲスト --theme ocean
    python workers/character_generator.py animation --photo /path/to/photo.jpg --template birthday_cake --zone 2
    python workers/character_generator.py memorial --photo /path/to/photo.jpg --name ゲスト --theme ocean
    python workers/character_generator.py templates --category welcome
"""

import asyncio
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


# 区画投影サイズ (content_compositor.py と統一)
ZONE_WIDTH = 1380
ZONE_HEIGHT = 1200


class CharacterJobStatus(str, Enum):
    QUEUED = "queued"
    DETECTING_FACE = "detecting_face"
    STYLING = "styling"
    ANIMATING = "animating"
    COMPOSITING = "compositing"
    COMPLETE = "complete"
    FAILED = "failed"


class CharacterJobType(str, Enum):
    AVATAR = "avatar"
    ANIMATION = "animation"
    MEMORIAL = "memorial"


class AnimationProvider(str, Enum):
    LIVEPORTRAIT = "liveportrait"
    HEDRA = "hedra"


class StylePreset(str, Enum):
    NONE = "none"
    WATERCOLOR = "watercolor"
    OIL_PAINTING = "oil_painting"
    SUMI_E = "sumi_e"
    NEON = "neon"
    GOLD_LEAF = "gold_leaf"
    SCI_FI = "sci_fi"
    STORYBOOK = "storybook"


# テーマ→スタイルプリセットのマッピング
THEME_STYLE_MAP: dict[str, StylePreset] = {
    "ocean": StylePreset.WATERCOLOR,
    "forest": StylePreset.OIL_PAINTING,
    "zen": StylePreset.SUMI_E,
    "fire": StylePreset.NEON,
    "gold": StylePreset.GOLD_LEAF,
    "space": StylePreset.SCI_FI,
    "fairytale": StylePreset.STORYBOOK,
}


# ── テンプレート定義 ──────────────────────────────────────────────────

# バースデー系 (既存5種のうち3種 + 統合)
BIRTHDAY_TEMPLATES = {
    "birthday_cake": {
        "name": "ケーキ作り",
        "category": "birthday",
        "description": "キャラクターがケーキを作って祝福する演出",
        "duration": 30,
        "driving_video": "templates/birthday/cake_making_driver.mp4",
        "background": "templates/birthday/cake_making_bg.mp4",
        "composite_position": {"x": 0.3, "y": 0.2, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "birthday_fireworks": {
        "name": "花火セレブレーション",
        "category": "birthday",
        "description": "花火をバックにキャラクターが祝福ダンス",
        "duration": 20,
        "driving_video": "templates/birthday/fireworks_driver.mp4",
        "background": "templates/birthday/fireworks_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.6, "scale": 0.45},
        "text_position": {"x": 0.5, "y": 0.1, "anchor": "center"},
    },
    "birthday_magic": {
        "name": "魔法の庭園",
        "category": "birthday",
        "description": "キャラクターが魔法で花を咲かせる演出",
        "duration": 25,
        "driving_video": "templates/birthday/magic_garden_driver.mp4",
        "background": "templates/birthday/magic_garden_bg.mp4",
        "composite_position": {"x": 0.4, "y": 0.3, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
}

# ウェルカム系
WELCOME_TEMPLATES = {
    "welcome_elegant": {
        "name": "エレガント入場",
        "category": "welcome",
        "description": "シンプルで洗練されたウェルカム演出",
        "duration": 10,
        "driving_video": "templates/welcome/elegant_entrance_driver.mp4",
        "background": "templates/welcome/elegant_entrance_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.5},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "welcome_nature": {
        "name": "ナチュラルウェルカム",
        "category": "welcome",
        "description": "自然のモチーフでゲストを迎える演出",
        "duration": 10,
        "driving_video": "templates/welcome/nature_welcome_driver.mp4",
        "background": "templates/welcome/nature_welcome_bg.mp4",
        "composite_position": {"x": 0.4, "y": 0.3, "scale": 0.45},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "welcome_sparkle": {
        "name": "スパークル",
        "category": "welcome",
        "description": "キラキラとした輝きの演出でゲストを迎える",
        "duration": 8,
        "driving_video": "templates/welcome/sparkle_driver.mp4",
        "background": "templates/welcome/sparkle_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.5, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.1, "anchor": "center"},
    },
}

# サプライズ系
SURPRISE_TEMPLATES = {
    "surprise_gift": {
        "name": "ギフトサプライズ",
        "category": "surprise",
        "description": "ギフトボックスが開いてキャラクターが登場",
        "duration": 15,
        "driving_video": "templates/surprise/gift_reveal_driver.mp4",
        "background": "templates/surprise/gift_reveal_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.45},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "surprise_confetti": {
        "name": "紙吹雪セレブレーション",
        "category": "surprise",
        "description": "紙吹雪が舞うお祝い演出",
        "duration": 12,
        "driving_video": "templates/surprise/confetti_driver.mp4",
        "background": "templates/surprise/confetti_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.5, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.1, "anchor": "center"},
    },
}

# 季節イベント系
SEASON_TEMPLATES = {
    "season_spring": {
        "name": "桜フェスティバル",
        "category": "season",
        "description": "桜が舞う春のお祝い演出",
        "duration": 15,
        "driving_video": "templates/season/spring_sakura_driver.mp4",
        "background": "templates/season/spring_sakura_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "season_summer": {
        "name": "サマーパラダイス",
        "category": "season",
        "description": "ビーチリゾート風の夏の演出",
        "duration": 15,
        "driving_video": "templates/season/summer_beach_driver.mp4",
        "background": "templates/season/summer_beach_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.5, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "season_autumn": {
        "name": "オータムハーベスト",
        "category": "season",
        "description": "紅葉と収穫の秋の演出",
        "duration": 15,
        "driving_video": "templates/season/autumn_harvest_driver.mp4",
        "background": "templates/season/autumn_harvest_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.4},
        "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
    },
    "season_winter": {
        "name": "ウィンターワンダーランド",
        "category": "season",
        "description": "雪景色のファンタジー冬の演出",
        "duration": 15,
        "driving_video": "templates/season/winter_snow_driver.mp4",
        "background": "templates/season/winter_snow_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.45},
        "text_position": {"x": 0.5, "y": 0.1, "anchor": "center"},
    },
}

# 全テンプレートを統合
ALL_TEMPLATES: dict[str, dict] = {
    **BIRTHDAY_TEMPLATES,
    **WELCOME_TEMPLATES,
    **SURPRISE_TEMPLATES,
    **SEASON_TEMPLATES,
}

# カテゴリ→テンプレートIDマッピング
CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "birthday": list(BIRTHDAY_TEMPLATES.keys()),
    "welcome": list(WELCOME_TEMPLATES.keys()),
    "surprise": list(SURPRISE_TEMPLATES.keys()),
    "season": list(SEASON_TEMPLATES.keys()),
}


@dataclass
class CharacterJob:
    job_id: str
    job_type: CharacterJobType
    photo_path: str
    guest_name: str = ""
    theme: str = "ocean"
    template_id: Optional[str] = None
    zone_id: int = 1
    provider: AnimationProvider = AnimationProvider.LIVEPORTRAIT
    style_preset: StylePreset = StylePreset.NONE
    status: CharacterJobStatus = CharacterJobStatus.QUEUED
    # 中間出力
    face_detected: bool = False
    styled_photo_path: Optional[str] = None
    animated_portrait_path: Optional[str] = None
    # 最終出力
    output_path: Optional[str] = None
    error: Optional[str] = None
    target_width: int = ZONE_WIDTH
    target_height: int = ZONE_HEIGHT
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    # メモリアル用追加フィールド
    scenes: Optional[list[str]] = None


def _get_api_key(key_name: str) -> str:
    """APIキーをDBから取得し、なければ環境変数にフォールバック。

    image_generator.py と同じパターン。
    """
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


# テーマ→スタイル説明のマッピング（Geminiプロンプト用）
THEME_STYLE_PROMPTS: dict[str, str] = {
    "ocean": (
        "ocean theme with deep blue and turquoise watercolor tones, flowing water ripples, "
        "bioluminescent accents, and gentle wave patterns"
    ),
    "forest": (
        "lush forest theme with rich emerald greens and earthy browns, oil-painting brushstroke "
        "texture, dappled light through canopy, and botanical details"
    ),
    "fire": (
        "fire and ember theme with vivid orange, crimson, and gold neon-glow tones, dynamic "
        "flame energy, and radiant heat shimmer"
    ),
    "ice": (
        "ice and crystal theme with cool pale blues, icy whites, and silver crystalline "
        "frost patterns with a delicate frozen texture"
    ),
    "cosmos": (
        "cosmic space theme with deep violet and midnight blue, glowing nebula clouds, "
        "star-field particles, and sci-fi holographic accents"
    ),
    "garden": (
        "blooming garden theme with soft petal pinks, sage greens, and warm ivory, "
        "watercolor floral motifs and botanical illustration style"
    ),
    "sunset": (
        "golden sunset theme with warm amber, coral, and rose-gold gradients, "
        "impressionistic sky texture and soft light-glow effects"
    ),
    # Legacy mappings from THEME_STYLE_MAP
    "zen": (
        "Japanese zen theme with sumi-e ink wash painting style, minimalist composition, "
        "muted grey and ivory tones, and delicate brushstroke details"
    ),
    "gold": (
        "luxury gold-leaf theme with metallic gold and deep black accents, "
        "intricate gilded patterns and opulent art-deco ornamentation"
    ),
    "space": (
        "sci-fi space theme with electric blue and neon purple holographic tones, "
        "digital circuit patterns, and futuristic glow effects"
    ),
    "fairytale": (
        "whimsical fairy-tale theme with pastel rainbow colours, "
        "storybook illustration style, and magical sparkle details"
    ),
}


def _project_root() -> str:
    """Return the immersive-dining project root directory."""
    # workers/ is one level below the project root.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CharacterGeneratorService:
    """汎用AIキャラクター生成サービス

    バースデー以外にも使える汎用的なキャラクター生成:
    - ウェルカムアバター（来店時）
    - リアクションキャラ（料理提供時）
    - メモリアルフォト（退店時のお土産画像）
    """

    def __init__(
        self,
        templates_dir: str = "",
        output_dir: str = "",
    ):
        root = _project_root()
        if not templates_dir:
            templates_dir = os.path.join(root, "touchdesigner", "content", "templates")
        if not output_dir:
            output_dir = os.path.join(root, "api", "uploads", "character_outputs")
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, CharacterJob] = {}
        self._job_counter = 0

        # LivePortrait設定 — defaults to $HOME/LivePortrait if not overridden.
        self.liveportrait_path = os.environ.get(
            "LIVEPORTRAIT_PATH",
            os.path.join(os.path.expanduser("~"), "LivePortrait"),
        )

        # Geminiクライアントキャッシュ (image_generator.py と同じパターン)
        self._gemini_api_key: Optional[str] = None
        self._gemini_client: Optional[object] = None

    def _next_job_id(self, prefix: str) -> str:
        self._job_counter += 1
        return f"{prefix}_{self._job_counter}_{int(time.time())}"

    def _get_gemini_client(self) -> object:
        """Gemini クライアントを返す。APIキーが変わった場合は再生成する。

        image_generator.py の _get_gemini_client と同じキャッシュ方式。

        Returns:
            genai.Client インスタンス

        Raises:
            RuntimeError: Gemini APIキーが設定されていない場合
        """
        from google import genai

        current_key = _get_api_key("GEMINI_API_KEY")
        if not current_key:
            raise RuntimeError("GEMINI_API_KEY が設定されていません")

        if self._gemini_client is None or self._gemini_api_key != current_key:
            self._gemini_api_key = current_key
            self._gemini_client = genai.Client(api_key=current_key)

        return self._gemini_client

    # ── ウェルカムアバター生成 ────────────────────────────────────

    def generate_welcome_avatar(
        self,
        photo_path: str,
        guest_name: str,
        theme: str = "ocean",
        template_id: str = "welcome_elegant",
        zone_id: int = 1,
    ) -> CharacterJob:
        """ウェルカム用アバター生成ジョブを作成して実行キューに追加"""
        if template_id not in ALL_TEMPLATES:
            raise ValueError(f"Unknown template: {template_id}. Available: {list(ALL_TEMPLATES.keys())}")
        if not Path(photo_path).exists():
            raise FileNotFoundError(f"Photo not found: {photo_path}")

        style = THEME_STYLE_MAP.get(theme, StylePreset.NONE)
        job_id = self._next_job_id("avatar")

        job = CharacterJob(
            job_id=job_id,
            job_type=CharacterJobType.AVATAR,
            photo_path=photo_path,
            guest_name=guest_name,
            theme=theme,
            template_id=template_id,
            zone_id=zone_id,
            style_preset=style,
            output_path=str(self.output_dir / f"{job_id}_avatar.mp4"),
        )
        self.jobs[job_id] = job
        return job

    # ── バースデーアニメーション生成 ──────────────────────────────

    def generate_birthday_animation(
        self,
        photo_path: str,
        guest_name: str,
        template_id: str = "birthday_cake",
        zone_id: int = 1,
        provider: AnimationProvider = AnimationProvider.LIVEPORTRAIT,
    ) -> CharacterJob:
        """バースデーアニメーション生成ジョブを作成"""
        if template_id not in ALL_TEMPLATES:
            raise ValueError(f"Unknown template: {template_id}. Available: {list(ALL_TEMPLATES.keys())}")
        if not Path(photo_path).exists():
            raise FileNotFoundError(f"Photo not found: {photo_path}")

        job_id = self._next_job_id("bday")

        job = CharacterJob(
            job_id=job_id,
            job_type=CharacterJobType.ANIMATION,
            photo_path=photo_path,
            guest_name=guest_name,
            template_id=template_id,
            zone_id=zone_id,
            provider=provider,
            output_path=str(self.output_dir / f"{job_id}_animation.mp4"),
        )
        self.jobs[job_id] = job
        return job

    # ── メモリアルフォト生成 ──────────────────────────────────────

    def generate_memorial_photo(
        self,
        photo_path: str,
        guest_name: str,
        theme: str = "ocean",
        scenes: Optional[list[str]] = None,
    ) -> CharacterJob:
        """退店時のお土産合成画像を生成"""
        if not Path(photo_path).exists():
            raise FileNotFoundError(f"Photo not found: {photo_path}")

        style = THEME_STYLE_MAP.get(theme, StylePreset.NONE)
        job_id = self._next_job_id("memorial")

        job = CharacterJob(
            job_id=job_id,
            job_type=CharacterJobType.MEMORIAL,
            photo_path=photo_path,
            guest_name=guest_name,
            theme=theme,
            style_preset=style,
            scenes=scenes or ["dining_highlight", "group_photo"],
            output_path=str(self.output_dir / f"{job_id}_memorial.jpg"),
        )
        self.jobs[job_id] = job
        return job

    # ── ジョブ実行 ────────────────────────────────────────────────

    async def process(self, job: CharacterJob) -> CharacterJob:
        """キャラクター生成フルパイプラインを実行"""
        try:
            print(f"[CharGen] Processing: {job.job_id} (type={job.job_type.value})")

            # Step 1: 顔検出
            job.status = CharacterJobStatus.DETECTING_FACE
            job.face_detected = await self._detect_face(job)
            if not job.face_detected:
                print(f"[CharGen] Face not detected, using fallback for {job.job_id}")

            # Step 2: スタイル変換 (avatar/memorial のみ)
            if job.style_preset != StylePreset.NONE:
                job.status = CharacterJobStatus.STYLING
                await self._apply_style(job)

            # Step 3: アニメーション生成 (avatar/animation のみ)
            if job.job_type in (CharacterJobType.AVATAR, CharacterJobType.ANIMATION):
                job.status = CharacterJobStatus.ANIMATING
                await self._animate(job)

            # Step 4: 合成
            job.status = CharacterJobStatus.COMPOSITING
            if job.job_type == CharacterJobType.MEMORIAL:
                await self._composite_memorial(job)
            else:
                await self._composite_animation(job)

            job.status = CharacterJobStatus.COMPLETE
            job.completed_at = time.time()
            elapsed = job.completed_at - job.created_at
            print(f"[CharGen] Complete: {job.job_id} ({elapsed:.1f}s)")
            print(f"[CharGen] Output: {job.output_path}")

        except Exception as e:
            job.status = CharacterJobStatus.FAILED
            job.error = str(e)
            print(f"[CharGen] Failed: {job.job_id} - {e}")

        return job

    # ── 内部: 顔検出 ─────────────────────────────────────────────

    async def _detect_face(self, job: CharacterJob) -> bool:
        """PIL ベースの顔検出 (肌色ヒューリスティック)。

        MediaPipe/OpenCV が不要な軽量実装。
        - 画像をリサイズしてから HSV 空間で肌色領域を探す
        - 肌色ピクセルが全体の 3% 以上あれば「顔あり」と判定
        - 失敗時は安全側に倒して True を返す

        Returns:
            bool: 顔が検出された場合 True、検出できなかった場合 False
        """
        try:
            from PIL import Image as PilImage

            with PilImage.open(job.photo_path) as img:
                # 処理速度のために縮小
                img_rgb = img.convert("RGB").resize((320, 320), PilImage.LANCZOS)
                pixels = list(img_rgb.getdata())
                total = len(pixels)

                skin_count = 0
                for r, g, b in pixels:
                    # 肌色ヒューリスティック (RGB空間)
                    # 条件: r > 95, g > 40, b > 20, max-min > 15, r > g, r > b
                    if (
                        r > 95
                        and g > 40
                        and b > 20
                        and (max(r, g, b) - min(r, g, b)) > 15
                        and r > g
                        and r > b
                    ):
                        skin_count += 1

                ratio = skin_count / total
                detected = ratio >= 0.03  # 3% 以上で顔ありと判定
                print(
                    f"[CharGen] Face detection: skin_ratio={ratio:.3f} "
                    f"({'detected' if detected else 'not detected'}) | {job.photo_path}"
                )
                return detected

        except Exception as e:
            # 検出失敗時は安全側に倒して True を返す (処理を続行させる)
            print(f"[CharGen] Face detection error (fallback=True): {e}")
            return True

    # ── 内部: スタイル変換 ───────────────────────────────────────

    async def _apply_style(self, job: CharacterJob) -> None:
        """Gemini でテーマに合わせた画像スタイル変換を実行する。

        アップロードされたキャラクター写真を入力として Gemini の
        multimodal 生成 (vision + image output) でスタイル変換し、
        _styled.jpg として保存する。

        Gemini が利用できない場合は元写真をコピーしてフォールバック。
        """
        styled_path = str(self.output_dir / f"{job.job_id}_styled.jpg")
        job.styled_photo_path = styled_path

        try:
            await self._apply_style_gemini(job, styled_path)
        except Exception as e:
            print(f"[CharGen] Gemini style transfer failed: {e}")
            print("[CharGen] Falling back to copy of original photo")
            await self._apply_style_fallback(job, styled_path)

    async def _apply_style_gemini(self, job: CharacterJob, styled_path: str) -> None:
        """Gemini multimodal API でスタイル変換を実行する。

        image_generator.py の _generate_gemini と同じ google.genai パターンを使用。
        入力: キャラクター写真 (JPEG bytes) + テキストプロンプト
        出力: テーマスタイルに変換されたキャラクター画像 → styled_path に保存

        Args:
            job: 実行中のキャラクタージョブ
            styled_path: 出力先ファイルパス (_styled.jpg)

        Raises:
            RuntimeError: APIキー未設定またはAPIがレスポンスに画像を返さない場合
            Exception: google.genai のインポートエラー、ファイル読み込みエラー等
        """
        import time as _t
        t_start = _t.monotonic()

        try:
            from google.genai import types
        except ImportError:
            raise RuntimeError(
                "google-genai SDK がインストールされていません。"
                "pip install google-genai を実行してください"
            )

        # Geminiクライアントを取得 (APIキー未設定時は RuntimeError)
        client = self._get_gemini_client()

        # キャラクター写真を読み込んでJPEGバイト列に変換
        photo_path = Path(job.styled_photo_path or job.photo_path)
        # styled_photo_path はまだ存在しないので元画像を使う
        photo_path = Path(job.photo_path)
        if not photo_path.exists():
            raise FileNotFoundError(f"キャラクター写真が見つかりません: {photo_path}")

        # PILで開いてJPEGとして標準化 (PNG・HEIC等でも対応)
        try:
            from PIL import Image as PilImage
            with PilImage.open(str(photo_path)) as img:
                img_rgb = img.convert("RGB")
                buf = io.BytesIO()
                img_rgb.save(buf, format="JPEG", quality=90)
                photo_bytes = buf.getvalue()
        except ImportError:
            # Pillow なければバイナリそのまま読む
            with open(str(photo_path), "rb") as f:
                photo_bytes = f.read()

        # テーマに応じたスタイル説明を取得
        theme_desc = THEME_STYLE_PROMPTS.get(
            job.theme,
            f"{job.theme} theme with elegant artistic styling"
        )

        # Geminiへのプロンプト
        prompt_text = (
            f"You are an artistic style transfer AI for an immersive dining projection system.\n\n"
            f"Transform the character in this image into the following dining theme style:\n"
            f"Theme: {job.theme}\n"
            f"Style description: {theme_desc}\n\n"
            f"Requirements:\n"
            f"- Keep the character fully recognizable (same pose, shape, and identity)\n"
            f"- Adapt the art style, color palette, and visual texture to match the {job.theme} theme\n"
            f"- Make it elegant and visually striking for projection on a dining table surface\n"
            f"- Output a clean portrait-style illustration suitable for theatrical projection\n"
            f"- Maintain a transparent-friendly or dark background so the character stands out\n"
            f"- The result should feel like a high-quality digital artwork, not a photograph\n"
        )

        model = "gemini-2.0-flash-exp-image-generation"
        print(f"[CharGen] Gemini style transfer: model={model}, theme={job.theme}")
        print(f"[CharGen] Photo: {photo_path} ({len(photo_bytes) // 1024}KB)")

        # APIコールはブロッキングなのでスレッドプールで実行
        loop = asyncio.get_running_loop()

        def _call_api():
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=photo_bytes, mime_type="image/jpeg"),
                    prompt_text,
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    temperature=1,
                    top_p=0.95,
                    top_k=40,
                ),
            )
            return response

        response = await loop.run_in_executor(None, _call_api)
        t_api = _t.monotonic() - t_start

        # レスポンスから画像データを抽出
        image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break

        if image_data is None:
            raise RuntimeError(
                "Gemini がレスポンスに画像データを返しませんでした。"
                "プロンプトまたはモデルの設定を確認してください"
            )

        # 出力先に保存
        output = Path(styled_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            from PIL import Image as PilImage
            pil_image = PilImage.open(io.BytesIO(image_data)).convert("RGB")
            pil_image.save(styled_path, format="JPEG", quality=90)
            w, h = pil_image.size
            print(f"[CharGen] Styled image saved: {styled_path} ({w}x{h})")
        except ImportError:
            with open(styled_path, "wb") as f:
                f.write(image_data)
            print(f"[CharGen] Styled image saved (raw): {styled_path}")

        t_total = _t.monotonic() - t_start
        print(
            f"[CharGen] Gemini style transfer complete | "
            f"api={t_api*1000:.0f}ms | total={t_total*1000:.0f}ms | "
            f"output={len(image_data) // 1024}KB"
        )

        # メタデータ保存
        meta_path = Path(styled_path).with_suffix(".json")
        metadata = {
            "job_id": job.job_id,
            "job_type": job.job_type.value,
            "label": "styled_photo",
            "photo": job.photo_path,
            "guest_name": job.guest_name,
            "theme": job.theme,
            "template": job.template_id,
            "style": job.style_preset.value,
            "provider": "gemini",
            "model": model,
            "status": "complete",
            "generated_at": time.time(),
        }
        with open(str(meta_path), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    async def _apply_style_fallback(self, job: CharacterJob, styled_path: str) -> None:
        """スタイル変換失敗時のフォールバック: 元写真をコピー"""
        import shutil
        output = Path(styled_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(job.photo_path, styled_path)
            print(f"[CharGen] Fallback: copied original photo → {styled_path}")
        except Exception as copy_err:
            print(f"[CharGen] Fallback copy also failed: {copy_err}")
            output.touch()

    # ── 内部: アニメーション生成 ─────────────────────────────────

    async def _animate(self, job: CharacterJob) -> None:
        """LivePortrait / Hedra でアニメーション生成"""
        animated_path = str(self.output_dir / f"{job.job_id}_animated.mp4")
        job.animated_portrait_path = animated_path

        if job.provider == AnimationProvider.LIVEPORTRAIT:
            await self._animate_liveportrait(job, animated_path)
        elif job.provider == AnimationProvider.HEDRA:
            await self._animate_hedra(job, animated_path)

    async def _animate_liveportrait(self, job: CharacterJob, output_path: str) -> None:
        """LivePortraitでアニメーション生成"""
        template = ALL_TEMPLATES.get(job.template_id, {})
        driving_video = str(self.templates_dir / template.get("driving_video", ""))

        liveportrait_dir = Path(self.liveportrait_path)
        if not liveportrait_dir.exists():
            print("[CharGen] LivePortrait not installed, creating placeholder")
            await self._create_placeholder_file(job, output_path, "animated_portrait")
            return

        # LivePortrait実行コマンド (本番用)
        # source_photo = job.styled_photo_path or job.photo_path
        # cmd = [
        #     "python", str(liveportrait_dir / "inference.py"),
        #     "--source_image", source_photo,
        #     "--driving_video", driving_video,
        #     "--output_path", output_path,
        #     "--flag_relative_motion", "True",
        #     "--flag_pasteback", "True",
        # ]
        # process = await asyncio.create_subprocess_exec(
        #     *cmd,
        #     stdout=asyncio.subprocess.PIPE,
        #     stderr=asyncio.subprocess.PIPE,
        # )
        # stdout, stderr = await process.communicate()
        # if process.returncode != 0:
        #     raise Exception(f"LivePortrait failed: {stderr.decode()}")

        await self._create_placeholder_file(job, output_path, "animated_portrait")

    async def _animate_hedra(self, job: CharacterJob, output_path: str) -> None:
        """Hedra AIでアニメーション生成"""
        hedra_api_key = os.environ.get("HEDRA_API_KEY", "")
        if not hedra_api_key:
            print("[CharGen] Hedra API key not set, creating placeholder")
            await self._create_placeholder_file(job, output_path, "animated_portrait")
            return

        # Hedra API呼び出し (本番用)
        # import httpx
        # source_photo = job.styled_photo_path or job.photo_path
        # async with httpx.AsyncClient() as client:
        #     with open(source_photo, 'rb') as f:
        #         response = await client.post(
        #             "https://api.hedra.com/v1/characters",
        #             headers={"Authorization": f"Bearer {hedra_api_key}"},
        #             files={"image": f},
        #             data={
        #                 "text": f"Welcome, {job.guest_name}!",
        #                 "voice": "en-US-warm-female",
        #             }
        #         )
        #     result = response.json()
        #     video_url = result["video_url"]
        #     video_resp = await client.get(video_url)
        #     with open(output_path, 'wb') as f:
        #         f.write(video_resp.content)

        await self._create_placeholder_file(job, output_path, "animated_portrait")

    # ── 内部: 合成 ───────────────────────────────────────────────

    async def _composite_animation(self, job: CharacterJob) -> None:
        """アニメーションをテンプレート背景に合成 → 区画サイズ出力。

        テンプレート背景動画と LivePortrait/Hedra が生成したアニメーション動画を
        ffmpeg で合成し、区画サイズ (ZONE_WIDTH x ZONE_HEIGHT) にリサイズして出力する。

        背景動画またはアニメーション動画が存在しない場合は PIL で静止画フォールバックを生成する。

        Args:
            job: 実行中のキャラクタージョブ。output_path に出力先を設定済み。
        """
        template = ALL_TEMPLATES.get(job.template_id, {})
        name = template.get("name", job.template_id)

        print(f"[CharGen] Compositing: {name} → Zone {job.zone_id} ({job.target_width}x{job.target_height})")

        Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)

        background_rel = template.get("background", "")
        background = str(self.templates_dir / background_rel) if background_rel else ""
        animated = job.animated_portrait_path or ""

        background_exists = bool(background) and Path(background).exists()
        animated_exists = bool(animated) and Path(animated).exists() and Path(animated).stat().st_size > 0

        if background_exists and animated_exists:
            # ffmpeg で背景動画にアニメーションをオーバーレイ合成
            pos = template.get("composite_position", {"x": 0.5, "y": 0.5, "scale": 0.4})
            filter_complex = (
                f"[1:v]scale=iw*{pos['scale']}:ih*{pos['scale']}[scaled];"
                f"[0:v][scaled]overlay=W*{pos['x']}-w/2:H*{pos['y']}-h/2[comp];"
                f"[comp]scale={job.target_width}:{job.target_height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={job.target_width}:{job.target_height}:(ow-iw)/2:(oh-ih)/2:black"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", background,
                "-i", animated,
                "-filter_complex", filter_complex,
                "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                "-an",
                job.output_path,
            ]
            print(f"[CharGen] Running ffmpeg composite: background={Path(background).name}, animated={Path(animated).name}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg composite failed (rc={process.returncode}): {err[-500:]}")
            print(f"[CharGen] ffmpeg composite done → {job.output_path}")

        else:
            # 背景またはアニメーションが存在しない場合: PIL で静止画フォールバック
            reason = []
            if not background_exists:
                reason.append(f"background not found ({background or 'not set'})")
            if not animated_exists:
                reason.append(f"animated portrait not found ({animated or 'not set'})")
            print(f"[CharGen] ffmpeg fallback ({', '.join(reason)}): generating PIL still image")
            await self._composite_animation_pil_fallback(job, template)

    async def _composite_memorial(self, job: CharacterJob) -> None:
        """メモリアルフォトを PIL で合成して静止画 JPEG として出力する。

        合成内容:
        1. スタイル変換済み写真 (または元写真) を中央に配置
        2. テーマカラーのグラデーション背景
        3. テーマに合わせた装飾ボーダー
        4. ゲスト名と日付テキストをオーバーレイ
        5. output_path (*.jpg) に JPEG で保存

        Args:
            job: 実行中のキャラクタージョブ。
                 job.styled_photo_path または job.photo_path を入力として使用。
        """
        import datetime

        from PIL import Image as PilImage
        from PIL import ImageDraw, ImageFilter, ImageFont

        print(f"[CharGen] Memorial composite: {job.guest_name} (theme={job.theme})")
        Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)

        # ── テーマカラー定義 ────────────────────────────────────
        THEME_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
            # (背景グラデ開始色, 背景グラデ終了色, アクセント色)
            "ocean":    ((10, 40, 80),    (30, 100, 160),  (100, 200, 240)),
            "forest":   ((20, 60, 20),    (50, 110, 50),   (130, 200, 80)),
            "fire":     ((80, 20, 0),     (160, 60, 0),    (255, 160, 40)),
            "ice":      ((180, 220, 240), (220, 240, 255),  (80, 160, 220)),
            "cosmos":   ((10, 5, 30),     (40, 20, 80),    (160, 100, 255)),
            "garden":   ((60, 30, 40),    (120, 60, 80),   (255, 160, 180)),
            "sunset":   ((80, 40, 10),    (160, 80, 30),   (255, 180, 80)),
            "zen":      ((40, 40, 35),    (80, 75, 65),    (200, 180, 140)),
            "gold":     ((20, 15, 5),     (50, 40, 10),    (220, 180, 60)),
            "space":    ((5, 5, 25),      (20, 10, 60),    (80, 160, 255)),
            "fairytale":((50, 20, 60),    (100, 50, 120),  (220, 160, 255)),
        }

        bg_start, bg_end, accent = THEME_COLORS.get(
            job.theme, ((20, 20, 40), (60, 60, 100), (160, 160, 220))
        )

        W, H = job.target_width, job.target_height  # 1380 × 1200

        # ── 背景: 縦グラデーション ────────────────────────────────
        canvas = PilImage.new("RGB", (W, H), bg_start)
        draw = ImageDraw.Draw(canvas)
        for y in range(H):
            t = y / H
            r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * t)
            g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * t)
            b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * t)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # ── ゲスト写真/スタイル変換画像を中央に配置 ──────────────
        photo_src = job.styled_photo_path or job.photo_path
        PHOTO_MAX_W = int(W * 0.55)
        PHOTO_MAX_H = int(H * 0.60)

        try:
            with PilImage.open(photo_src) as guest_img:
                guest_rgb = guest_img.convert("RGB")
                guest_rgb.thumbnail((PHOTO_MAX_W, PHOTO_MAX_H), PilImage.LANCZOS)
                gw, gh = guest_rgb.size

                # 淡い影
                shadow = PilImage.new("RGB", (gw + 12, gh + 12), bg_end)
                shadow_blurred = shadow.filter(ImageFilter.GaussianBlur(radius=8))
                px = (W - gw) // 2
                py = int(H * 0.12)
                canvas.paste(shadow_blurred, (px - 6, py + 6))
                canvas.paste(guest_rgb, (px, py))

                # 写真周囲のアクセントボーダー
                draw.rectangle(
                    [px - 3, py - 3, px + gw + 2, py + gh + 2],
                    outline=accent,
                    width=3,
                )
        except Exception as img_err:
            print(f"[CharGen] Memorial: failed to paste guest photo ({img_err}), skipping")
            py = int(H * 0.12)
            gh = int(H * 0.60)

        # ── ボーダー装飾 ──────────────────────────────────────────
        BORDER = 18
        draw.rectangle([BORDER, BORDER, W - BORDER, H - BORDER], outline=accent, width=2)
        draw.rectangle([BORDER + 6, BORDER + 6, W - BORDER - 6, H - BORDER - 6], outline=accent, width=1)

        # コーナー装飾
        corner_size = 30
        for cx, cy in [(BORDER, BORDER), (W - BORDER, BORDER), (BORDER, H - BORDER), (W - BORDER, H - BORDER)]:
            draw.ellipse([cx - corner_size // 2, cy - corner_size // 2, cx + corner_size // 2, cy + corner_size // 2], outline=accent, width=2)

        # ── テキストオーバーレイ ──────────────────────────────────
        # システムフォントのフォールバックチェーン
        FONT_CANDIDATES = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            for fp in FONT_CANDIDATES:
                if Path(fp).exists():
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        continue
            return ImageFont.load_default()

        # ゲスト名 (大きめ)
        text_y_base = py + gh + 30
        if job.guest_name:
            font_name = _load_font(52)
            name_text = job.guest_name
            bbox = draw.textbbox((0, 0), name_text, font=font_name)
            text_w = bbox[2] - bbox[0]
            text_x = (W - text_w) // 2
            # 影
            draw.text((text_x + 2, text_y_base + 2), name_text, font=font_name, fill=(0, 0, 0, 128))
            draw.text((text_x, text_y_base), name_text, font=font_name, fill=accent)
            text_y_base += 65

        # 日付
        font_date = _load_font(32)
        today = datetime.date.today().strftime("%Y.%m.%d")
        date_text = f"Thank you for your visit — {today}"
        bbox = draw.textbbox((0, 0), date_text, font=font_date)
        text_w = bbox[2] - bbox[0]
        text_x = (W - text_w) // 2
        draw.text((text_x + 1, text_y_base + 1), date_text, font=font_date, fill=(0, 0, 0, 100))
        draw.text((text_x, text_y_base), date_text, font=font_date, fill=(200, 200, 200))

        # ── 保存 ──────────────────────────────────────────────────
        canvas.save(job.output_path, format="JPEG", quality=90)
        print(f"[CharGen] Memorial saved: {job.output_path} ({W}x{H})")

        # メタデータ
        meta_path = Path(job.output_path).with_suffix(".json")
        metadata = {
            "job_id": job.job_id,
            "job_type": job.job_type.value,
            "label": "memorial_photo",
            "photo": job.photo_path,
            "styled_photo": job.styled_photo_path,
            "guest_name": job.guest_name,
            "theme": job.theme,
            "style": job.style_preset.value,
            "scenes": job.scenes,
            "status": "complete",
            "generated_at": time.time(),
        }
        with open(str(meta_path), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    async def _composite_animation_pil_fallback(self, job: CharacterJob, template: dict) -> None:
        """ffmpeg が使えない場合に PIL で静止画フォールバックを生成する。

        アニメーション動画の代わりに、スタイル変換済みキャラクター画像を
        黒背景に配置した静止画 JPEG を出力する。
        video_generator.py に倣い、最終出力は .jpg 拡張子で保存する。

        Args:
            job: 実行中のキャラクタージョブ
            template: テンプレート設定辞書
        """
        from PIL import Image as PilImage, ImageDraw

        W, H = job.target_width, job.target_height
        canvas = PilImage.new("RGB", (W, H), (0, 0, 0))

        photo_src = job.styled_photo_path or job.photo_path
        pos = template.get("composite_position", {"x": 0.5, "y": 0.5, "scale": 0.4})

        try:
            with PilImage.open(photo_src) as char_img:
                char_rgb = char_img.convert("RGB")
                max_w = int(W * pos["scale"])
                max_h = int(H * pos["scale"])
                char_rgb.thumbnail((max_w, max_h), PilImage.LANCZOS)
                cw, ch = char_rgb.size
                paste_x = int(W * pos["x"] - cw / 2)
                paste_y = int(H * pos["y"] - ch / 2)
                canvas.paste(char_rgb, (paste_x, paste_y))
        except Exception as e:
            print(f"[CharGen] PIL fallback: could not paste character image ({e})")

        # ゲスト名テキスト
        if job.guest_name:
            try:
                from PIL import ImageFont
                FONT_CANDIDATES = [
                    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/System/Library/Fonts/Arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
                font = ImageFont.load_default()
                for fp in FONT_CANDIDATES:
                    if Path(fp).exists():
                        try:
                            font = ImageFont.truetype(fp, 48)
                            break
                        except Exception:
                            continue
                draw = ImageDraw.Draw(canvas)
                text_pos = template.get("text_position", {"x": 0.5, "y": 0.85, "anchor": "center"})
                bbox = draw.textbbox((0, 0), job.guest_name, font=font)
                tw = bbox[2] - bbox[0]
                tx = int(W * text_pos["x"] - tw / 2)
                ty = int(H * text_pos["y"])
                draw.text((tx, ty), job.guest_name, font=font, fill=(255, 255, 255))
            except Exception as te:
                print(f"[CharGen] PIL fallback: could not draw text ({te})")

        # .mp4 パスを .jpg に変えて保存 (プレースホルダビデオの代替)
        fallback_path = Path(job.output_path).with_suffix(".jpg")
        canvas.save(str(fallback_path), format="JPEG", quality=85)
        job.output_path = str(fallback_path)
        print(f"[CharGen] PIL fallback still image saved: {fallback_path} ({W}x{H})")

    # ── ユーティリティ ───────────────────────────────────────────

    async def _create_placeholder_file(self, job: CharacterJob, output_path: str, label: str) -> None:
        """プレースホルダファイルとメタデータを作成"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        meta_path = Path(output_path).with_suffix('.json')
        metadata = {
            "job_id": job.job_id,
            "job_type": job.job_type.value,
            "label": label,
            "photo": job.photo_path,
            "guest_name": job.guest_name,
            "theme": job.theme,
            "template": job.template_id,
            "style": job.style_preset.value,
            "provider": job.provider.value,
            "status": "placeholder",
            "note": "実際の生成エンジン設定後に有効化されます",
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        Path(output_path).touch()
        print(f"[CharGen] Placeholder: {meta_path}")

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """ジョブステータスを取得"""
        job = self.jobs.get(job_id)
        if job:
            return asdict(job)
        return None

    @staticmethod
    def list_templates(category: Optional[str] = None) -> dict[str, dict]:
        """利用可能テンプレート一覧を取得

        Args:
            category: フィルターするカテゴリ (birthday/welcome/surprise/season)
                      Noneの場合は全テンプレートを返す
        """
        if category and category in CATEGORY_TEMPLATES:
            template_ids = CATEGORY_TEMPLATES[category]
            return {
                tid: {
                    "name": ALL_TEMPLATES[tid]["name"],
                    "category": ALL_TEMPLATES[tid]["category"],
                    "description": ALL_TEMPLATES[tid]["description"],
                    "duration": ALL_TEMPLATES[tid]["duration"],
                }
                for tid in template_ids
            }

        return {
            k: {
                "name": v["name"],
                "category": v["category"],
                "description": v["description"],
                "duration": v["duration"],
            }
            for k, v in ALL_TEMPLATES.items()
        }


# ====================================================================
# CLI実行
# ====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="汎用AIキャラクター生成サービス")
    subparsers = parser.add_subparsers(dest="command")

    # アバター生成
    avatar_parser = subparsers.add_parser("avatar", help="ウェルカム用アバター生成")
    avatar_parser.add_argument("--photo", required=True, help="ゲストの写真パス")
    avatar_parser.add_argument("--name", default="", help="ゲスト名")
    avatar_parser.add_argument("--theme", default="ocean", help="テーマ")
    avatar_parser.add_argument("--template", default="welcome_elegant", help="テンプレートID")
    avatar_parser.add_argument("--zone", type=int, default=1, help="投影先の区画番号 1-4")

    # アニメーション生成
    anim_parser = subparsers.add_parser("animation", help="キャラクターアニメーション生成")
    anim_parser.add_argument("--photo", required=True, help="ゲストの写真パス")
    anim_parser.add_argument("--name", default="", help="ゲスト名")
    anim_parser.add_argument("--template", default="birthday_cake", help="テンプレートID")
    anim_parser.add_argument("--zone", type=int, default=1, help="投影先の区画番号 1-4")
    anim_parser.add_argument("--provider", default="liveportrait", choices=["liveportrait", "hedra"])

    # メモリアル生成
    memorial_parser = subparsers.add_parser("memorial", help="メモリアルフォト生成")
    memorial_parser.add_argument("--photo", required=True, help="ゲストの写真パス")
    memorial_parser.add_argument("--name", default="", help="ゲスト名")
    memorial_parser.add_argument("--theme", default="ocean", help="テーマ")

    # テンプレート一覧
    tmpl_parser = subparsers.add_parser("templates", help="テンプレート一覧表示")
    tmpl_parser.add_argument("--category", default=None, help="カテゴリ (birthday/welcome/surprise/season)")

    args = parser.parse_args()
    service = CharacterGeneratorService()

    if args.command == "avatar":
        job = service.generate_welcome_avatar(
            args.photo, args.name, theme=args.theme,
            template_id=args.template, zone_id=args.zone,
        )
        asyncio.run(service.process(job))

    elif args.command == "animation":
        job = service.generate_birthday_animation(
            args.photo, args.name, template_id=args.template,
            zone_id=args.zone, provider=AnimationProvider(args.provider),
        )
        asyncio.run(service.process(job))

    elif args.command == "memorial":
        job = service.generate_memorial_photo(
            args.photo, args.name, theme=args.theme,
        )
        asyncio.run(service.process(job))

    elif args.command == "templates":
        templates = CharacterGeneratorService.list_templates(args.category)
        category_label = args.category or "全"
        print(f"\n=== {category_label}テンプレート一覧 ===\n")
        for tid, info in templates.items():
            print(f"  {tid}:")
            print(f"    名前: {info['name']}")
            print(f"    カテゴリ: {info['category']}")
            print(f"    説明: {info['description']}")
            print(f"    長さ: {info['duration']}秒\n")
    else:
        parser.print_help()
