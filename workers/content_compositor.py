"""
コンテンツコンポジター v2

3つの合成パイプライン:

1. unified_stitch  — 21:9 × 2セグメント(L/R) → table_width x table_height シームレス合成
2. zone_fit        — 1:1正方形映像 → zone_width x zone_height 区画サイズにフィット
3. split           — 全体映像を3プロジェクター用に分割

使い方:
    # 統一モード: 左右セグメントを合成
    python workers/content_compositor.py stitch \\
        --left themes/ocean/unified/appetizer_left.mp4 \\
        --right themes/ocean/unified/appetizer_right.mp4 \\
        --output ocean_appetizer_table.mp4

    # 区画モード: 1:1映像を区画サイズにフィット
    python workers/content_compositor.py zone-fit \\
        --input themes/ocean/zone/appetizer_zone2.mp4 \\
        --output ocean_appetizer_z2.mp4

    # 3プロジェクター分割
    python workers/content_compositor.py split --input ocean_appetizer_table.mp4

    # テーブルレイアウト情報
    python workers/content_compositor.py info

精度上の要件 (audit 2026-05-16):
- ffmpeg/ffprobe 不在や失敗時は CompositorError を投げる。empty .touch() を
  成功扱いしない (投影側に黒フレームが流れない)。
- ffprobe の framerate は eval() ではなく fractions.Fraction で parse。
- 統一モード合成は xstack ではなく overlay+blend mask による真の crossfade。
  中央 seam を緩和する。
- 分割は各 ffmpeg の returncode + output 解像度を検証する。
- 解像度は module constants ではなく LayoutSpec として渡せる。
"""

import asyncio
import json
import shutil
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Optional


class CompositorError(RuntimeError):
    """Compositor が成功状態を保証できなかったときに投げる。"""


# ─── テーブル物理仕様 (デフォルト) ─────────────────────────────
DEFAULT_PJ_WIDTH = 1920
DEFAULT_PJ_HEIGHT = 1200
DEFAULT_PJ_COUNT = 3
DEFAULT_BLEND_OVERLAP = 120  # エッジブレンド重なり (px)
DEFAULT_ZONE_COUNT = 4

# 後方互換のための module constants (新規呼び出し側は LayoutSpec を渡すこと)
PJ_WIDTH = DEFAULT_PJ_WIDTH
PJ_HEIGHT = DEFAULT_PJ_HEIGHT
PJ_COUNT = DEFAULT_PJ_COUNT
BLEND_OVERLAP = DEFAULT_BLEND_OVERLAP
TABLE_WIDTH = (PJ_WIDTH * PJ_COUNT) - (BLEND_OVERLAP * (PJ_COUNT - 1))  # 5520
TABLE_HEIGHT = PJ_HEIGHT  # 1200
TABLE_ASPECT = TABLE_WIDTH / TABLE_HEIGHT  # 4.6
ZONE_COUNT = DEFAULT_ZONE_COUNT
ZONE_WIDTH = TABLE_WIDTH // ZONE_COUNT   # 1380
ZONE_HEIGHT = TABLE_HEIGHT               # 1200

# ─── 統一モード合成仕様 ──────────────────────────────────────────
# Runway 21:9 4Kアップスケール出力: 3840 x 1080
SEGMENT_W = 3840
SEGMENT_H = 1080
SEGMENT_OVERLAP_RATIO = 0.20  # 左右20%オーバーラップ

# ─── 区画モード仕様 ──────────────────────────────────────────────
# 1:1 4Kアップスケール出力: 2160 x 2160
ZONE_NATIVE = 2160


