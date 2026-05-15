# ULTRA_WIDE_I2V ワークフロー (option ③)

audit 2026-05-16 以降、Runway/Kling/Pika はいずれも 21:9 を直接出力できず、unified モードは
事実上ブロックされた状態だった。本ドキュメントは、**事前生成した 32:9 (≈4.6:1) 静止画を
image-to-video の入力として投入し、後段で table 解像度 (5520×1200) に整形する**
代替パイプライン (option ③) の駆動方法をまとめる。

ここでカバーする範囲: 1 コース分 (1 シーン) の動画生成 のみ。
複数コース一括 (batch) は今のところ手動で 1 ジョブずつ叩く。

---

## 全体フロー

```
┌────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│ MJ / Flux で    │    │ Kling i2v          │    │ ffmpeg crop_to_     │
│ 32:9 静止画生成 │ →  │ (fal.ai 推奨)       │ →  │ table_band で       │
│ --ar 32:9       │    │ 16:9 出力          │    │ 5520x1200 に整形    │
└────────────────┘    └────────────────────┘    └─────────────────────┘
       手動                 API呼び出し                   API呼び出し
```

---

## 1. 静止画生成 (手動)

### Midjourney (推奨)

```
/imagine prompt: <theme prompt>, ultra-wide cinematic top-down composition,
designed for projection on a long table surface, no horizon line,
seamless horizontal flow, 8K detail --ar 32:9 --v 6
```

ポイント:
- `--ar 32:9` で 32:9 アスペクトを明示
- 被写体は中央の水平 4.6:1 band 内に収める
- 上下の余白は **どのみち crop で捨てる前提** で広めに取って構図安定を狙う
- 出力を `/Users/mr.fu/DAIMASUsystem/api/uploads/seeds/<theme>_<course>_uw.jpg` などに保存

### Flux Pro 1.1 (fal.ai 経由でも生成可)

```bash
curl -X POST 'https://fal.run/fal-ai/flux-pro/v1.1' \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "<theme prompt> ultra-wide cinematic top-down view",
    "image_size": {"width": 1920, "height": 540},
    "num_inference_steps": 28
  }'
```

`image_size` を 1920×540 (≒32:9) などで指定できる。

---

## 2. i2v 生成 + crop (API 経由)

サーバ起動:
```bash
cd /Users/mr.fu/DAIMASUsystem
uvicorn api.main:app --reload
```

エンドポイント呼び出し:
```bash
curl -X POST http://localhost:8000/api/generation/video/ultra-wide \
  -H "Content-Type: application/json" \
  -d '{
    "theme": "zen",
    "course": "main",
    "seed_image_path": "/Users/mr.fu/DAIMASUsystem/api/uploads/seeds/zen_main_uw.jpg",
    "provider": "fal",
    "duration_seconds": 10,
    "crop_after": true
  }'
```

レスポンス:
```json
{
  "job_id": "webuw_<12hex>",
  "status": "processing",
  "message": "zen/main ultra-wide i2v 生成を開始しました (seed=...)"
}
```

進捗ポーリング:
```bash
curl http://localhost:8000/api/generation/jobs/<job_id>
```

完了時:
```json
{
  "status": "complete",
  "output_path": "/path/to/main_uw__gen_xxx_band.mp4"
}
```

出力解像度を ffprobe で再検証:
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
  -of csv=p=0 /path/to/main_uw__gen_xxx_band.mp4
# expected: 5520,1200
```

---

## 3. 内部動作

| ステップ | 関数 / API | 役割 |
|---|---|---|
| 1. job 作成 | `VideoGeneratorService.create_job(mode=ULTRA_WIDE_I2V)` | metadata 上は aspect="32:9"、出力 mp4 名は `<course>_uw__<job_id>.mp4` |
| 2. provider 呼び出し | `_generate_fal(job)` または `_generate_runway(job)` | `aspect_ratio` を強制的に 16:9 に。`seed_image_b64` は `job.seed_image_path` 由来 |
| 3. crop | `crop_to_table_band(input, output, layout)` | 中央水平 4.6:1 band を抜き、scale で 5520×1200 へ |

---

## 4. 既知の制約

### Kling i2v は input aspect の保持が不確実
Kling 公式は output aspect_ratio を 16:9 / 9:16 / 1:1 から選ぶ仕様で、それ以外は受け付けない。
input image が 32:9 でも output は 16:9 になる **可能性が高い**。実際の出力アスペクトは
1ジョブ叩いて確認するしかない。万一 Kling が 32:9 を保ってくれた場合、`crop_to_table_band`
は左右クロップではなく upscale のみで通る。

### Runway Gen-4.5 Turbo は input aspect の保持に厳格に追随しない
Runway は構図を自由にリフレームする傾向が強い。option ③ では fal.ai (Kling) を第一候補に
する理由はこれ。

### 後段 crop の画質劣化
Kling/Runway の native 出力は 1920×1080 や 1280×720 級。これを 5520×1200 にアップ
スケールすると visual quality が劣化する。理想は:
- 1080p 生成 → 中央 4.6:1 帯 (≒1920×417) → 5520×1200 に拡大 (約 2.9 倍)

この劣化が許容できないユースケース (ゲストの近距離視認シーンなど) では、option ⑤
(zone mode) や option ⑥ (Wan 2.2 / LTX Video) を検討。

---

## 5. 関連コード

- [workers/video_generator.py](../workers/video_generator.py)
  - `GenerationMode.ULTRA_WIDE_I2V`
  - `VideoGeneratorService.generate_ultra_wide_from_still()`
  - `_generate_fal` の ULTRA_WIDE_I2V 分岐
  - `_generate_runway` の ULTRA_WIDE_I2V 分岐
- [workers/content_compositor.py](../workers/content_compositor.py)
  - `crop_to_table_band(input_path, output_path, layout)`
- [api/routers/generation.py](../api/routers/generation.py)
  - `POST /api/generation/video/ultra-wide`
  - `VideoGenerateRequest.seed_image_path` (既存 `/video` 経由でも使える)

---

## 6. 検証チェックリスト

実機 1 ジョブ走らせるときに見るポイント:

- [ ] Kling の生成出力アスペクトを ffprobe で確認 (32:9 を保ったか / 16:9 に戻ったか)
- [ ] `crop_to_table_band` 後の解像度が 5520×1200 ぴったり
- [ ] 中央被写体が crop でフレームアウトしてないか目視
- [ ] zone 単位 (1380×1200 × 4) の seam が出ない (全 band が連続している)
- [ ] TouchDesigner 側に流し込んで実投影で破綻 (色帯 / banding / 黒バー) がないか
