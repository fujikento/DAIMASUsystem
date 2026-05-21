"""Seedance クリップ生成プロバイダ (long_video.ClipGenerator 実装)

長尺パイプライン (workers/long_video.py) に差し込むクリップ生成器。
1 クリップ (4-15s) を生成して mp4 パスを返す。chain 戦略では start_image_path
(前クリップ最終フレーム) を i2v のシードに使い、フレーム連続性を作る。

provider の実体は env で切替:
  - SEEDANCE_BACKEND=fal    (既定): fal.ai 経由で Bytedance Seedance を呼ぶ
      * SEEDANCE_FAL_T2V_MODEL / SEEDANCE_FAL_I2V_MODEL で model id 指定可
      * 既定は fal-ai/bytedance/seedance の pro text/image-to-video
  - SEEDANCE_BACKEND=higgsfield : Higgsfield REST を直接呼ぶ (要 HIGGSFIELD_API_KEY
      + HIGGSFIELD_API_BASE)。Seedance 2.0 を使う場合はこちら。

注: Higgsfield Seedance 2.0 は現状 Claude の MCP 経由が主アクセス路。バックエンド
から直接叩く場合は REST エンドポイントとキーを env で与えること
(docs/SEEDANCE_LONG_VIDEO.md 参照)。
"""

from __future__ import annotations

import asyncio
import os
import time
import urllib.request
from pathlib import Path
from typing import Optional


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class SeedanceClipGenerator:
    """long_video.ClipGenerator 互換のクリップ生成器。"""

    def __init__(
        self,
        *,
        resolution: str = "1080p",
        aspect_ratio: str = "21:9",
        mode: str = "std",
        backend: Optional[str] = None,
    ) -> None:
        self.resolution = resolution
        self.aspect_ratio = aspect_ratio
        self.mode = mode
        self.backend = (backend or _env("SEEDANCE_BACKEND", "fal")).lower()

    async def __call__(
        self,
        *,
        index: int,
        prompt: str,
        seconds: int,
        start_image_path: Optional[str],
        output_path: str,
    ) -> str:
        if self.backend == "higgsfield":
            return await self._generate_higgsfield(
                prompt=prompt, seconds=seconds,
                start_image_path=start_image_path, output_path=output_path,
            )
        return await self._generate_fal(
            prompt=prompt, seconds=seconds,
            start_image_path=start_image_path, output_path=output_path,
        )

    # ── fal.ai backend ────────────────────────────────────────────
    async def _generate_fal(
        self, *, prompt: str, seconds: int,
        start_image_path: Optional[str], output_path: str,
    ) -> str:
        api_key = _env("FAL_API_KEY")
        if not api_key:
            raise RuntimeError("FAL_API_KEY 未設定 — Seedance(fal) を使うには必要です")
        try:
            import fal_client
        except ImportError as e:
            raise RuntimeError("fal-client 未インストール: pip install fal-client") from e
        os.environ["FAL_KEY"] = api_key

        if start_image_path:
            model = _env(
                "SEEDANCE_FAL_I2V_MODEL",
                "fal-ai/bytedance/seedance/v1/pro/image-to-video",
            )
            # 前フレームを data URI でシードに
            import base64
            with open(start_image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            args = {
                "prompt": prompt,
                "image_url": f"data:image/png;base64,{b64}",
                "duration": str(seconds),
                "resolution": self.resolution,
                "aspect_ratio": self.aspect_ratio,
            }
        else:
            model = _env(
                "SEEDANCE_FAL_T2V_MODEL",
                "fal-ai/bytedance/seedance/v1/pro/text-to-video",
            )
            args = {
                "prompt": prompt,
                "duration": str(seconds),
                "resolution": self.resolution,
                "aspect_ratio": self.aspect_ratio,
            }

        loop = asyncio.get_running_loop()

        def _call():
            return fal_client.subscribe(model, arguments=args)

        result = await asyncio.wait_for(
            loop.run_in_executor(None, _call), timeout=600.0
        )
        video = result.get("video") or {}
        url = video.get("url")
        if not url:
            raise RuntimeError(f"fal Seedance returned no video url: {result}")
        await self._download(url, output_path)
        return output_path

    # ── Higgsfield REST backend ───────────────────────────────────
    async def _generate_higgsfield(
        self, *, prompt: str, seconds: int,
        start_image_path: Optional[str], output_path: str,
    ) -> str:
        """Higgsfield Seedance 2.0 を REST で生成する。

        submit → poll job → download の典型フロー。エンドポイントは env で与える
        (固定で焼かない):
          HIGGSFIELD_API_BASE  例) https://api.higgsfield.ai
          HIGGSFIELD_API_KEY
          HIGGSFIELD_GENERATE_PATH (既定 /v1/videos)
          HIGGSFIELD_JOB_PATH      (既定 /v1/jobs/{job_id})
        """
        base = _env("HIGGSFIELD_API_BASE")
        key = _env("HIGGSFIELD_API_KEY")
        if not base or not key:
            raise RuntimeError(
                "HIGGSFIELD_API_BASE / HIGGSFIELD_API_KEY 未設定 — "
                "Higgsfield Seedance 2.0 を backend から直接使うには必要です。"
                "Claude の MCP 経由なら docs/SEEDANCE_LONG_VIDEO.md の手順を使う。"
            )
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx 未インストール") from e

        gen_path = _env("HIGGSFIELD_GENERATE_PATH", "/v1/videos")
        job_path = _env("HIGGSFIELD_JOB_PATH", "/v1/jobs/{job_id}")
        payload: dict = {
            "model": "seedance_2_0",
            "prompt": prompt,
            "duration": seconds,
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "mode": self.mode,
        }
        if start_image_path:
            payload["start_image_path"] = start_image_path

        headers = {"Authorization": f"Bearer {key}"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0)) as client:
            r = await client.post(f"{base}{gen_path}", json=payload, headers=headers)
            r.raise_for_status()
            job_id = r.json().get("job_id") or r.json().get("id")
            if not job_id:
                raise RuntimeError(f"Higgsfield submit returned no job id: {r.text[:200]}")

            # poll
            deadline = time.time() + 600
            url = None
            while time.time() < deadline:
                jp = job_path.format(job_id=job_id)
                jr = await client.get(f"{base}{jp}", headers=headers)
                jr.raise_for_status()
                data = jr.json()
                status = data.get("status")
                if status in ("completed", "succeeded", "done"):
                    url = (data.get("result") or {}).get("url") or data.get("url")
                    break
                if status in ("failed", "error"):
                    raise RuntimeError(f"Higgsfield job failed: {data}")
                await asyncio.sleep(data.get("poll_after_seconds", 5))
            if not url:
                raise RuntimeError("Higgsfield job did not complete in time")
        await self._download(url, output_path)
        return output_path

    # ── shared download ───────────────────────────────────────────
    async def _download(self, url: str, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()

        def _dl():
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()

        data = await loop.run_in_executor(None, _dl)
        if len(data) < 1000:
            raise RuntimeError(f"downloaded clip too small ({len(data)} bytes): {url}")
        with open(output_path, "wb") as f:
            f.write(data)