@dataclass(frozen=True)
class LayoutSpec:
    """投影レイアウト仕様。DB の ProjectionConfig を表す不変オブジェクト。"""

    pj_width: int = DEFAULT_PJ_WIDTH
    pj_height: int = DEFAULT_PJ_HEIGHT
    pj_count: int = DEFAULT_PJ_COUNT
    blend_overlap: int = DEFAULT_BLEND_OVERLAP
    zone_count: int = DEFAULT_ZONE_COUNT

    @property
    def table_width(self) -> int:
        return (self.pj_width * self.pj_count) - (self.blend_overlap * (self.pj_count - 1))

    @property
    def table_height(self) -> int:
        return self.pj_height

    @property
    def zone_width(self) -> int:
        return self.table_width // self.zone_count

    @property
    def zone_height(self) -> int:
        return self.pj_height

    def zone_box(self, zone_id: int) -> dict:
        """zone_id (1-indexed) の {x,y,w,h} を返す。"""
        if zone_id < 1 or zone_id > self.zone_count:
            raise ValueError(f"zone_id out of range: {zone_id} (1..{self.zone_count})")
        return {
            "x": self.zone_width * (zone_id - 1),
            "y": 0,
            "w": self.zone_width,
            "h": self.zone_height,
        }

    def pj_regions(self) -> list[dict]:
        """各プロジェクターの切り出し座標を返す。"""
        regions: list[dict] = []
        for i in range(self.pj_count):
            x = i * (self.pj_width - self.blend_overlap)
            regions.append({"name": f"pj{i + 1}", "x": x, "w": self.pj_width})
        return regions


DEFAULT_LAYOUT = LayoutSpec()


