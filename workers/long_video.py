"""長尺動画オーケストレーション (Seedance 2.0 + Xfade)

Seedance 2.0 は 1 クリップ 4-15 秒。任意尺の長い動画は「複数クリップを生成して
クロスフェードで連結」して作る。本モジュールはその方式を実装する:

  1. plan_segments(): 目標尺 → セグメント分割計画
  2. ClipGenerator プロトコル: 1 クリップ生成を抽象化 (provider 非依存)
  3. generate_long_video(): クリップ生成 (chain / parallel) → xfade で 1 本に組み立て

連続性 (最高品質) の核心:
  - chain 戦略: クリップ k の start_image に「クリップ k-1 の最終フレーム」を渡す。
    Seedance が前の絵から動きを継続するのでカット感が消える。さらに xfade で
    継ぎ目をぼかす → ほぼシームレスな長尺。
  - parallel 戦略 (最速): 全クリップを共通の reference image から並列生成し xfade。
    フレーム連続性は chain に劣るが生成が並列で速い。

provider 非依存: ClipGenerator を実装すれば Seedance / Kling / Runway いずれでも
同じオーケストレーションで長尺化できる。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Optional, Protocol

from workers.content_compositor import (
    CompositorError,
    extract_last_frame,
    xfade_concat,
)

# Seedance 2.0 のクリップ尺レンジ (models_explore より)
SEEDANCE_MIN_CLIP = 4
SEEDANCE_MAX_CLIP = 15
# 品質と動きの一貫性のスイートスポット。max(15s) は動きが破綻しやすいので既定 8s。
DEFAULT_CLIP_SECONDS = 8
DEFAULT_TRANSITION = 0.7  # xfade クロスフェード長 (秒)


@dataclass
class SegmentPlan:
    """1 セグメントの生成計画。"""
    index: int
    seconds: int
    # chain 戦略時: このセグメントの start_image にする「前クリップ最終フレーム」パス。
    # 先頭 (index=0) は None。
    start_image_path: Optional[str] = None
    # 全セグメント共通のテキスト指示 (シーンの prompt)。
    prompt: str = ""


@dataclass
class LongVideoPlan:
    total_seconds: int
    transition_seconds: float
    segments: list[SegmentPlan] = field(default_factory=list)

    @property
    def n_segments(self) -> int:
        return len(self.segments)

    @property
    def estimated_output_seconds(self) -> float:
        raw = sum(s.seconds for s in self.segments)
        return raw - (self.n_segments - 1) * self.transition_seconds if self.segments else 0.0


def plan_segments(
    total_seconds: int,
    prompt: str = "",
    clip_seconds: int = DEFAULT_CLIP_SECONDS,
    transition_seconds: float = DEFAULT_TRANSITION,
) -> LongVideoPlan:
    """目標尺をセグメント分割する。

    xfade で隣接 (N-1) 回 transition_seconds ぶん重なるので、出力尺 =
    Σ(clip) - (N-1)*T。目標尺に到達するよう必要セグメント数を逆算する。

    clip_seconds は Seedance レンジ [4,15] にクランプ。
    """
    clip = max(SEEDANCE_MIN_CLIP, min(SEEDANCE_MAX_CLIP, clip_seconds))
    if total_seconds <= clip:
        # 1 クリップで足りる
        return LongVideoPlan(
            total_seconds=total_seconds,
            transition_seconds=transition_seconds,
            segments=[SegmentPlan(index=0, seconds=max(SEEDANCE_MIN_CLIP, total_seconds), prompt=prompt)],
        )

    # N クリップの実効尺: N*clip - (N-1)*T >= total
    # → N >= (total - T) / (clip - T)
    eff = clip - transition_seconds
    if eff <= 0:
        raise CompositorError(
            f"transition_seconds {transition_seconds} >= clip_seconds {clip}; "
            f"クロスフェードがクリップより長くできません"
        )
    import math
    n = max(1, math.ceil((total_seconds - transition_seconds) / eff))

    segments = [
        SegmentPlan(index=i, seconds=clip, prompt=prompt)
        for i in range(n)
    ]
    return LongVideoPlan(
        total_seconds=total_seconds,
        transition_seconds=transition_seconds,
        segments=segments,
    )


class ClipGenerator(Protocol):
    """1 クリップを生成して動画ファイルパスを返す抽象。

    実装は Seedance(Higgsfield) / Kling / Runway 等。start_image_path が
    与えられたら i2v (前フレーム継続) で生成する。
    """

    async def __call__(
        self,
        *,
        index: int,
        prompt: str,
        seconds: int,
        start_image_path: Optional[str],
        output_path: str,
    ) -> str:
        ...


async def generate_long_video(
    plan: LongVideoPlan,
    generator: ClipGenerator,
    work_dir: str,
    output_path: str,
    strategy: str = "chain",
    transition: str = "fade",
) -> str:
    """長尺動画を生成する。

    Args:
        plan: plan_segments() の結果。
        generator: クリップ生成の実装 (provider 非依存)。
        work_dir: 中間クリップ / フレーム置き場。
        output_path: 最終長尺動画。
        strategy:
            "chain"   - 逐次生成。クリップ k の start_image = クリップ k-1 最終フレーム
                        (最高の連続性、生成は直列)。
            "parallel"- 全クリップを並列生成 (最速、連続性は xfade のみに依存)。
        transition: xfade トランジション種別。

    Returns:
        output_path
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    clip_paths: list[str] = []

    if strategy == "chain":
        prev_last_frame: Optional[str] = None
        for seg in plan.segments:
            clip_out = str(work / f"seg_{seg.index:03d}.mp4")
            await generator(
                index=seg.index,
                prompt=seg.prompt,
                seconds=seg.seconds,
                start_image_path=prev_last_frame,
                output_path=clip_out,
            )
            clip_paths.append(clip_out)
            # 次セグメントの開始フレーム用に最終フレームを抽出
            if seg.index < plan.n_segments - 1:
                frame_out = str(work / f"frame_{seg.index:03d}.png")
                prev_last_frame = await extract_last_frame(clip_out, frame_out)

    elif strategy == "parallel":
        async def _gen(seg: SegmentPlan) -> str:
            clip_out = str(work / f"seg_{seg.index:03d}.mp4")
            await generator(
                index=seg.index,
                prompt=seg.prompt,
                seconds=seg.seconds,
                start_image_path=seg.start_image_path,
                output_path=clip_out,
            )
            return clip_out

        clip_paths = await asyncio.gather(*[_gen(s) for s in plan.segments])
        clip_paths = list(clip_paths)

    else:
        raise CompositorError(f"unknown strategy: {strategy} (use 'chain' or 'parallel')")

    # xfade で連結
    return await xfade_concat(
        clip_paths,
        output_path,
        transition_duration=plan.transition_seconds,
        transition=transition,
    )
