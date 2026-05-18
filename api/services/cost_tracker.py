"""AI 生成コスト tracking + デイリー cap。

目的:
  - gpt-image-2 / fal.ai Kling / Runway が無制限に呼ばれて月数千ドル請求されるのを防ぐ
  - 当日コスト残量を /api/cost/today で可視化、UI が表示
  - 上限超過時はジョブを synchronous に拒否 (生成前 fail-fast)

設計:
  - SQLite の `event_logs` に `category='ai_cost'` で記録 (既存テーブル流用)
  - 環境変数 DAILY_AI_BUDGET_USD で日次上限 (default 50.00)
  - 価格表は static dict (随時更新)

価格 (2026 年初時点の概算 USD):
  - gpt-image-2 high quality 1536x1024 ≒ $0.17 / image
  - fal.ai Flux Pro v1.1 Ultra ≒ $0.05 / image
  - Gemini 2.5 Flash Image ≒ $0.039 / image
  - Imagen 4 Fast ≒ $0.02 / image
  - fal.ai Kling v2.1 ≒ $0.10 / 5秒video, $0.20 / 10秒video
  - Runway Gen-4.5 Turbo ≒ $0.25 / 10秒video
"""
from __future__ import annotations

import datetime
import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# USD per unit. 不明な provider は 0 (記録のみで cap 計算から外れる)。
PROVIDER_PRICES: dict[str, float] = {
    # 画像 ($/枚)
    "gpt_image_2": 0.17,
    "fal_image": 0.05,            # fal.ai Flux Pro v1.1 Ultra
    "gemini": 0.039,
    "gemini_pro": 0.06,
    "imagen": 0.02,
    "imagen_fast": 0.02,
    # 動画 ($/clip) — duration_seconds で内部按分
    "fal_video_5s": 0.10,
    "fal_video_10s": 0.20,
    "runway_video": 0.25,
    "kling_video": 0.20,           # Kling 2.6 公開 API (推定)
    "pika_video": 0.18,            # Pika 2.5 (placeholder)
}


def map_video_provider(provider_str: str) -> str:
    """API request の provider 名 (`runway`/`fal`/`kling`/`pika`) を cost_tracker の
    price key に変換する (codex round 6 P2: kling/pika が runway 扱いだったのを修正)。"""
    p = (provider_str or "").lower()
    if p == "fal":
        return "fal_video"
    if p == "kling":
        return "kling_video"
    if p == "pika":
        return "pika_video"
    return "runway_video"


def map_image_provider(provider_str: str) -> str:
    """ImageProvider value を price key に変換。"""
    p = (provider_str or "").lower()
    if p == "fal":
        return "fal_image"
    return p  # gpt_image_2 / gemini / imagen 等はそのまま

# 日次上限。env override 可能。テスト時は環境変数で 0 にして cap 無効化。
DAILY_AI_BUDGET_USD = float(os.environ.get("DAILY_AI_BUDGET_USD", "50.0"))


@dataclass
class CostRecord:
    provider: str
    operation: str  # "image" | "video"
    units: int
    duration_seconds: Optional[int]
    estimated_usd: float
    metadata: dict


def _estimate_video_usd(provider: str, duration_seconds: int) -> float:
    """動画 provider のコスト見積もり。duration で分岐するため別 helper。

    codex round 7 P1: kling/pika を 0 円扱いしていたバグを修正。
    map_video_provider が返す値全てに対応する。
    """
    if provider == "fal_video":
        # Kling via fal.ai 5s / 10s 価格帯
        if duration_seconds <= 5:
            return PROVIDER_PRICES["fal_video_5s"]
        return PROVIDER_PRICES["fal_video_10s"]
    if provider == "runway_video":
        return PROVIDER_PRICES["runway_video"]
    if provider == "kling_video":
        return PROVIDER_PRICES["kling_video"]
    if provider == "pika_video":
        return PROVIDER_PRICES["pika_video"]
    return 0.0


