"""
コンテンツコンポジター v2

2つの合成パイプライン:

1. unified_stitch  — 21:9 × 2セグメント(L/R) → 5520x1200 シームレス合成
2. zone_fit        — 1:1正方形映像 → 1380x1200 区画サイズにフィット
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
"""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ─── テーブル物理仕様 ─────────────────────────────────────────────
PJ_WIDTH = 1920
PJ_HEIGHT = 1200
PJ_COUNT = 3
BLEND_OVERLAP = 120  # エッジブレンド重なり (px)

# 実効投影解像度
TABLE_WIDTH = (PJ_WIDTH * PJ_COUNT) - (BLEND_OVERLAP * (PJ_COUNT - 1))  # 5520
TABLE_HEIGHT = PJ_HEIGHT  # 1200
TABLE_ASPECT = TABLE_WIDTH / TABLE_HEIGHT  # 4.6

# 区画 (4テーブル)
ZONE_COUNT = 4
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

# ─── ゾーン座標 ──────────────────────────────────────────────────
ZONES = {
    "all": {"x": 0, "y": 0, "w": TABLE_WIDTH, "h": TABLE_HEIGHT},
    "1": {"x": 0, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "2": {"x": ZONE_WIDTH, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "3": {"x": ZONE_WIDTH * 2, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
    "4": {"x": ZONE_WIDTH * 3, "y": 0, "w": ZONE_WIDTH, "h": ZONE_HEIGHT},
}

# プロジェクター切り出し座標
PJ_REGIONS = [
    {"name": "pj1", "x": 0, "w": PJ_WIDTH},
    {"name": "pj2", "x": PJ_WIDTH - BLEND_OVERLAP, "w": PJ_WIDTH},
    {"name": "pj3", "x": (PJ_WIDTH - BLEND_OVERLAP) * 2, "w": PJ_WIDTH},
]


async def check_ffmpeg() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def get_video_info(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        info = json.loads(stdout.decode())
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                return {
                    "width": int(s["width"]),
                    "height": int(s["height"]),
                    "duration": float(s.get("duration", 0)),
                    "fps": eval(s.get("r_frame_rate", "30/1")),
                }
    except Exception as e:
        print(f"[Compositor] ffprobe error: {e}")
    return {"width": 0, "height": 0, "duration": 0, "fps": 30}


# ====================================================================
# 1. 統一モード合成: 21:9 L + R → 5520x1200
# ====================================================================

async def stitch_unified(
    left_path: str,
    right_path: str,
    output_path: str,
) -> str:
    """
    左右2セグメント (21:9, 各3840x1080) を合成して 5520x1200 にする。

    手順:
    1. 各セグメントを縦方向にスケール: 1080 → 1200 (+11%)
       → 各セグメントは 4267x1200 になる
    2. 左セグメントの右端20%と右セグメントの左端20%をクロスフェードブレンド
    3. 合成して 5520x1200 に仕上げ
    """
    print(f"[Stitch] L: {left_path}")
    print(f"[Stitch] R: {right_path}")
    print(f"[Stitch] → {output_path}")

    has_ffmpeg = await check_ffmpeg()
    if not has_ffmpeg:
        return await _create_stitch_metadata(left_path, right_path, output_path)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # 縦スケール比: 1200/1080 = 1.111
    scale_h = TABLE_HEIGHT
    scale_w = int(SEGMENT_W * (TABLE_HEIGHT / SEGMENT_H))  # 4267

    # オーバーラップ幅 (px)
    overlap_px = int(scale_w * SEGMENT_OVERLAP_RATIO)  # ~853px

    # 合成後の幅: 2 × scale_w - overlap_px
    # = 2 × 4267 - 853 = 7681 → crop to 5520
    # 実際は: 左の非重複部 + ブレンド部 + 右の非重複部 = 5520
    left_unique = (TABLE_WIDTH - overlap_px) // 2     # 左の固有部分
    right_unique = TABLE_WIDTH - left_unique - overlap_px

    # ffmpegフィルター:
    # [0] left → scale to scale_w x 1200
    # [1] right → scale to scale_w x 1200
    # [0scaled] crop left portion (left_unique + overlap_px) wide
    # [1scaled] crop right portion from start
    # blend overlap region with crossfade
    filter_complex = (
        f"[0:v]scale={scale_w}:{scale_h}[lscaled];"
        f"[1:v]scale={scale_w}:{scale_h}[rscaled];"
        # 左から必要な幅を切り出し
        f"[lscaled]crop={left_unique + overlap_px}:{scale_h}:0:0[lcrop];"
        # 右から必要な幅を切り出し (右端から)
        f"[rscaled]crop={overlap_px + right_unique}:{scale_h}:{scale_w - overlap_px - right_unique}:0[rcrop];"
        # xfade でオーバーレイ (横方向オーバーラップ)
        f"[lcrop][rcrop]xstack=inputs=2:layout=0_0|{left_unique}_0[wide];"
        # 最終的に TABLE_WIDTH にクロップ
        f"[wide]crop={TABLE_WIDTH}:{TABLE_HEIGHT}:0:0"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", left_path,
        "-i", right_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-an",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        print(f"[Stitch] ffmpeg error: {stderr.decode()[-500:]}")
        return await _create_stitch_metadata(left_path, right_path, output_path)

    print(f"[Stitch] Output: {output_path} ({TABLE_WIDTH}x{TABLE_HEIGHT})")
    return output_path


async def _create_stitch_metadata(left: str, right: str, output: str) -> str:
    meta = {
        "left_segment": left,
        "right_segment": right,
        "target": f"{TABLE_WIDTH}x{TABLE_HEIGHT}",
        "method": "21:9 x2 → stitch with 20% overlap → 5520x1200",
        "status": "metadata_only",
        "note": "ffmpegインストール後に実行: brew install ffmpeg",
    }
    meta_path = Path(output).with_suffix('.json')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    Path(output).touch()
    print(f"[Stitch] Metadata: {meta_path}")
    return output


# ====================================================================
# 2. 区画モード: 1:1 → 1380x1200
# ====================================================================

async def fit_zone(input_path: str, output_path: str) -> str:
    """
    1:1 正方形映像 (2160x2160 4K) を区画サイズ 1380x1200 にフィット。

    手順:
    1. 中心から 1380x1200 相当の領域をクロップ
       (2160から → crop 1380:1200 の比率でスケール)
    2. まず 2160x2160 → 1380 幅にスケール → 高さ 1380 → crop 1200
    """
    print(f"[ZoneFit] {input_path} → {output_path}")

    has_ffmpeg = await check_ffmpeg()
    if not has_ffmpeg:
        return await _create_zone_metadata(input_path, output_path)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # scale to width=1380, then crop height to 1200 (center crop)
    filter_str = (
        f"scale={ZONE_WIDTH}:-1,"
        f"crop={ZONE_WIDTH}:{ZONE_HEIGHT}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-an",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        print(f"[ZoneFit] ffmpeg error: {stderr.decode()[-500:]}")
        return await _create_zone_metadata(input_path, output_path)

    print(f"[ZoneFit] Output: {output_path} ({ZONE_WIDTH}x{ZONE_HEIGHT})")
    return output_path


async def _create_zone_metadata(input_path: str, output: str) -> str:
    meta = {
        "input": input_path,
        "target": f"{ZONE_WIDTH}x{ZONE_HEIGHT}",
        "method": "1:1 (2160x2160) → scale to 1380w → center crop 1380x1200",
        "status": "metadata_only",
    }
    meta_path = Path(output).with_suffix('.json')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    Path(output).touch()
    return output


# ====================================================================
# 3. プロジェクター分割: 全体映像 → PJ1/PJ2/PJ3
# ====================================================================

async def split_for_projectors(input_path: str, output_dir: str) -> list[str]:
    """5520x1200 全体映像を 3台プロジェクター用に分割（エッジブレンド重なり含む）"""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    outputs = []
    stem = Path(input_path).stem
    has_ffmpeg = await check_ffmpeg()

    for region in PJ_REGIONS:
        output_path = str(output_dir_path / f"{stem}_{region['name']}.mp4")

        if has_ffmpeg:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", f"crop={region['w']}:{TABLE_HEIGHT}:{region['x']}:0",
                "-c:v", "libx264", "-preset", "fast", "-crf", "16",
                output_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        else:
            Path(output_path).touch()

        outputs.append(output_path)
        print(f"[Split] {region['name']}: x={region['x']}, w={region['w']} → {output_path}")

    return outputs


# ====================================================================
# レイアウト情報
# ====================================================================

def print_layout_info():
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║          イマーシブダイニング テーブルレイアウト v2                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  テーブル全長: 8,126mm （4区画 × 2名）                            ║
║  投影解像度:   {TABLE_WIDTH} x {TABLE_HEIGHT} px                            ║
║  アスペクト比: {TABLE_ASPECT:.1f}:1 (超ワイド)                              ║
║                                                                  ║
║  ┌──────────┬──────────┬──────────┬──────────┐                   ║
║  │  Zone 1  │  Zone 2  │  Zone 3  │  Zone 4  │                   ║
║  │{ZONE_WIDTH}x{ZONE_HEIGHT} │{ZONE_WIDTH}x{ZONE_HEIGHT} │{ZONE_WIDTH}x{ZONE_HEIGHT} │{ZONE_WIDTH}x{ZONE_HEIGHT} │                   ║
║  └──────────┴──────────┴──────────┴──────────┘                   ║
║                                                                  ║
║  Projector Coverage ({BLEND_OVERLAP}px overlap):                            ║
║  [PJ1: 0—{PJ_WIDTH}] [PJ2: {PJ_WIDTH-BLEND_OVERLAP}—{PJ_WIDTH*2-BLEND_OVERLAP}] [PJ3: {(PJ_WIDTH-BLEND_OVERLAP)*2}—{TABLE_WIDTH+BLEND_OVERLAP}]      ║
║                                                                  ║
║  ─── 生成戦略 ───────────────────────────────────────────────    ║
║                                                                  ║
║  統一モード (unified):                                            ║
║    Runway 21:9 × 2セグメント(L+R) → 4K upscale                   ║
║    → 3840x1080 × 2 → stitch → {TABLE_WIDTH}x{TABLE_HEIGHT}                  ║
║                                                                  ║
║  区画モード (zone):                                               ║
║    1:1 正方形 → 4K upscale → 2160x2160                           ║
║    → crop {ZONE_WIDTH}x{ZONE_HEIGHT}                                        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


# ====================================================================
# CLI
# ====================================================================
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="コンテンツコンポジター v2")
    subparsers = parser.add_subparsers(dest="command")

    # 統一モード合成
    stitch_parser = subparsers.add_parser("stitch", help="21:9 L+R → 5520x1200 合成")
    stitch_parser.add_argument("--left", required=True, help="左セグメント映像")
    stitch_parser.add_argument("--right", required=True, help="右セグメント映像")
    stitch_parser.add_argument("--output", required=True, help="出力パス")

    # 区画モードフィット
    zone_parser = subparsers.add_parser("zone-fit", help="1:1 → 1380x1200 フィット")
    zone_parser.add_argument("--input", required=True)
    zone_parser.add_argument("--output", required=True)

    # 3PJ分割
    split_parser = subparsers.add_parser("split", help="3プロジェクター分割")
    split_parser.add_argument("--input", required=True)
    split_parser.add_argument("--output-dir", default="/tmp/pj_split")

    # レイアウト
    subparsers.add_parser("info", help="レイアウト情報表示")

    args = parser.parse_args()

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
