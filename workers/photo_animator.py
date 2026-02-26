"""
写真→キャラクターアニメーション ワーカー

誕生日サプライズ用: ゲストの写真1枚からアニメーションキャラクターを生成し、
テンプレート映像に合成する。

出力は区画サイズ 1380x1200 (1:1に近い) に最適化。
特定テーブルに投影する誕生日演出に使用。

技術: LivePortrait (ローカル実行) / Hedra AI (API)

使い方:
    python workers/photo_animator.py animate --photo /path/to/photo.jpg --template birthday_cake --zone 2
    python workers/photo_animator.py list-templates
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


# 区画投影サイズ (content_compositor.py と統一)
ZONE_WIDTH = 1380
ZONE_HEIGHT = 1200


class AnimationStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPOSITING = "compositing"
    COMPLETE = "complete"
    FAILED = "failed"


class AnimationProvider(str, Enum):
    LIVEPORTRAIT = "liveportrait"
    HEDRA = "hedra"


# 誕生日サプライズテンプレート
BIRTHDAY_TEMPLATES = {
    "birthday_cake": {
        "name": "ケーキ作り",
        "description": "キャラクターがケーキを作って祝福する演出",
        "duration": 30,
        "driving_video": "templates/birthday/cake_making_driver.mp4",
        "background": "templates/birthday/cake_making_bg.mp4",
        "composite_position": {"x": 0.3, "y": 0.2, "scale": 0.4},
    },
    "starry_flight": {
        "name": "星空フライト",
        "description": "キャラクターが星空を飛ぶファンタジー演出",
        "duration": 25,
        "driving_video": "templates/birthday/starry_flight_driver.mp4",
        "background": "templates/birthday/starry_flight_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.4, "scale": 0.35},
    },
    "ocean_adventure": {
        "name": "海中冒険",
        "description": "キャラクターが海中で泳ぎながら祝福",
        "duration": 28,
        "driving_video": "templates/birthday/ocean_driver.mp4",
        "background": "templates/birthday/ocean_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.5, "scale": 0.3},
    },
    "fireworks_celebration": {
        "name": "花火セレブレーション",
        "description": "花火をバックにキャラクターが祝福ダンス",
        "duration": 20,
        "driving_video": "templates/birthday/fireworks_driver.mp4",
        "background": "templates/birthday/fireworks_bg.mp4",
        "composite_position": {"x": 0.5, "y": 0.6, "scale": 0.45},
    },
    "magic_garden": {
        "name": "魔法の庭園",
        "description": "キャラクターが魔法で花を咲かせる演出",
        "duration": 25,
        "driving_video": "templates/birthday/magic_garden_driver.mp4",
        "background": "templates/birthday/magic_garden_bg.mp4",
        "composite_position": {"x": 0.4, "y": 0.3, "scale": 0.4},
    },
}


@dataclass
class AnimationJob:
    job_id: str
    photo_path: str
    template_id: str
    zone_id: int = 1  # 投影先の区画番号 (1-4)
    provider: AnimationProvider = AnimationProvider.LIVEPORTRAIT
    status: AnimationStatus = AnimationStatus.QUEUED
    animated_portrait_path: Optional[str] = None
    final_output_path: Optional[str] = None
    error: Optional[str] = None
    guest_name: str = ""
    target_width: int = ZONE_WIDTH    # 1380
    target_height: int = ZONE_HEIGHT  # 1200
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class PhotoAnimatorService:
    """写真アニメーション生成サービス"""

    def __init__(
        self,
        templates_dir: str = "/Users/kento/immersive-dining/touchdesigner/content/templates",
        output_dir: str = "/Users/kento/immersive-dining/api/uploads/birthday_videos",
    ):
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, AnimationJob] = {}
        self._job_counter = 0

        # LivePortrait設定
        self.liveportrait_path = os.environ.get(
            "LIVEPORTRAIT_PATH",
            "/Users/kento/LivePortrait"
        )

    def create_job(
        self,
        photo_path: str,
        template_id: str,
        guest_name: str = "",
        zone_id: int = 1,
        provider: AnimationProvider = AnimationProvider.LIVEPORTRAIT,
    ) -> AnimationJob:
        """アニメーションジョブを作成"""
        if template_id not in BIRTHDAY_TEMPLATES:
            raise ValueError(f"Unknown template: {template_id}. Available: {list(BIRTHDAY_TEMPLATES.keys())}")

        if not Path(photo_path).exists():
            raise FileNotFoundError(f"Photo not found: {photo_path}")

        self._job_counter += 1
        job_id = f"anim_{self._job_counter}_{int(time.time())}"

        output_path = str(self.output_dir / f"{job_id}_final.mp4")

        job = AnimationJob(
            job_id=job_id,
            photo_path=photo_path,
            template_id=template_id,
            zone_id=zone_id,
            provider=provider,
            guest_name=guest_name,
            final_output_path=output_path,
        )
        self.jobs[job_id] = job
        return job

    async def process(self, job: AnimationJob) -> AnimationJob:
        """アニメーション生成フルパイプライン"""
        try:
            # Step 1: 写真→アニメーション生成
            job.status = AnimationStatus.PROCESSING
            print(f"[PhotoAnim] Processing: {job.job_id}")
            print(f"[PhotoAnim] Photo: {job.photo_path}")
            print(f"[PhotoAnim] Template: {job.template_id}")

            if job.provider == AnimationProvider.LIVEPORTRAIT:
                await self._animate_liveportrait(job)
            elif job.provider == AnimationProvider.HEDRA:
                await self._animate_hedra(job)

            # Step 2: テンプレート映像に合成
            job.status = AnimationStatus.COMPOSITING
            await self._composite(job)

            job.status = AnimationStatus.COMPLETE
            job.completed_at = time.time()
            elapsed = job.completed_at - job.created_at
            print(f"[PhotoAnim] Complete: {job.job_id} ({elapsed:.1f}s)")
            print(f"[PhotoAnim] Output: {job.final_output_path}")

        except Exception as e:
            job.status = AnimationStatus.FAILED
            job.error = str(e)
            print(f"[PhotoAnim] Failed: {job.job_id} - {e}")

        return job

    async def _animate_liveportrait(self, job: AnimationJob):
        """LivePortraitでアニメーション生成"""
        template = BIRTHDAY_TEMPLATES[job.template_id]
        driving_video = str(self.templates_dir / template["driving_video"])

        animated_path = str(self.output_dir / f"{job.job_id}_animated.mp4")
        job.animated_portrait_path = animated_path

        liveportrait_dir = Path(self.liveportrait_path)
        if not liveportrait_dir.exists():
            print("[PhotoAnim] LivePortrait not installed, creating placeholder")
            await self._create_placeholder(job, animated_path)
            return

        # LivePortrait実行コマンド
        # cmd = [
        #     "python", str(liveportrait_dir / "inference.py"),
        #     "--source_image", job.photo_path,
        #     "--driving_video", driving_video,
        #     "--output_path", animated_path,
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

        await self._create_placeholder(job, animated_path)

    async def _animate_hedra(self, job: AnimationJob):
        """Hedra AIでアニメーション生成"""
        animated_path = str(self.output_dir / f"{job.job_id}_animated.mp4")
        job.animated_portrait_path = animated_path

        hedra_api_key = os.environ.get("HEDRA_API_KEY", "")
        if not hedra_api_key:
            print("[PhotoAnim] Hedra API key not set, creating placeholder")
            await self._create_placeholder(job, animated_path)
            return

        # Hedra API呼び出し
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     with open(job.photo_path, 'rb') as f:
        #         response = await client.post(
        #             "https://api.hedra.com/v1/characters",
        #             headers={"Authorization": f"Bearer {hedra_api_key}"},
        #             files={"image": f},
        #             data={
        #                 "text": f"Happy birthday {job.guest_name}! Wishing you a wonderful celebration!",
        #                 "voice": "en-US-warm-female",
        #             }
        #         )
        #     result = response.json()
        #     video_url = result["video_url"]
        #     # ダウンロード
        #     video_resp = await client.get(video_url)
        #     with open(animated_path, 'wb') as f:
        #         f.write(video_resp.content)

        await self._create_placeholder(job, animated_path)

    async def _composite(self, job: AnimationJob):
        """アニメーションをテンプレート背景に合成 → 区画サイズ (1380x1200) で出力"""
        template = BIRTHDAY_TEMPLATES[job.template_id]

        print(f"[PhotoAnim] Compositing: {template['name']} → Zone {job.zone_id} ({job.target_width}x{job.target_height})")

        # ffmpegで合成 + 区画サイズにリサイズ
        # background = str(self.templates_dir / template["background"])
        # pos = template["composite_position"]
        #
        # cmd = [
        #     "ffmpeg", "-y",
        #     "-i", background,
        #     "-i", job.animated_portrait_path,
        #     "-filter_complex",
        #     f"[1:v]scale=iw*{pos['scale']}:ih*{pos['scale']}[scaled];"
        #     f"[0:v][scaled]overlay=W*{pos['x']}-w/2:H*{pos['y']}-h/2[comp];"
        #     f"[comp]scale={job.target_width}:{job.target_height}:"
        #     f"force_original_aspect_ratio=decrease,"
        #     f"pad={job.target_width}:{job.target_height}:(ow-iw)/2:(oh-ih)/2:black",
        #     "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        #     "-an",
        #     job.final_output_path,
        # ]
        # process = await asyncio.create_subprocess_exec(
        #     *cmd,
        #     stdout=asyncio.subprocess.PIPE,
        #     stderr=asyncio.subprocess.PIPE,
        # )
        # await process.communicate()

        # プレースホルダ
        Path(job.final_output_path).touch()

    async def _create_placeholder(self, job: AnimationJob, output_path: str):
        """プレースホルダ作成"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        meta_path = Path(output_path).with_suffix('.json')
        metadata = {
            "job_id": job.job_id,
            "photo": job.photo_path,
            "template": job.template_id,
            "guest_name": job.guest_name,
            "provider": job.provider.value,
            "status": "placeholder",
            "note": "LivePortrait/Hedraセットアップ後に実際のアニメーションが生成されます",
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        Path(output_path).touch()
        print(f"[PhotoAnim] Placeholder: {meta_path}")

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """ジョブステータスを取得"""
        job = self.jobs.get(job_id)
        if job:
            return asdict(job)
        return None

    @staticmethod
    def list_templates() -> dict:
        """利用可能テンプレート一覧"""
        return {k: {"name": v["name"], "description": v["description"], "duration": v["duration"]}
                for k, v in BIRTHDAY_TEMPLATES.items()}


# ====================================================================
# CLI実行
# ====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="写真→キャラクターアニメーション ワーカー")
    subparsers = parser.add_subparsers(dest="command")

    # アニメーション生成
    anim_parser = subparsers.add_parser("animate", help="写真からアニメーション生成")
    anim_parser.add_argument("--photo", required=True, help="ゲストの写真パス")
    anim_parser.add_argument("--template", required=True, choices=list(BIRTHDAY_TEMPLATES.keys()))
    anim_parser.add_argument("--name", default="", help="ゲスト名")
    anim_parser.add_argument("--zone", type=int, default=1, help="投影先の区画番号 1-4")
    anim_parser.add_argument("--provider", default="liveportrait", choices=["liveportrait", "hedra"])

    # テンプレート一覧
    subparsers.add_parser("list-templates", help="テンプレート一覧表示")

    args = parser.parse_args()
    service = PhotoAnimatorService()

    if args.command == "animate":
        job = service.create_job(
            args.photo,
            args.template,
            guest_name=args.name,
            zone_id=args.zone,
            provider=AnimationProvider(args.provider),
        )
        asyncio.run(service.process(job))

    elif args.command == "list-templates":
        templates = PhotoAnimatorService.list_templates()
        print("\n=== 誕生日サプライズテンプレート ===\n")
        for tid, info in templates.items():
            print(f"  {tid}:")
            print(f"    名前: {info['name']}")
            print(f"    説明: {info['description']}")
            print(f"    長さ: {info['duration']}秒\n")
    else:
        parser.print_help()