def estimate_usd(provider: str, operation: str, duration_seconds: Optional[int] = None) -> float:
    """1 操作あたりの USD 見積もり。価格表に無い provider は 0。"""
    if operation == "video" and duration_seconds is not None:
        return _estimate_video_usd(provider, duration_seconds)
    return PROVIDER_PRICES.get(provider, 0.0)


def _today_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def daily_total_usd(db: Session) -> float:
    """本日の累計 USD (UTC 日付ベース)。"""
    from api.models.schemas import EventLog
    today = _today_iso()
    rows = (
        db.query(EventLog)
        .filter(EventLog.event_category == "ai_cost", EventLog.event_type == "spent")
        .all()
    )
    total = 0.0
    for r in rows:
        # EventLog の datetime column 名は schema 側で `timestamp` (codex round 1 P1)
        ts = getattr(r, "timestamp", None)
        if not ts:
            continue
        if ts.strftime("%Y-%m-%d") != today:
            continue
        try:
            import json as _j
            usd = float(_j.loads(r.data or "{}").get("usd", 0))
            total += usd
        except (ValueError, TypeError):
            continue
    return round(total, 4)


def remaining_budget_usd(db: Session) -> float:
    """本日残り予算。cap 0 なら無制限を意味し、999999 を返す。"""
    if DAILY_AI_BUDGET_USD <= 0:
        return 999_999.0
    used = daily_total_usd(db)
    return round(DAILY_AI_BUDGET_USD - used, 4)


def check_budget_or_raise(db: Session, estimated_cost: float) -> None:
    """この操作で本日上限を超えるなら RuntimeError を投げる。

    呼び出し側 (endpoint) は HTTPException(429) として返す。
    """
    if DAILY_AI_BUDGET_USD <= 0:
        return  # cap 無効
    remaining = remaining_budget_usd(db)
    if estimated_cost > remaining:
        raise RuntimeError(
            f"Daily AI budget exceeded: estimated ${estimated_cost:.4f} > remaining ${remaining:.4f} "
            f"(daily cap ${DAILY_AI_BUDGET_USD:.2f}). Wait until UTC midnight or raise DAILY_AI_BUDGET_USD."
        )


# プロセス内のシリアル化 lock — 同時 reserve_or_raise の race を防ぐ
_BUDGET_LOCK = threading.Lock()


def reserve_or_raise(
    db: Session,
    provider: str,
    operation: str,
    estimated_cost: float,
    metadata: Optional[dict] = None,
) -> None:
    """予算チェック + record_spend を同一 lock の中で atomic に実行する。

    codex round 3 P2: check_budget_or_raise → 後で record_spend だと concurrent
    request が両方通って overspend する。check + record を seriall に。

    制限: プロセス内 threading.Lock のため複数 process / 複数 host では使えない。
    本格運用では Redis WATCH/MULTI 等で置換のこと。
    """
    with _BUDGET_LOCK:
        check_budget_or_raise(db, estimated_cost)
        # 予算 OK → ここで record して以後の concurrent request の見え高を上げる
        record_spend(db, provider, operation, estimated_cost, metadata)


def record_refund(
    db: Session,
    provider: str,
    operation: str,
    refund_usd: float,
    metadata: Optional[dict] = None,
) -> None:
    """job 失敗時に reserve したコストを返金 (負の usd で record)。"""
    if refund_usd <= 0:
        return
    record_spend(
        db, provider, operation, -refund_usd,
        metadata={"refund": True, **(metadata or {})},
    )


def record_spend(
    db: Session,
    provider: str,
    operation: str,
    estimated_usd: float,
    metadata: Optional[dict] = None,
) -> None:
    """支出を event_logs に記録 (失敗は warning ログのみで握りつぶす — 主処理は止めない)。"""
    from api.models.schemas import EventLog
    import json as _j
    try:
        log = EventLog(
            event_category="ai_cost",
            event_type="spent",
            data=_j.dumps({
                "provider": provider,
                "operation": operation,
                "usd": estimated_usd,
                **(metadata or {}),
            }),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("[cost_tracker] record_spend failed: %s", e)
