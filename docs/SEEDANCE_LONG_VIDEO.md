# 長尺動画パイプライン (Seedance 2.0 + Xfade)

任意尺の長い動画を「Seedance 2.0 で短いクリップを複数生成 → 時間方向クロスフェード
(xfade) で 1 本に連結」して作る仕組み。DAIMASUsystem に組み込み済み。

## なぜこの方式か (最適・最速・最高品質の設計根拠)

Seedance 2.0 は 1 クリップ **4-15 秒**しか作れない (Higgsfield, `models_explore`)。
長尺は分割生成 + 連結が必須。品質の鍵は「継ぎ目をどう消すか」:

| 手法 | 連続性 | 速度 |
|---|---|---|
| 単純 concat (切替) | カット感が出る | 速い |
| **frame-chain + xfade** (採用) | ほぼシームレス | chain は直列 |
| parallel + xfade | 中 (xfade のみ) | 最速 (並列生成) |

**frame-chain (chain 戦略)** = クリップ k の `start_image` に「クリップ k-1 の最終フレーム」
を渡す。Seedance が前の絵から動きを継続するのでカット感が消え、さらに xfade
(既定 0.7s クロスフェード) で継ぎ目をぼかす。これが最高品質。
急ぐ場合は **parallel 戦略** (共通参照画像から全クリップ並列生成 → xfade)。

クリップ尺の既定は **8 秒**: 15s(最大)は動きが破綻しやすく、4s(最小)はクリップ数が
増えてコスト/継ぎ目が増えるため、品質×コストのスイートスポット。

出力尺 = Σ(各クリップ尺) − (N−1) × トランジション秒。
例: 8s × 6 本 − 5 × 0.7s = **44.5s**。

## 構成要素 (組み込み済み)

| ファイル | 役割 |
|---|---|
| `workers/content_compositor.py` | `xfade_concat()` 時間方向連結 / `extract_last_frame()` |
| `workers/long_video.py` | `plan_segments()` 分割計画 / `generate_long_video()` chain・parallel |
| `workers/seedance_provider.py` | `SeedanceClipGenerator` (fal / higgsfield backend) |
| `api/routers/generation.py` | `/long-video/plan` `/long-video/assemble` `/long-video` |

## 2 つの実行経路

### 経路 A — Claude + MCP (Higgsfield Seedance 2.0)  ※今すぐ使える主経路

Higgsfield Seedance 2.0 へのアクセスは Claude の MCP 経由が主。手順:

1. `/long-video/plan` で分割計画 + 概算クレジットを確認
   ```bash
   curl -X POST localhost:8000/api/generation/long-video/plan \
     -d '{"prompt":"...","total_seconds":40,"output_path":"touchdesigner/content/long/out.mp4"}'
   ```
2. Claude が各セグメントを MCP で生成 (frame-chain):
   - セグメント 0: `generate_video(model=seedance_2_0, prompt, duration=8, resolution=1080p, aspect_ratio=21:9)`
   - `job_status` で完了待ち → クリップ DL → `touchdesigner/content/...` に保存
   - 次セグメント: 前クリップの最終フレームを `medias:[{role:"start_image", value:<uuid/url>}]` に
3. 全クリップを backend で連結:
   ```bash
   curl -X POST localhost:8000/api/generation/long-video/assemble \
     -d '{"clip_paths":[".../seg0.mp4",".../seg1.mp4",...],"output_path":".../long.mp4","transition_seconds":0.7}'
   ```

> 注: クリップ・出力パスは `touchdesigner/content/` または `api/uploads/` 配下に限定
> (local file oracle 防止)。

### 経路 B — backend 完結 (fal / Higgsfield REST)

キー設定済みなら backend だけで生成〜連結まで:
```bash
curl -X POST localhost:8000/api/generation/long-video \
  -d '{"prompt":"...","total_seconds":40,"output_path":"touchdesigner/content/long/out.mp4","strategy":"chain"}'
```

backend 切替 (env):
- `SEEDANCE_BACKEND=fal` (既定) — `FAL_API_KEY` + fal の Bytedance Seedance モデル
  (`SEEDANCE_FAL_T2V_MODEL` / `SEEDANCE_FAL_I2V_MODEL` で model id 上書き可)
- `SEEDANCE_BACKEND=higgsfield` — `HIGGSFIELD_API_BASE` + `HIGGSFIELD_API_KEY`
  (REST パスは `HIGGSFIELD_GENERATE_PATH` / `HIGGSFIELD_JOB_PATH` で指定)

## コスト目安 (Higgsfield)

Seedance 2.0 1080p / std / 8s ≈ **72 credits/クリップ** (`get_cost` 実測)。
40s (6 クリップ) ≈ **432 credits**。`/long-video/plan` が概算を返す。

## テーブル投影との連携

`aspect_ratio=21:9` で生成すると、できた長尺を `crop_to_table_band()` で
5520×1200 のテーブル帯に整形でき、`/seat/content` で席別投影に流せる。

## 既知の制約

- Higgsfield 残高 0 のときは経路 A/B とも実生成不可 (`/long-video/plan` は常に可)。
- chain 戦略は直列生成のため尺に比例して時間がかかる。急ぐなら parallel。
- fal の Seedance model id は環境により異なるため env で上書きする想定。
