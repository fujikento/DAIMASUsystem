"""コンテンツ QC pipeline — 生成 video が本番投影に耐えるか自動検証する。

検査項目:
  - ffprobe で実ファイル存在 / 再生可能性 / 解像度 / fps / 持続時間
  - 期待解像度との一致 (zone=1380x1200, unified=5520x1200 等)
  - 0 byte / 0 sec の placeholder 除外
  - 黒フレーム dominance (ffmpeg blackdetect で 90% 以上黒なら NG)
  - 音声 stream 数 (BGM trigger 用にあるかどうか、ない場合 warning)

呼び出し側:
  - storyboard generate-videos の _run() 末尾で全 scene を qc_video() に通す
  - QC NG なら scene.video_status = "qc_failed" に
  - 結果を event_logs に category='content_qc' で記録
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QcResult:
    ok: bool
    file_path: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    has_audio: bool = False
    file_size_bytes: int = 0
    black_dominance_percent: Optional[float] = None
    warnings: list[str] = None
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


def _have_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None


def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


async def _ffprobe_json(path: str) -> dict:
    """ffprobe streams + format を JSON で取得。"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode(errors='replace')[:300]}")
    return json.loads(stdout.decode())


async def _black_dominance(path: str, sample_seconds: float = 5.0) -> Optional[float]:
    """ffmpeg blackdetect で「黒判定された duration / 動画 duration」を返す。

    最初の `sample_seconds` 秒だけサンプリング (高速化)。
    1.0 = 全部黒、0.0 = 黒検出なし。検出失敗時は None。
    """
    if not _have_ffmpeg():
        return None
    cmd = [
        "ffmpeg", "-nostats", "-hide_banner", "-i", path,
        "-vf", "blackdetect=d=0.5:pix_th=0.10",
        "-t", str(sample_seconds), "-f", "null", "-",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        stderr_text = stderr.decode(errors="replace")
        # blackdetect は stderr に "black_start:0.5 black_end:1.2 black_duration:0.7" 形式
        total_black = 0.0
        for line in stderr_text.splitlines():
            if "black_duration:" in line:
                try:
                    dur = float(line.split("black_duration:")[-1].strip().split()[0])
                    total_black += dur
                except (ValueError, IndexError):
                    continue
        return min(1.0, total_black / sample_seconds) if sample_seconds > 0 else None
    except Exception as e:
        logger.warning("[content_qc] black_dominance failed: %s", e)
        return None


async def qc_video(
    path: str,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
    expected_duration_seconds: Optional[float] = None,
    duration_tolerance_pct: float = 0.20,
    max_black_dominance: float = 0.50,
    check_black: bool = True,
) -> QcResult:
    """生成 video の QC を 1 つの非同期呼び出しで全部やる。

    Args:
        path: 検査対象 mp4 のパス
        expected_width/height: 期待解像度。None なら検査しない
        expected_duration_seconds: 期待 duration。None なら検査しない
        duration_tolerance_pct: 持続時間の許容誤差 (例: 0.20 → ±20%)
        max_black_dominance: 0.0-1.0 黒フレーム占有率の許容上限 (0.50 → 半分以上黒なら NG)
        check_black: blackdetect を走らせるか (重いので skip 可能)

    Returns:
        QcResult — ok=True なら本番投入可。warnings/errors に詳細。
    """
    result = QcResult(ok=False, file_path=path)

    # 0. 存在チェック
    if not path or not os.path.exists(path):
        result.errors.append(f"file_not_found: {path}")
        return result
    if not os.path.isfile(path):
        result.errors.append(f"not_a_regular_file: {path}")
        return result

    result.file_size_bytes = os.path.getsize(path)
    if result.file_size_bytes < 1024:
        result.errors.append(f"file_too_small ({result.file_size_bytes} bytes — likely placeholder)")
        return result

    # 1. ffprobe で metadata
    if not _have_ffprobe():
        result.errors.append("ffprobe_not_installed")
        return result

    try:
        info = await _ffprobe_json(path)
    except Exception as e:
        result.errors.append(f"ffprobe_error: {e}")
        return result

    streams = info.get("streams", [])
    fmt = info.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    result.has_audio = bool(audio_streams)

    if not video_streams:
        result.errors.append("no_video_stream")
        return result

    v = video_streams[0]
    result.width = int(v.get("width") or 0)
    result.height = int(v.get("height") or 0)

    # duration は stream か format から (どちらかが空のことがある)
    duration = None
    try:
        duration = float(v.get("duration") or 0) or float(fmt.get("duration") or 0)
    except (ValueError, TypeError):
        duration = None
    result.duration_seconds = duration

    # fps (e.g. "30000/1001" → 29.97)
    try:
        from fractions import Fraction
        fps_str = v.get("r_frame_rate") or "0/1"
        result.fps = float(Fraction(fps_str))
    except Exception:
        result.fps = None

    # 2. 期待解像度との一致
    if expected_width and result.width != expected_width:
        result.errors.append(
            f"width_mismatch: got {result.width}, expected {expected_width}"
        )
    if expected_height and result.height != expected_height:
        result.errors.append(
            f"height_mismatch: got {result.height}, expected {expected_height}"
        )

    # 3. duration check
    if expected_duration_seconds and duration is not None and duration > 0:
        rel_err = abs(duration - expected_duration_seconds) / expected_duration_seconds
        if rel_err > duration_tolerance_pct:
            result.errors.append(
                f"duration_mismatch: got {duration:.2f}s, expected {expected_duration_seconds}s "
                f"(±{duration_tolerance_pct*100:.0f}%)"
            )

    if duration is None or duration < 0.1:
        result.errors.append(f"duration_invalid: {duration}")

    # 4. audio stream
    if not result.has_audio:
        result.warnings.append("no_audio_stream (acceptable but BGM trigger needs separate file)")

    # 5. black dominance (重いので最後 + opt-out 可能)
    if check_black:
        bd = await _black_dominance(path, sample_seconds=min(5.0, duration or 5.0))
        result.black_dominance_percent = round((bd or 0) * 100, 2) if bd is not None else None
        if bd is not None and bd > max_black_dominance:
            result.errors.append(
                f"black_dominant: {result.black_dominance_percent}% of sampled duration "
                f"is black (>{max_black_dominance*100:.0f}% threshold)"
            )

    result.ok = not result.errors
    return result
