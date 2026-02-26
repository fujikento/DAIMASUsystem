# 05. AIキャラクター生成 設計書

## 概要

ゲストの写真1枚から、テーマに合わせたAIキャラクターを生成し、プロジェクション演出に組み込むシステム。
バースデー専用だった `photo_animator.py` を汎用化し、ウェルカム・リアクション・メモリアルフォトなど複数ユースケースに対応する。

---

## A. キャラクター生成パイプライン

### パイプライン全体フロー

```
写真アップロード → 顔検出 → スタイル変換 → アニメーション生成 → テンプレート合成 → 区画配置
                    │            │              │                  │
                    ▼            ▼              ▼                  ▼
               face_detect   style_transfer   LivePortrait      ffmpeg
               (mediapipe)   (Stable Diff     / Hedra API      composite
                              img2img)                          → 1380x1200
```

### Step 1: 写真アップロード & 顔検出

- アップロード先: `api/uploads/character_photos/`
- 顔検出: MediaPipe FaceDetection で顔領域を抽出
- 顔が検出できない場合 → フォールバック（後述）
- 複数の顔が検出された場合 → 最大面積の顔を採用

### Step 2: スタイル変換（オプション）

テーマに合わせた画風変換を適用:

| テーマ     | スタイル       | 手法                         |
|-----------|--------------|------------------------------|
| ocean     | 水彩風        | img2img (watercolor style)   |
| forest    | 油絵風        | img2img (oil painting style) |
| zen       | 墨絵風        | img2img (sumi-e style)       |
| fire      | ネオン風       | img2img (neon glow style)    |
| gold      | ゴールド箔風    | img2img (gold leaf style)    |
| space     | SF風         | img2img (sci-fi style)       |
| fairytale | イラスト風     | img2img (storybook style)    |

- プロバイダー: ローカル Stable Diffusion または API (Stability AI)
- 強度 (denoising_strength): 0.4〜0.6 で元の顔の特徴を保持

### Step 3: アニメーション生成

2つのプロバイダーを選択可能:

**LivePortrait (ローカル):**
- ドライバー動画から動きを転写
- 推論時間: 約10〜30秒
- GPU必要: NVIDIA RTX 3060以上推奨
- メリット: ランニングコスト無し、低レイテンシ

**Hedra AI (API):**
- テキスト + 写真 → トーキングヘッド動画
- 推論時間: 約30〜60秒
- メリット: 音声付き、表情が豊か

### Step 4: テンプレート合成

- アニメーション結果をテンプレート背景動画に合成
- composite_position (x, y, scale) でキャラクター配置
- テキストオーバーレイ（ゲスト名、メッセージ）
- 出力: 1380x1200 (区画サイズ)

### リアルタイム vs プリレンダリング

| 方式            | 用途              | 所要時間    | 品質   |
|----------------|-------------------|-----------|--------|
| プリレンダリング | バースデー、メモリアル | 30〜90秒  | 高     |
| リアルタイム     | ウェルカム演出       | 5〜15秒   | 中     |

- **プリレンダリング**: バースデー予約時に事前生成。高品質なアニメーション + 合成。
- **リアルタイム**: 来店時にタブレットで撮影 → 簡易スタイル変換のみ → 静止画ベースの演出。

### 顔検出失敗時のフォールバック

1. 写真全体をアバターとして使用（顔クロップなし）
2. デフォルトアバター画像を適用（テーマに合わせた汎用キャラクター）
3. テキストのみの演出に切り替え（名前 + メッセージ投影）

---

## B. キャラクターインタラクション設計

### ウェルカム演出

ゲスト来店時に、タブレットで撮影した写真からアバターを即時生成:

- 投影: ゲストの着席区画 (Zone) に個別表示
- 演出: アバターが「おかえりなさい、{名前}さん」とテキスト付きで登場
- 所要時間: 撮影 → 表示まで10秒以内目標（簡易スタイル変換のみ）
- フォールバック: 名前のみのテキスト演出

### バースデー演出

予約時にアップロードされた写真からフルアニメーションを事前生成:

- 演出パターン: キャラクターがケーキを運ぶ / 花火 / 魔法 等
- 投影: 対象ゲストの区画 + 周辺区画への波及演出
- 音声同期: BGM切り替えトリガーと連動
- テキスト: 「Happy Birthday {名前}さん!」

### サプライズ演出

特別イベント時のキャラクター登場:

- **記念日サプライズ**: キャラクターがギフトボックスを持って登場
- **プロポーズ演出**: 花びらが舞い、キャラクターがリングを差し出す演出
- **団体パーティー**: 全員のアバターが共演するフィナーレ

### テーブル全体での協調演出 (8席分)

4区画 × 2席 = 8名分のキャラクターが協調する演出:

```
Zone 1          Zone 2          Zone 3          Zone 4
┌───────────┬───────────┬───────────┬───────────┐
│ Guest A   │ Guest C   │ Guest E   │ Guest G   │
│   +       │   +       │   +       │   +       │
│ Guest B   │ Guest D   │ Guest F   │ Guest H   │
└───────────┴───────────┴───────────┴───────────┘
```