# ─── ゾーン座標 (後方互換) ──────────────────────────────────────
ZONES = {
    "all": {"x": 0, "y": 0, "w": TABLE_WIDTH, "h": TABLE_HEIGHT},
    "1": {"x": 0, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "2": {"x": ZONE_WIDTH, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "3": {"x": ZONE_WIDTH * 2, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "4": {"x": ZONE_WIDTH * 3, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
}

# プロジェクター切り出し座標 (後方互換)
PJ_REGIONS = DEFAULT_LAYOUT.pj_regions()


# ─── ffmpeg / ffprobe 検出 ───────────────────────────────────

def has_ffmpeg_sync() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


async def check_ffmpeg() -> bool:
    return has_ffmpeg_sync()


def _require_ffmpeg() -> None:
    if not has_ffmpeg_sync():
        raise CompositorError(
            "ffmpeg/ffprobe not found in PATH. Install via `brew install ffmpeg` "
            "(macOS) or `apt-get install ffmpeg`."
        )


def _parse_framerate(rate: str) -> float:
    """ffprobe の r_frame_rate ("30000/1001" 形式) を float fps に変換する。

    eval() は使わない。parse 失敗時は CompositorError を投げる。
    """
    try:
        frac = Fraction(rate)
        return float(frac)
    except (ZeroDivisionError, ValueError, TypeError) as e:
        raise CompositorError(f"Invalid framerate '{rate}': {e}")


async def get_video_info(path: str) -> dict:
    """ffprobe で映像情報を取得する。失敗時は CompositorError。"""
    _require_ffmpeg()
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise CompositorError(
            f"ffprobe failed for {path}: {stderr.decode(errors='replace')[-500:]}"
        )

    try:
        info = json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        raise CompositorError(f"ffprobe returned invalid JSON for {path}: {e}")

    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            return {
                "width": int(s["width"]),
                "height": int(s["height"]),
                "duration": float(s.get("duration", 0)),
                "fps": _parse_framerate(s.get("r_frame_rate", "30/1")),
            }
    raise CompositorError(f"No video stream found in {path}")


def _resolve_layout(layout: Optional[LayoutSpec]) -> LayoutSpec:
    if layout is None:
        return DEFAULT_LAYOUT
    return layout


# ====================================================================
# 1. 統一モード合成: 21:9 L + R → table_width x table_height
# ====================================================================

async def stitch_unified(
    left_path: str,
    right_path: str,
    output_path: str,
    layout: Optional[LayoutSpec] = None,
) -> str:
    """
    左右2セグメント (21:9, 各3840x1080) を合成して layout.table_width x table_height に。

    手順:
    1. 各セグメントを縦方向にスケール: 1080 → table_height
       → 各セグメントは scale_w x table_height になる
    2. 左セグメントの右端 overlap_ratio% と右セグメントの左端 overlap_ratio% を
       blend マスクで真の crossfade 合成 (xstack による単なる重ね合わせではない)
    3. crop して table_width x table_height に仕上げる
    """
    spec = _resolve_layout(layout)
    table_w = spec.table_width
    table_h = spec.table_height

    print(f"[Stitch] L: {left_path}")
    print(f"[Stitch] R: {right_path}")
    print(f"[Stitch] → {output_path}")
    print(f"[Stitch] target: {table_w}x{table_h}")

    _require_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 縦スケール比: table_height/SEGMENT_H
    scale_h = table_h
    scale_w = int(SEGMENT_W * (table_h / SEGMENT_H))

    # オーバーラップ幅 (px) — 合成後の幅が table_w になるように逆算
    # 合成後の幅 = 2 * scale_w - overlap_px = table_w が理想だが、
    # scale_w が大きい場合は overlap_px を増やし、それでも余る場合は crop で吸収。
    natural_overlap = 2 * scale_w - table_w
    overlap_px = max(int(scale_w * SEGMENT_OVERLAP_RATIO), natural_overlap)
    if overlap_px >= scale_w:
        raise CompositorError(
            f"Computed overlap {overlap_px}px exceeds segment width {scale_w}px; "
            f"check SEGMENT_OVERLAP_RATIO / segment resolution."
        )

    # filter graph:
    # [0] L → scale → put at x=0
    # [1] R → scale → overlay at x=scale_w - overlap_px with alpha gradient
    # ブレンドマスクは overlap 領域内で 0→1 に線形変化
    overlay_x = scale_w - overlap_px
    fade_w = overlap_px
    # 右映像の alpha チャンネルを overlap 部分でグラデーション、それ以外は1.0
    # geq の X は出力フレーム座標。0..fade_w が overlap 内。
    alpha_expr = (
        f"if(lt(X,{fade_w}),X/{fade_w},1)"
    )
    filter_complex = (
        f"[0:v]scale={scale_w}:{scale_h},setpts=PTS-STARTPTS[lscaled];"
        f"[1:v]scale={scale_w}:{scale_h},setpts=PTS-STARTPTS,format=yuva444p,"
        f"geq=lum='p(X,Y)':a='255*({alpha_expr})'[rfaded];"
        f"[lscaled][rfaded]overlay=x={overlay_x}:y=0:shortest=1:format=auto[merged];"
        f"[merged]crop={table_w}:{table_h}:0:0,format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", left_path,
        "-i", right_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise CompositorError(
            f"stitch_unified ffmpeg failed (rc={proc.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )

    # 出力検証: 解像度が想定通りか確認
    info = await get_video_info(output_path)
    if info["width"] != table_w or info["height"] != table_h:
        raise CompositorError(
            f"stitch output resolution mismatch: got {info['width']}x{info['height']}, "
            f"expected {table_w}x{table_h}"
        )

    print(f"[Stitch] Output: {output_path} ({info['width']}x{info['height']}, {info['duration']:.1f}s)")
    return output_path


# ====================================================================
# 2. 区画モード: 1:1 → zone_width x zone_height
# ====================================================================

async def fit_zone(
    input_path: str,
    output_path: str,
    layout: Optional[LayoutSpec] = None,
) -> str:
    """
    1:1 正方形映像 (2160x2160 4K) を区画サイズ zone_width x zone_height にフィット。

    手順:
    1. width = zone_width にスケール (アスペクト維持)
    2. 中央クロップで height = zone_height に切り出す
    """
    spec = _resolve_layout(layout)
    zone_w = spec.zone_width
    zone_h = spec.zone_height
    print(f"[ZoneFit] {input_path} → {output_path} ({zone_w}x{zone_h})")

    _require_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    filter_str = (
        f"scale={zone_w}:-1,"
        f"crop={zone_w}:{zone_h}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise CompositorError(
            f"fit_zone ffmpeg failed (rc={proc.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )

    info = await get_video_info(output_path)
    if info["width"] != zone_w or info["height"] != zone_h:
        raise CompositorError(
            f"zone-fit output resolution mismatch: got {info['width']}x{info['height']}, "
            f"expected {zone_w}x{zone_h}"
        )
    print(f"[ZoneFit] Output: {output_path} ({info['width']}x{info['height']})")
    return output_path


# ====================================================================
# 2b. ウルトラワイド帯 crop: 任意 aspect の動画 → table_width x table_height
# ====================================================================

async def crop_to_table_band(
    input_path: str,
    output_path: str,
    layout: Optional[LayoutSpec] = None,
) -> str:
    """任意 aspect の input 動画を、中央水平帯として table_width x table_height に
    crop + scale する。option ③ (MJ 32:9 still → Kling i2v → このメソッド) で使う。

    手順:
    1. ffprobe で input 解像度を取得
    2. input の aspect が target (≈4.6:1) より広いなら、左右クロップで target aspect に
       揃え、scale で table_width に伸ばす
    3. input の aspect が target より狭いなら、scale で table_width に揃え、
       中央 band を crop して table_height に
    4. 出力解像度を ffprobe で再検証

    target aspect の決定:
        target_w / target_h (デフォルト 5520 / 1200 = 4.6)

    Note: 入力が小さすぎる (例: 1920x1080 → 5520 にアップスケール) と画質劣化が
    顕著になる。Kling/Runway の生成解像度を考慮し、できるだけ 4K (3840x2160) で
    生成した上でこの crop を通すのが理想。
    """
    spec = _resolve_layout(layout)
    table_w = spec.table_width
    table_h = spec.table_height
    target_aspect = table_w / table_h  # 例: 4.6

    _require_ffmpeg()
    info = await get_video_info(input_path)
    src_w = info["width"]
    src_h = info["height"]
    src_aspect = src_w / src_h if src_h else 0
    if src_aspect <= 0:
        raise CompositorError(f"crop_to_table_band: invalid source dimensions {src_w}x{src_h}")

    print(f"[CropBand] {input_path} → {output_path}")
    print(f"[CropBand] source: {src_w}x{src_h} (aspect {src_aspect:.3f}), target: {table_w}x{table_h} (aspect {target_aspect:.3f})")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if src_aspect >= target_aspect:
        # 入力の方が横長 → 左右クロップで aspect を target に揃え、その後 scale
        crop_w = int(round(src_h * target_aspect))
        crop_x = max(0, (src_w - crop_w) // 2)
        filter_str = (
            f"crop={crop_w}:{src_h}:{crop_x}:0,"
            f"scale={table_w}:{table_h}:flags=lanczos"
        )
    else:
        # 入力の方が縦長 → scale で幅を table_w に合わせ、中央 band を crop
        scaled_h = int(round(table_w / src_aspect))
        crop_y = max(0, (scaled_h - table_h) // 2)
        filter_str = (
            f"scale={table_w}:{scaled_h}:flags=lanczos,"
            f"crop={table_w}:{table_h}:0:{crop_y}"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-an",
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise CompositorError(
            f"crop_to_table_band ffmpeg failed (rc={proc.returncode}): "
            f"{stderr.decode(errors='replace')[-500:]}"
        )

    out_info = await get_video_info(output_path)
    if out_info["width"] != table_w or out_info["height"] != table_h:
        raise CompositorError(
            f"crop_to_table_band output resolution mismatch: "
            f"got {out_info['width']}x{out_info['height']}, expected {table_w}x{table_h}"
        )
    print(f"[CropBand] Output: {output_path} ({out_info['width']}x{out_info['height']}, {out_info['duration']:.1f}s)")
    return output_path


# ====================================================================
# 3. プロジェクター分割: 全体映像 → PJ1/PJ2/PJ3
# ====================================================================

async def split_for_projectors(
    input_path: str,
    output_dir: str,
    layout: Optional[LayoutSpec] = None,
) -> list[str]:
    """全体映像を pj_count 台プロジェクター用に分割（エッジブレンド重なり含む）

    各 ffmpeg の returncode を検証し、出力解像度を ffprobe で再確認する。
    1台でも失敗すれば CompositorError を投げる。
    """
    _require_ffmpeg()
    spec = _resolve_layout(layout)
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    outputs: list[str] = []
    stem = Path(input_path).stem
    errors: list[str] = []

    for region in spec.pj_regions():
        output_path = str(output_dir_path / f"{stem}_{region['name']}.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"crop={region['w']}:{spec.table_height}:{region['x']}:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            errors.append(
                f"{region['name']}: ffmpeg rc={proc.returncode} – "
                f"{stderr.decode(errors='replace')[-300:]}"
            )
            continue

        try:
            info = await get_video_info(output_path)
        except CompositorError as e:
            errors.append(f"{region['name']}: ffprobe failed – {e}")
            continue

        if info["width"] != region["w"] or info["height"] != spec.table_height:
            errors.append(
                f"{region['name']}: resolution mismatch "
                f"got {info['width']}x{info['height']}, "
                f"expected {region['w']}x{spec.table_height}"
            )
            continue

        outputs.append(output_path)
        print(f"[Split] {region['name']}: x={region['x']}, w={region['w']} → {output_path}")

    if errors:
        raise CompositorError(
            "split_for_projectors had failures:\n  - " + "\n  - ".join(errors)
        )
    return outputs


# ====================================================================
# レイアウト情報
# ====================================================================

def print_layout_info(layout: Optional[LayoutSpec] = None):
    spec = _resolve_layout(layout)
    table_w = spec.table_width
    table_h = spec.table_height
    aspect = table_w / table_h
    zone_w = spec.zone_width
    zone_h = spec.zone_height
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║          イマーシブダイニング テーブルレイアウト v2                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  テーブル全長: 8,126mm （{spec.zone_count}区画 × 2名）                            ║
║  投影解像度:   {table_w} x {table_h} px                            ║
║  アスペクト比: {aspect:.1f}:1 (超ワイド)                              ║
║                                                                  ║
║  Zone size:    {zone_w} x {zone_h} px × {spec.zone_count} 区画                  ║
║                                                                  ║
║  Projector Coverage ({spec.blend_overlap}px overlap):                            ║
""")
    for r in spec.pj_regions():
        print(f"║  [{r['name']:>3}: {r['x']}–{r['x']+r['w']}]")
    print("╚══════════════════════════════════════════════════════════════════╝")


# ====================================================================
# CLI
# ====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="コンテンツコンポジター v2")
    subparsers = parser.add_subparsers(dest="command")

    stitch_parser = subparsers.add_parser("stitch", help="21:9 L+R → table_width x table_height 合成")
    stitch_parser.add_argument("--left", required=True, help="左セグメント映像")
    stitch_parser.add_argument("--right", required=True, help="右セグメント映像")
    stitch_parser.add_argument("--output", required=True, help="出力パス")

    zone_parser = subparsers.add_parser("zone-fit", help="1:1 → zone_width x zone_height フィット")
    zone_parser.add_argument("--input", required=True)
    zone_parser.add_argument("--output", required=True)

    split_parser = subparsers.add_parser("split", help="3プロジェクター分割")
    split_parser.add_argument("--input", required=True)
    split_parser.add_argument("--output-dir", default="/tmp/pj_split")

    subparsers.add_parser("info", help="レイアウト情報表示")

    args = parser.parse_args()

    try:
        if args.command == "stitch":
            asyncio.run(stitch_unified(args.left, args.right, args.output))
        elif args.command == "zone-fit":
            asyncio.run(fit_zone(args.input, args.output))
        elif args.command == "split":
            asyncio.run(split_for_projectors(args.input, args.output_dir))
        elif args.command == "info":
            print_layout_info()
        else:
            parser.print_help()
    except CompositorError as e:
        print(f"[Compositor] ERROR: {e}")
        raise SystemExit(2)
