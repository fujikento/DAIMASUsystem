# DAIMASUsystem オペレーション Runbook

**対象**: 現場オペレーター(本番投入時にステージ近くで操作する人)
**前提**: backend (FastAPI) + frontend (Next.js) + TouchDesigner + プロジェクター × 3 が稼働している

---

## 0. ショー前(本番 60 分前まで)

### 0.1 起動確認

```bash
# 開発機 / 制御 PC で
cd /Users/mr.fu/DAIMASUsystem
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 &
cd web && npm run dev &
```

ブラウザで `http://localhost:3000/operator` を開く(スマホで開くなら同 LAN の制御 PC IP)。

### 0.2 readiness probe

```
GET /api/readiness
→ overall: "ready" を確認
```

`degraded` や `unready` なら下記:

| overall | 意味 | 対応 |
|---|---|---|
| `ready` | 全部 OK | 続行 |
| `degraded` | DB/ffmpeg/seed_root は OK だが API key 未設定 | Settings で key 入力。AI 生成しないなら無視可 |
| `unready` | DB か ffmpeg か seed_root が壊れている | 起動失敗。下記 1.1 参照 |

### 0.3 コスト残額確認

```
GET /api/cost/today
→ remaining_usd を確認
```

本番日の見込みコスト(例: 5 ストーリーボード × 5 scene × $0.17/image + 動画 $0.20 ≒ $10)を
remaining_usd が下回るなら `DAILY_AI_BUDGET_USD` env を上げる。

### 0.4 リハーサルモード起動

```
POST /api/system/rehearsal/1
```

これ以降の OSC 送信は TouchDesigner に届かず、ログだけ残る。dry-run で全 cue を
回せる。本番開始前に元に戻す:

```
POST /api/system/rehearsal/0
```

オペレーター画面の上に黄色バナーが出ていればリハーサル中。

### 0.5 ショー事前検証

```
GET /api/shows/{show_id}/rehearsal/validate
```

レスポンス例:
```json
{
  "ok": true,
  "total_runtime_seconds": 1820.5,
  "cues": [...],
  "summary": {"n_cues": 24, "n_ok": 24, "n_warning": 0, "n_error": 0}
}
```

- `n_error > 0` → 該当 cue を修正してから本番投入
- `n_warning > 0` → 警告内容を確認(ほとんどは BGM trigger に content_path 未設定など、許容範囲)

---

## 1. ショー中

### 1.1 オペレーター UI

スマホで `http://<制御PC>:3000/operator` を開く。

ボタン:

| ボタン | 意味 |
|---|---|
| ▶ START | 最初の cue を実行(panic flag も解除) |
| → GO | 次の cue へ手動進行 |
| ‖ PAUSE | 進行停止(現在の表示は保持) |
| ■ STOP | 終了(プロジェクターは黒へ) |
| ◑ BLACKOUT | プロジェクター強制黒画面(VIP 撮影等で隠したいとき) |
| ◐ UNBLACK | BLACKOUT 解除 |
| 🚨 EMERGENCY STOP | 全 OSC 即停止 + blackout + panic flag。再開には START が必要 |

### 1.2 異常時(degraded フラグが出たら)

UI に **⚠ DEGRADED: <理由>** の赤帯が出る。

| 理由 | 意味 | 対応 |
|---|---|---|
| `load_content failed: ...` | OSC が TouchDesigner に届かない | OSC ポート / TD プロセス確認 |
| `transition failed: ...` | trasition 実行不可 | 同上 |
| `emergency_stop` | 緊急停止された | START で再開 |

### 1.3 致命的事故(画面が暴れる / 大量黒帯 / ループ)

1. 🚨 EMERGENCY STOP を押す(panic flag が立ち、以後 OSC ロック)
2. 客への影響回避を最優先(司会者に合図、照明スタッフ呼ぶ)
3. 落ち着いたら ◑ BLACKOUT で完全に黒に固定
4. システム側のログ確認(`tail -f /tmp/daimasu_logs/backend.log` か journalctl)
5. 復帰可能と判断したら ▶ START で再開

---

## 2. ショー後

### 2.1 バックアップ

```bash
./scripts/backup.sh
```

`backups/dining-YYYYMMDD-HHMMSS.db.gz` が作られる(自動で 30 世代までローテーション)。
cron で 毎日 03:00 にも自動実行する:

```cron
0 3 * * * cd /Users/mr.fu/DAIMASUsystem && ./scripts/backup.sh
```

### 2.2 コスト集計

```
GET /api/cost/today
```

`used_usd_today` を計上(運営精算用)。

### 2.3 ログ保存

