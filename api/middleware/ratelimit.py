"""レートリミット — 公開 endpoint の DoS / 生成 API コスト乱用を防ぐ。

slowapi (Flask-Limiter ベース) を採用。in-memory バックエンドで運用想定 (単一 process)。
複数 process / 複数 host で分散させたい場合は `storage_uri="redis://..."` に切替。

policy:
  - 生成系 endpoint (画像 / 動画) は 1 IP あたり 30 req/分
  - その他 API 全般は 1 IP あたり 120 req/分
  - 監視 / health は無制限 (auth middleware の UNAUTHENTICATED_PATHS とは別管理)

各 endpoint で `@limiter.limit("30/minute")` を貼ることで個別に上書き可能。
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request
from fastapi.responses import JSONResponse


def _identify(request: Request) -> str:
    """ID 戦略: 認証通過した API key を持つ場合のみ key 毎の bucket、それ以外は IP。

    codex round 2 P2: open mode では key 検証が走らないため、攻撃者が
    `X-API-Key: random123` `X-API-Key: random456` ... と変えると無限に
    fresh bucket を作って rate limit を bypass できてしまう。これを防ぐため、
    expected key と一致した場合のみ key bucket を使い、それ以外は IP。
    """
    api_key = request.headers.get("x-api-key", "").strip()
    expected = os.environ.get("ADMIN_API_KEY", "").strip()
    if api_key and expected:
        # hmac.compare_digest 相当の constant-time compare
        import hmac as _hmac
        if _hmac.compare_digest(api_key, expected):
            return f"key:{api_key[:16]}"
    return f"ip:{get_remote_address(request)}"


# default が緩めな順に並べる (specific endpoint で上書きする)
_DEFAULT_LIMIT = os.environ.get("RATE_LIMIT_DEFAULT", "120/minute")
_GENERATION_LIMIT = os.environ.get("RATE_LIMIT_GENERATION", "30/minute")


limiter = Limiter(
    key_func=_identify,
    default_limits=[_DEFAULT_LIMIT],
    headers_enabled=True,  # X-RateLimit-Limit / X-RateLimit-Remaining を response に
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 を JSON で返す (default は HTML)"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "code": "rate_limited",
        },
    )


# 生成系で使うデコレーター shortcut
def generation_rate_limit():
    """画像/動画生成系の endpoint に付与する decorator factory。"""
    return limiter.limit(_GENERATION_LIMIT)


__all__ = [
    "limiter",
    "rate_limit_exceeded_handler",
    "generation_rate_limit",
    "_GENERATION_LIMIT",
    "_DEFAULT_LIMIT",
]
