"""システム稼働状況 / health / readiness エンドポイント。

運用時の主要監視ポイント:
  - `/api/health` — 軽量 (DB/OSC など外部依存を触らない liveness probe)
  - `/api/readiness` — 重め (DB ping + 外部キー有無 + ffmpeg 等を確認、本番投入可否)
  - `/api/system/info` — バージョン / コミット sha / 環境情報の自己診断

これらは認証不要で公開する (操作画面 / オペレーター / 監視 SaaS から叩く前提)。
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.middleware.ratelimit import limiter
from api.models.database import get_db

router = APIRouter(prefix="/api", tags=["system"])

_START_TIME = time.monotonic()


def _git_sha_short() -> str:
    """git の HEAD SHA (短縮) を取得。失敗時は env 'GIT_SHA' fallback、それも無ければ 'unknown'。"""
    sha = os.environ.get("GIT_SHA", "")
    if sha:
        return sha[:10]
    try:
        head_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".git", "HEAD",
        )
        if not os.path.exists(head_path):
            return "unknown"
        with open(head_path, "r", encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            ref_path = os.path.join(
                os.path.dirname(head_path),
                head[5:].strip(),
            )
            if os.path.exists(ref_path):
                with open(ref_path, "r", encoding="utf-8") as f:
                    return f.read().strip()[:10]
        return head[:10]
    except OSError:
        return "unknown"


@router.get("/health")
@limiter.exempt  # 監視 probe は throttle されない (codex round 3 P2)
def health() -> dict[str, Any]:
    """軽量 liveness probe (DB 等外部依存を触らない)。

    監視 SaaS の uptime check / kubernetes liveness probe から叩く想定。
    Always returns 200 unless the FastAPI process itself is dying.
    """
    return {
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": int(time.time()),
    }


@router.get("/readiness")
@limiter.exempt  # readiness probe も throttle 対象外
def readiness(db: Session = Depends(get_db)) -> dict[str, Any]:
    """重め readiness probe。投入前 / 投入後の本番投入可否判定に使う。

    検査項目:
      1. DB ping (`SELECT 1`)
      2. ffmpeg / ffprobe の PATH 解決可否 (映像合成パイプライン必須)
      3. 主要 API key の DB or env 設定状況 (値は返さず、設定有無のみ)
      4. uploads/seeds ディレクトリ書込可否 (絵コンテ seed 受入先)

    各項目が 1 つでも fail なら overall='degraded'、致命なら 'unready'。
    """
    from api.models.schemas import AppSetting

    checks: dict[str, Any] = {}

    # 1. DB ping
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = {"ok": True}
    except Exception as e:
        checks["db"] = {"ok": False, "error": str(e)[:200]}

    # 2. ffmpeg / ffprobe
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    checks["ffmpeg"] = {"ok": bool(ffmpeg and ffprobe), "ffmpeg": ffmpeg, "ffprobe": ffprobe}

    # 3. API key 設定状況 (値は返さない)
    key_names = [
        "GEMINI_API_KEY", "FAL_API_KEY", "RUNWAY_API_KEY",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    ]
    keys: dict[str, bool] = {}
    for k in key_names:
        # env or DB AppSetting どちらかで値が入っているか
        env_present = bool(os.environ.get(k))
        db_present = False
        if not env_present:
            try:
                row = db.query(AppSetting).filter(AppSetting.key == k).first()
                db_present = bool(row and row.value)
            except Exception:
                db_present = False
        keys[k] = env_present or db_present
    checks["api_keys"] = keys

    # 4. uploads/seeds 書込可否
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    seed_root = os.environ.get(
        "SEED_IMAGES_ROOT",
        os.path.join(project_root, "api", "uploads", "seeds"),
    )
    try:
        os.makedirs(seed_root, exist_ok=True)
        test_file = os.path.join(seed_root, ".readiness_check")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks["seed_root"] = {"ok": True, "path": seed_root}
    except OSError as e:
        checks["seed_root"] = {"ok": False, "path": seed_root, "error": str(e)[:200]}

    # 総合判定
    db_ok = checks["db"]["ok"]
    ffmpeg_ok = checks["ffmpeg"]["ok"]
    seed_ok = checks["seed_root"]["ok"]
    any_key = any(keys.values())

    if not db_ok or not ffmpeg_ok or not seed_ok:
        overall = "unready"
    elif not any_key:
        overall = "degraded"  # 動くが AI 生成は placeholder にしか落ちない
    else:
        overall = "ready"

    return {
        "overall": overall,
        "checks": checks,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
    }


@router.get("/cost/today")
def cost_today(db: Session = Depends(get_db)) -> dict[str, Any]:
    """本日 (UTC) の AI 生成コスト累計と残予算。

    UI のサイドバーに表示する想定。デイリー cap が DAILY_AI_BUDGET_USD で
    定義されていて、超過時は生成 endpoint が 429 で reject する。
    """
    from api.services.cost_tracker import (
        DAILY_AI_BUDGET_USD,
        daily_total_usd,
        remaining_budget_usd,
    )
    used = daily_total_usd(db)
    remaining = remaining_budget_usd(db)
    cap_active = DAILY_AI_BUDGET_USD > 0
    return {
        "used_usd_today": used,
        "remaining_usd": remaining if cap_active else None,
        "daily_cap_usd": DAILY_AI_BUDGET_USD if cap_active else None,
        "cap_active": cap_active,
        "percent_used": round((used / DAILY_AI_BUDGET_USD) * 100, 1) if cap_active else None,
    }


@router.post("/system/rehearsal/{enable}")
def set_rehearsal_mode(enable: int) -> dict[str, Any]:
    """Rehearsal mode (OSC dry-run) を on/off する。

    - enable=1: 以降の OSC 送信は TouchDesigner に届かず、ログに残るだけ。
      cue 進行 / DB 状態更新 / SSE は通常通り。TD 不在でも show を回せる。
    - enable=0: 通常モード復帰。dry_run ログはクリア。

    URL 例:
        POST /api/system/rehearsal/1  → dry-run on
        POST /api/system/rehearsal/0  → 通常モードへ
    """
    from api.services.osc_controller import osc
    osc.set_dry_run(bool(enable))
    return {"dry_run": osc.is_dry_run(), "log_count": len(osc.get_dry_run_log(10000))}


@router.get("/system/rehearsal/log")
def get_rehearsal_log(limit: int = 100) -> dict[str, Any]:
    """rehearsal 中に「送るはずだったメッセージ」を時系列で返す。"""
    from api.services.osc_controller import osc
    return {
        "dry_run": osc.is_dry_run(),
        "log": osc.get_dry_run_log(limit),
    }


@router.get("/system/info")
def system_info() -> dict[str, Any]:
    """自己診断 — version / git sha / 環境設定 / 現在時刻"""
    return {
        "service": "Immersive Dining Projection API",
        "version": "0.1.0",
        "git_sha": _git_sha_short(),
        "started_at_uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "python_version": os.environ.get("PYTHON_VERSION", ""),
        "env": {
            "OSC_TD_HOST": os.environ.get("OSC_TD_HOST", "127.0.0.1"),
            "OSC_TD_PORT": int(os.environ.get("OSC_TD_PORT", "7000")),
            "OSC_ACK_ENABLED": os.environ.get("OSC_ACK_ENABLED", "0"),
            "SEED_IMAGES_ROOT_SET": bool(os.environ.get("SEED_IMAGES_ROOT")),
            "OPENAI_IMAGE_MODEL": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        },
    }