- 各区画に2名分のキャラクターを配置可能
- キャラクター同士が手を振る / 乾杯するなどの連動アニメーション
- バースデーゲストの区画を中心に、他区画のキャラクターが祝福する演出
- 全区画を使った「ウェーブ演出」（Zone1→2→3→4と順に反応）

---

## C. テンプレートシステム拡張

### テンプレートカテゴリ一覧

#### バースデー系 (3パターン)

| ID                     | 名前             | 時間 | ドライバー動画                          | 背景                              | 合成位置                    | テキスト位置          |
|------------------------|-----------------|------|----------------------------------------|-----------------------------------|-----------------------------|----------------------|
| birthday_cake          | ケーキ作り        | 30s  | birthday/cake_making_driver.mp4        | birthday/cake_making_bg.mp4       | x:0.3, y:0.2, scale:0.4    | 下部中央             |
| birthday_fireworks     | 花火セレブレーション | 20s  | birthday/fireworks_driver.mp4          | birthday/fireworks_bg.mp4         | x:0.5, y:0.6, scale:0.45   | 上部中央             |
| birthday_magic         | 魔法の庭園        | 25s  | birthday/magic_garden_driver.mp4       | birthday/magic_garden_bg.mp4      | x:0.4, y:0.3, scale:0.4    | 下部中央             |

#### ウェルカム系 (3パターン)

| ID                     | 名前             | 時間 | ドライバー動画                          | 背景                              | 合成位置                    | テキスト位置          |
|------------------------|-----------------|------|----------------------------------------|-----------------------------------|-----------------------------|----------------------|
| welcome_elegant        | エレガント入場     | 10s  | welcome/elegant_entrance_driver.mp4    | welcome/elegant_entrance_bg.mp4   | x:0.5, y:0.4, scale:0.5    | 下部中央             |
| welcome_nature         | ナチュラルウェルカム | 10s  | welcome/nature_welcome_driver.mp4      | welcome/nature_welcome_bg.mp4     | x:0.4, y:0.3, scale:0.45   | 下部中央             |
| welcome_sparkle        | スパークル         | 8s   | welcome/sparkle_driver.mp4            | welcome/sparkle_bg.mp4            | x:0.5, y:0.5, scale:0.4    | 上部中央             |

#### サプライズ系 (2パターン)

| ID                     | 名前             | 時間 | ドライバー動画                          | 背景                              | 合成位置                    | テキスト位置          |
|------------------------|-----------------|------|----------------------------------------|-----------------------------------|-----------------------------|----------------------|
| surprise_gift          | ギフトサプライズ   | 15s  | surprise/gift_reveal_driver.mp4        | surprise/gift_reveal_bg.mp4       | x:0.5, y:0.4, scale:0.45   | 下部中央             |
| surprise_confetti      | 紙吹雪セレブレーション | 12s | surprise/confetti_driver.mp4          | surprise/confetti_bg.mp4          | x:0.5, y:0.5, scale:0.4    | 上部中央             |

#### 季節イベント系 (4パターン)

| ID                     | 名前             | 時間 | ドライバー動画                          | 背景                              | 合成位置                    | テキスト位置          |
|------------------------|-----------------|------|----------------------------------------|-----------------------------------|-----------------------------|----------------------|
| season_spring          | 桜フェスティバル   | 15s  | season/spring_sakura_driver.mp4        | season/spring_sakura_bg.mp4       | x:0.5, y:0.4, scale:0.4    | 下部中央             |
| season_summer          | サマーパラダイス   | 15s  | season/summer_beach_driver.mp4         | season/summer_beach_bg.mp4        | x:0.5, y:0.5, scale:0.4    | 下部中央             |
| season_autumn          | オータムハーベスト | 15s  | season/autumn_harvest_driver.mp4       | season/autumn_harvest_bg.mp4      | x:0.5, y:0.4, scale:0.4    | 下部中央             |
| season_winter          | ウィンターワンダーランド | 15s | season/winter_snow_driver.mp4       | season/winter_snow_bg.mp4         | x:0.5, y:0.4, scale:0.45   | 上部中央             |

### テンプレート仕様詳細

各テンプレートは以下の構成ファイルを持つ:

```
templates/{category}/{template_id}/
├── driver.mp4          # ドライバー動画 (LivePortrait用)
├── background.mp4      # 背景映像
├── config.json         # 合成位置、テキスト設定
├── thumbnail.jpg       # プレビューサムネイル
└── preview.mp4         # プレビュー動画 (デフォルトキャラ付き)
```

`config.json` 例:
```json
{
  "id": "birthday_cake",
  "category": "birthday",
  "name": "ケーキ作り",
  "description": "キャラクターがケーキを作って祝福する演出",
  "duration": 30,
  "composite_position": {"x": 0.3, "y": 0.2, "scale": 0.4},
  "text_position": {"x": 0.5, "y": 0.85, "anchor": "center"},
  "text_style": {
    "font_size": 48,
    "color": "#FFFFFF",
    "shadow": true,
    "animation": "fade_in"
  },
  "style_hint": "warm, celebratory, golden lighting"
}
```

---

## 技術仕様

- 出力解像度: 1380x1200 (区画サイズ)
- フレームレート: 30fps
- コーデック: H.264, CRF 16
- 最大同時生成ジョブ: 4 (区画数)
- ジョブキュー: インメモリ (将来的にRedis化)
