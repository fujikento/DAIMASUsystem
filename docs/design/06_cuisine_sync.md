# 料理同期システム設計書

## 概要

イマーシブダイニングにおける料理提供と投影演出の同期システム。
キッチン出し〜テーブル着席〜食事完了の各フェーズで、TouchDesigner への OSC トリガーを自動または手動で発火し、没入体験を演出する。

---

## A. 料理提供フロー

### キッチン → ホール → テーブル フロー

```
[キッチン]                  [ホール]                  [テーブル]
    |                           |                           |
    |-- prepared ↓              |                           |
    | （盛り付け完了）           |                           |
    |                    served ↓                           |
    |                  （ホール通過）                        |
    |                           |              served ↓     |
    |                           |          （テーブル着）    |
    |                           |                           |
    |                           |              eating ↓     |
    |                           |           （食事開始）     |
    |                           |                           |
    |                           |             cleared ↓     |
    |                           |           （皿下げ完了）   |
```

### 各段階のトリガーポイント

| event_type | 発火者 | タイミング | 投影演出 |
|---|---|---|---|
| `prepared` | キッチンスタッフ | 盛り付け完了・出口通過 | コース予告映像（ソフトグロー） |
| `served` | ホールスタッフ | テーブルへ配膳完了 | メイン演出開始（OSC: /course/serve） |
| `eaten` | ホールスタッフ | ゲストが食べ始めたと判断 | 演出継続・BGM フェード |
| `cleared` | ホールスタッフ | 皿を下げた後 | 次コース予告・幕間演出 |

### 料理写真撮影 → 投影連携

1. スタッフがタブレットで料理写真を撮影（任意）
2. 写真を `CourseEvent.notes` にパスとして記録
3. 写真はリアルタイム投影の補助素材として TouchDesigner へ転送
4. AI 演出（Runway 生成映像）との切り替えはスタッフがボタン操作でトリガー

---

## B. 同期プロトコル

### キッチンディスプレイとの連携方式

- **プロトコル**: REST API + SSE（Server-Sent Events）によるリアルタイム通知
- キッチンディスプレイは `GET /api/sessions?status=active` をポーリング（5 秒間隔）
- セッション状態変更時にイベントを発火、キッチン画面をリフレッシュ

### テーブルスタッフ用タブレット UI

- `CourseControlPanel.tsx` でコース進行を管理
- 各コースに「提供」「下げ」ボタンを配置（大きなタッチターゲット）
- ネットワーク切断時はオフラインキューで操作をバッファリング
- ダークテーマで夜間操作でも目立たない設計

### 自動タイマー vs 手動トリガー のハイブリッド制御

```
[モード選択]
  ├── AUTO: 前コース "cleared" から N 分後に次コース "served" を自動発火
  └── MANUAL: スタッフが「提供」ボタンを押すまで待機

[推奨設定]
  - welcome → appetizer : 12 分 (AUTO)
  - appetizer → soup    : 15 分 (AUTO)
  - soup → main         : 20 分 (MANUAL 推奨・料理に時間がかかるため)
  - main → dessert      : 25 分 (MANUAL 推奨)
```

### 遅延許容度の設計（±30 秒バッファリング）

- 演出はコース提供の **30 秒前** からプリロードを開始
- `course_started_at` からの経過時間を `CourseEvent.timestamp` で追跡
- 実測遅延が ±30 秒以内: 演出は予定通り継続
- 遅延が 30〜90 秒: 演出速度を 0.9x に落として引き伸ばし
- 遅延が 90 秒超: 幕間ループ映像へ切り替え、手動復帰を待つ

OSC アドレス例:
```
/course/preload  {course_key}              # 30秒前プリロード
/course/serve    {course_key, session_id}  # 提供トリガー
/course/clear    {course_key, session_id}  # 皿下げトリガー
/course/buffer   {mode}                    # バッファモード切替
```

---

## C. メニュー管理拡張

### 日替わりメニュー + 固定メニュー管理

```
CourseDish.day_of_week = "monday" | "tuesday" | ... | "everyday"
```

- `day_of_week = "everyday"` は全曜日で有効な固定メニューとして扱う
- 日替わりメニューは曜日指定で登録
- 一覧取得時に `everyday` + 当日曜日でマージして返す

### アレルギー / 特別食対応時の演出変更

- `TableSession.special_requests` に JSON 形式で記録:
  ```json
  {
    "allergies": ["shellfish", "nuts"],
    "dietary": "vegan",
    "note": "卵アレルギーのお客様"
  }
  ```
- アレルギー対応コースが提供される際、投影演出の color_tone を変更して
  スタッフへ視覚的な注意喚起を行う（例: 赤いボーダー演出）
- TouchDesigner へ OSC で `/course/allergen_alert {session_id}` を送信

### 料理写真ライブラリ管理

- ディレクトリ: `touchdesigner/content/cuisine_photos/{day_of_week}/{course_key}/`
- ファイル命名: `{dish_name}_{YYYYMMDD}.jpg`
- CourseEvent 登録時に `notes` フィールドへ写真パスを JSON で格納:
  ```json
  {"photo_path": "cuisine_photos/monday/main/wagyu_20260221.jpg"}
  ```
- 静的配信: `/static/cuisine_photos` エンドポイントで配信予定

---

## D. データモデル

### TableSession

| カラム | 型 | 説明 |
|---|---|---|
| id | Integer PK | セッション ID |
| table_number | Integer | テーブル番号（デフォルト 1） |
| guest_count | Integer | ゲスト人数 |
| storyboard_id | Integer FK | 使用ストーリーボード |
| show_id | Integer | ショーコントロール参照 ID |
| status | String | seated / dining / dessert / completed |
| current_course | String | 現在のコースキー |
| course_started_at | DateTime | 現在コース開始時刻 |
| special_requests | Text | JSON: アレルギー等 |
| started_at | DateTime | セッション開始時刻 |
| completed_at | DateTime | セッション完了時刻 |

### CourseEvent

| カラム | 型 | 説明 |
|---|---|---|
| id | Integer PK | イベント ID |
| session_id | Integer FK | 対応セッション |
| course_key | String | welcome / appetizer / soup / main / dessert |
| event_type | String | prepared / served / eaten / cleared |
| timestamp | DateTime | イベント発生時刻 |
| notes | Text | JSON: メモ・写真パス等 |

---

## E. API エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| POST | /api/sessions | セッション開始 |
| GET | /api/sessions | アクティブセッション一覧 |
| GET | /api/sessions/{id} | セッション詳細 |
| POST | /api/sessions/{id}/course/{course_key}/serve | 料理提供トリガー |
| POST | /api/sessions/{id}/course/{course_key}/clear | 料理下げトリガー |
| POST | /api/sessions/{id}/complete | セッション完了 |
| GET | /api/sessions/{id}/timeline | イベントタイムライン |

---

## F. OSC メッセージ仕様

TouchDesigner 受信アドレス:

| アドレス | 引数 | タイミング |
|---|---|---|
| `/course/serve` | session_id, course_key | 料理テーブル着 |
| `/course/clear` | session_id, course_key | 皿下げ完了 |
| `/course/preload` | course_key | 提供 30 秒前 |
| `/course/allergen_alert` | session_id | アレルギー対応時 |
| `/session/start` | session_id, table_number | セッション開始 |
| `/session/complete` | session_id | セッション完了 |