`/tmp/daimasu_logs/backend.log` を別ディレクトリへ退避(`/tmp` は再起動で消える)。

---

## 3. トラブルシュート

### 3.1 backend が起動しない

```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
# エラー内容を確認:
# - "Address already in use" → 別 process が 8000 を掴んでる
#   lsof -ti:8000 | xargs kill
# - "No such file: dining.db" → 初回起動で自動作成されるはずなので touch で空 db を作って再起動
# - module import error → pip install -r requirements.txt が必要
```

### 3.2 frontend が起動しない

```bash
cd web && npm install && npm run dev
```

### 3.3 OSC が TouchDesigner に届かない

1. `GET /api/system/info` で `OSC_TD_HOST` / `OSC_TD_PORT` を確認(default 127.0.0.1:7000)
2. TouchDesigner 側の OSC In CHOP を起動して同 port で listening している?
3. `POST /api/system/rehearsal/1` でリハーサルモード on にして、`GET /api/system/rehearsal/log` で
   backend が送る予定だった OSC 内容を確認
4. firewall で 7000/udp が blocked されていないか

### 3.4 認証 401 連発

ブラウザの localStorage に古い ADMIN_API_KEY が残っている可能性。

開発者ツール → Application → Local Storage → `DAIMASU_ADMIN_API_KEY` を削除して reload。
AdminKeyGate モーダルが再表示されるので、現行の key を入力。

### 3.5 デイリーバジェット 429

```
HTTP 429: Daily AI budget exceeded
```

- 一時的解決: `export DAILY_AI_BUDGET_USD=100` で再起動
- 翌日 (UTC 00:00) になれば自動リセット
- またはミスで重複生成していないか確認(`GET /api/analytics/generation/costs`)

---

## 4. 重要な env vars リファレンス

| env | default | 説明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<project>/api/dining.db` | DB 接続文字列 |
| `ADMIN_API_KEY` | (空) | 設定時のみ /api/* 認証 enforce |
| `OSC_TD_HOST` | `127.0.0.1` | TouchDesigner ホスト |
| `OSC_TD_PORT` | `7000` | TD への OSC 送信先 |
| `OSC_ACK_ENABLED` | `0` | ack mode (TD パッチが /ack/<seq> 返す前提) |
| `OSC_DRY_RUN` | `0` | 起動時から rehearsal mode |
| `SEED_IMAGES_ROOT` | `<project>/api/uploads/seeds` | gpt-image-2 用 seed 画像置場 |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` | OpenAI Images API 用 model id |
| `DAILY_AI_BUDGET_USD` | `50.0` | 1 日あたりの AI 生成コスト上限 |
| `OPENAI_API_KEY` | (空) | 設定で gpt-image-2 有効 |
| `GEMINI_API_KEY` | (空) | Storyboard 台本生成 / Gemini 画像 |
| `FAL_API_KEY` | (空) | fal.ai Flux Pro 画像 + Kling 動画 |
| `RUNWAY_API_KEY` | (空) | Runway Gen-4.5 動画 |
| `RATE_LIMIT_DEFAULT` | `120/minute` | API 全般のリクエスト上限 |
| `RATE_LIMIT_GENERATION` | `30/minute` | 生成系 endpoint の上限 |

---

## 5. ファイル配置

```
DAIMASUsystem/
├── api/                       # FastAPI backend
│   ├── main.py
│   ├── middleware/auth.py     # API key middleware
│   ├── middleware/ratelimit.py
│   ├── routers/system.py      # /api/health, /api/cost/today, /api/qc/video 等
│   ├── routers/show_control.py  # /api/shows/{id}/emergency-stop 等
│   ├── services/cost_tracker.py
│   ├── services/content_qc.py
│   ├── services/osc_controller.py
│   ├── uploads/seeds/         # gpt-image-2 用 seed 置場 (SEED_IMAGES_ROOT)
│   └── dining.db              # SQLite DB
├── web/                       # Next.js frontend
│   ├── src/app/operator/      # オペレーター用 mobile UI
│   ├── src/app/generation/    # 管理画面 (絵コンテ → 画像 → 動画)
│   └── src/components/AdminKeyGate.tsx
├── workers/                   # 生成パイプライン
│   ├── video_generator.py
│   ├── image_generator.py
│   └── content_compositor.py
├── touchdesigner/             # 生成された content / TD パッチ置場
│   └── content/
├── scripts/
│   └── backup.sh
├── docs/
│   ├── OPERATIONS_RUNBOOK.md  # ← このファイル
│   ├── ULTRA_WIDE_I2V_WORKFLOW.md
│   └── design/                # 設計ドキュメント群
└── tests/                     # pytest critical path
```
