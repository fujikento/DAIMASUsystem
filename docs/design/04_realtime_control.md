# リアルタイム制御設計書

## A. ショーコントロールシステム

### キュー（Cue）ベースのショー制御アーキテクチャ

ショーはキューのシーケンスとして管理される。各キューはひとつの演出単位（コンテンツ切替、トランジション、待機など）を表す。

```
Show
 └─ ShowCue[] (sort_order 順)
      ├─ cue_number: 1.0, 1.5, 2.0 ...（小数点は挿入キューに使用）
      ├─ cue_type: content / transition / trigger / wait
      ├─ target_zones: "all" or "1,2,3,4"
      ├─ content_path: 再生するメディアのパス
      ├─ transition: crossfade / cut / fade_black
      ├─ duration_seconds: キューの継続時間
      ├─ auto_follow: true の場合、自動で次キューへ
      └─ auto_follow_delay: 自動進行までの秒数
```

### 進行モード

#### 自動進行モード（タイマーベース）
- `auto_follow = true` のキューは `duration_seconds + auto_follow_delay` 後に自動で次キューへ進む
- バックグラウンドタスク（asyncio）でタイマーを管理
- ショー全体の自動実行に使用（コース提供が決まっているランチなど）

#### 手動進行モード（スタッフがボタンを押す）
- `auto_follow = false` のキューで停止
- スタッフが `/api/shows/{id}/go` を叩くまで待機
- 料理提供のタイミングに合わせた柔軟な進行が可能

### フェイルセーフ

| 状況 | フォールバック動作 |
|------|------------------|
| OSC通信断（TouchDesigner接続失敗） | ログ記録のみ、ショーステータスは継続 |
| キューの次がない | ショーを completed 状態にする |
| サーバー再起動 | Show.status が running のままの場合、再起動後にリセット |
| WebSocket切断 | クライアントは再接続を試みる（3秒間隔） |

---

## B. WebSocket拡張プロトコル

### エンドポイント
`/api/projection/ws`（既存）および `/api/shows/ws`（ショー専用・新規追加）

### チャンネル設計

#### status チャンネル（サーバー → クライアント）
ショーの現在状態を定期配信（状態変化時のみ送信）

```json
{
  "channel": "status",
  "data": {
    "show_id": 1,
    "show_status": "running",
    "current_cue_id": 5,
    "current_cue_number": 3.0,
    "elapsed_in_cue": 12.5,
    "remaining_in_cue": 17.5,
    "total_cues": 8,
    "completed_cues": 2
  }
}
```

#### control チャンネル（クライアント → サーバー）
スタッフ操作のコマンド送信

```json
{"channel": "control", "action": "next_cue", "data": {"show_id": 1}}
{"channel": "control", "action": "go_to_cue", "data": {"show_id": 1, "cue_id": 5}}
{"channel": "control", "action": "pause", "data": {"show_id": 1}}
{"channel": "control", "action": "stop", "data": {"show_id": 1}}
```

#### sync チャンネル（サーバー → クライアント）
複数クライアント間の同期確認

```json
{
  "channel": "sync",
  "data": {
    "server_time": 1700000000.123,
    "show_id": 1,
    "cue_started_at": 1700000000.000
  }
}
```

#### alert チャンネル（サーバー → クライアント）
エラーや警告の通知

```json
{
  "channel": "alert",
  "level": "warning",
  "message": "OSC接続失敗: TouchDesignerが応答しません",
  "timestamp": "2024-01-01T12:00:00"
}
```

---

## C. 同期タイミング制御

### 料理提供タイミングとのシンク方式

#### 手動トリガー方式（推奨）
- スタッフが料理を提供する直前に「GO」ボタンを押す
- `POST /api/shows/{id}/go` でキューを進める
- 遅延補正: OSC送信 → TouchDesigner受信まで約50ms。これを考慮してボタン押下後すぐにOSC送信

#### 自動タイマー方式
- コース提供時刻をあらかじめ設定（`auto_follow_delay`）
- ショー開始時刻から相対時間で進行
- フルコース（90分固定）のランチコースで使用

### 複数テーブル同時運用時の独立制御

```
Show A (テーブル1) --- ShowCue 1 → 2 → 3
Show B (テーブル2) --- ShowCue 1 → 2 → 3
Show C (テーブル3) --- ShowCue 1 → 2 → 3
```

- 各 Show は独立した OSC チャンネルで制御
- OSC アドレス: `/show/{table_id}/content/load`, `/show/{table_id}/play` 等
- 複数テーブルを同期進行させる場合: `target_tables` パラメータで複数指定
- 将来的にテーブルID別OSCポートの分離も可能

### 音響連携（BGM切り替えのOSC送信）

```
キュー cue_type="trigger" で音響連携:
  OSC address: /audio/bgm/load
  args: [bgm_file_path, fade_duration]

  OSC address: /audio/bgm/play
  args: [volume, loop]

  OSC address: /audio/se/trigger
  args: [se_name]
```

音響キューは `cue_type = "trigger"` として定義し、`content_path` にBGMファイルパスを格納する。
トランジション時に同時送信することで映像・音響の同期を実現する。

---

## D. システム全体フロー

```
スタッフ操作
    │
    ▼
ShowControl API (/api/shows/{id}/go)
    │
    ├─ DBのcurrent_cue_idを更新
    ├─ 次キューのコンテンツをOSC送信
    │       └─ osc.load_content(content_path, zone)
    │       └─ osc.transition(transition, duration)
    ├─ WebSocketで全クライアントにステータス配信
    └─ auto_follow=True の場合: asyncioタスクでタイマー設定
```

---

## E. データモデル

### Show テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | Integer | PK |
| name | String | ショー名 |
| storyboard_id | Integer FK | 元ストーリーボード（任意） |
| status | String | standby/running/paused/completed |
| current_cue_id | Integer | 現在実行中のキューID |
| created_at | DateTime | 作成日時 |

### ShowCue テーブル
| カラム | 型 | 説明 |
|--------|-----|------|
| id | Integer | PK |
| show_id | Integer FK | 所属ショー |
| cue_number | Float | 1.0, 1.5, 2.0 ... |
| cue_type | String | content/transition/trigger/wait |
| target_zones | String | "1,2,3,4" or "all" |
| content_path | String | メディアパス |
| transition | String | crossfade/cut/fade_black |
| duration_seconds | Float | キュー継続時間 |
| auto_follow | Boolean | 自動進行フラグ |
| auto_follow_delay | Float | 自動進行遅延（秒） |
| notes | Text | メモ |
| sort_order | Integer | 表示順 |
