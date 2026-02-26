# 分析・改善設計書

## A. データ収集戦略

### イベントログ (event_logs テーブル)

| event_type | event_category | 説明 |
|---|---|---|
| session.start | session | テーブルセッション開始 |
| session.complete | session | テーブルセッション完了 |
| course.served | course | コース料理提供 |
| course.cleared | course | コース料理片付け |
| show.cue | show | ショーキュー実行 |
| show.start | show | ショー開始 |
| show.complete | show | ショー完了 |
| generation.complete | generation | AI生成完了 |
| generation.failed | generation | AI生成失敗 |
| system.startup | system | システム起動 |
| system.error | system | システムエラー |

### パフォーマンスメトリクス (generation_metrics テーブル)

- **API応答時間** (`api_duration_ms`): プロバイダーAPIの純粋な応答時間
- **合計処理時間** (`total_duration_ms`): 前処理・後処理を含む総時間
- **出力ファイルサイズ** (`output_size_bytes`)
- **コスト推定** (`cost_estimate`): USD単位

### システムヘルス (GET /api/analytics/health)

- DB接続状態
- 直近5分間のイベント件数（アクティビティ指標）
- 最後の生成エラー詳細

### ゲスト満足度指標（推測ベース）

- **滞在時間**: `table_sessions.started_at` → `completed_at` の差分
- **コース消費ペース**: `course_events` のタイムスタンプ間隔
- **リピート率**: `reservations.guest_email` の重複カウント（将来実装）


## B. 分析ダッシュボード設計

### 日次サマリー (GET /api/analytics/dashboard)

```json
{
  "date": "2026-02-21",
  "total_sessions": 12,
  "total_generations": 48,
  "generation_success_rate": 93.8,
  "avg_image_duration_ms": 3200,
  "avg_video_duration_ms": 45000,
  "total_cost_estimate": 2.34,
  "event_counts_by_category": {
    "session": 24,
    "course": 60,
    "generation": 48
  }
}
```

### セッション分析 (GET /api/analytics/sessions)

- 日別セッション数と平均滞在時間
- クエリパラメータ: `period=daily|weekly`, `days=7|30`

### 生成パフォーマンス (GET /api/analytics/generation)

- プロバイダー別・生成種別別の集計
- 成功率、平均API時間、平均合計時間、コスト

### コスト分析 (GET /api/analytics/generation/costs)

- 日別・プロバイダー別コスト推移
- クエリパラメータ: `days=30`

### テーマ別利用統計 (GET /api/analytics/themes)

- 曜日テーマ別ストーリーボード数
- 画像生成完了数・動画生成完了数


## C. 改善サイクル

### A/Bテスト設計

演出パターン比較のためのフレームワーク:

1. `event_logs.data` に `variant: "A"|"B"` を含める
2. バリアント別の完了率・セッション時間を比較
3. 統計的有意差 p < 0.05 を確認してから採用

```python
# イベント記録例
EventLogger.log(
    event_type="show.complete",
    category="show",
    session_id=session.id,
    data={"variant": "A", "duration_s": 45, "cue_count": 8}
)
```

### プロンプト最適化フィードバックループ

1. `generation_metrics` で成功/失敗を追跡
2. 失敗の多いプロンプトパターンを抽出
3. `storyboard_scenes.prompt_modifier` で改善プロンプトをテスト
4. 成功率向上を `generation_metrics` で確認

### 自動最適化ロードマップ

| フェーズ | 内容 | 指標 |
|---|---|---|
| Phase 1 | データ収集・モニタリング | イベントログ蓄積 |
| Phase 2 | 人気テーマの自動推薦 | テーマ別利用頻度 |
| Phase 3 | 生成コスト最適化 | コスト/シーン削減率 |
| Phase 4 | ゲスト体験パーソナライズ | 滞在時間・満足度指標 |


## D. 実装ファイル一覧

| ファイル | 説明 |
|---|---|
| `api/models/schemas.py` | `EventLog`, `GenerationMetrics` ORM + Pydanticスキーマ |
| `api/services/event_logger.py` | `EventLogger` ヘルパークラス |
| `api/routers/analytics.py` | 分析APIルーター (8エンドポイント) |
| `api/main.py` | `analytics.router` 登録済み |
| `web/src/app/analytics/page.tsx` | 分析ダッシュボードUI |
| `web/src/lib/api.ts` | Analytics型定義・API関数追加済み |
| `web/src/components/Sidebar.tsx` | 「分析」リンク追加済み |


## E. イベントロガー使用例

```python
from api.services.event_logger import EventLogger

# シンプルなイベント記録
EventLogger.log(
    event_type="session.start",
    category="session",
    session_id=session.id,
    data={"table_number": 2, "guest_count": 4}
)

# 生成メトリクス記録
EventLogger.log_generation(
    provider="imagen",
    model="imagen-3.0-generate-001",
    gen_type="image",
    duration_ms=3200,
    status="success",
    scene_id=scene.id,
    prompt_length=len(prompt),
    cost_estimate=0.04,
)
```
