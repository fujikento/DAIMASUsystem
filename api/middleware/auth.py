"""API key middleware — オペレーター画面 / 監視サービスからの呼び出しを保護する。

設計方針:
  - 本番では `ADMIN_API_KEY` env を必須にする (`X-API-Key` ヘッダで比較)。
  - 設定なし or 空文字 → middleware は no-op (開発時 / 既存ユーザーの後方互換)。
    起動ログでは警告を出すので運用者は気づける。
  - 公開すべきパスは UNAUTHENTICATED_PATHS で個別許可:
      `/api/health`, `/api/readiness`, `/api/system/info`, `/docs`, `/openapi.json`,
      `/redoc`, `/static/*`, `/api/storyboards/events/stream` (SSE)
  - キーの比較は `hmac.compare_digest` (timing attack 対策)
  - 公開 endpoint 以外で key 不一致 → 401 を JSON で返す
"""
from __future__ import annotations

import hmac
import logging
import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# 認証不要パス (先頭一致)
UNAUTHENTICATED_PATH_PREFIXES = (
    "/api/health",
    "/api/readiness",
    "/api/system/info",
    "/api/storyboards/events/stream",  # SSE: EventSource はカスタムヘッダ送れない
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",
    "/favicon.ico",
)

# codex round 1 P1: prefix "/" を入れると全 path に match して bypass されるので外し、
# root メタは exact match で別判定。
UNAUTHENTICATED_PATH_EXACT = {"/"}

_ALLOW_PATH_RE = re.compile(
    r"^(" + "|".join(re.escape(p) for p in UNAUTHENTICATED_PATH_PREFIXES) + r")"
)


def _is_unauthenticated_path(path: str) -> bool:
    return path in UNAUTHENTICATED_PATH_EXACT or bool(_ALLOW_PATH_RE.match(path))


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API key by `X-API-Key` header. CORS preflight (OPTIONS) は素通し。

    ADMIN_API_KEY は __init__ で cache せず、毎リクエストで env を読む。
    これにより:
      - テストで monkeypatch.setenv が即座に反映される
      - 運用中に env をリロードして key rotation できる (systemctl reload 等)
    """

    def __init__(self, app: ASGIApp, expected_key: str | None = None) -> None:
        super().__init__(app)
        # 起動時 1 度のみ警告 (毎回出すとログがうるさい)
        # expected_key 引数指定時はそれを優先 (テスト用シーム)
        self._init_override = (expected_key or "").strip() or None
        startup_key = self._current_key()
        if not startup_key:
            logger.warning(
                "[AUTH] ADMIN_API_KEY is not set — auth middleware running in OPEN mode. "
                "Set ADMIN_API_KEY env (or .env) before production deployment."
            )
        else:
            logger.info(
                "[AUTH] ADMIN_API_KEY configured (len=%d). All /api/* endpoints require "
                "'X-API-Key' header except: %s",
                len(startup_key),
                ", ".join(UNAUTHENTICATED_PATH_PREFIXES),
            )

    def _current_key(self) -> str:
        if self._init_override is not None:
            return self._init_override
        return (os.environ.get("ADMIN_API_KEY") or "").strip()

    async def dispatch(self, request: Request, call_next):
        expected = self._current_key()

        # OPEN mode: key 未設定なら誰でも通す (backward compat)
        if not expected:
            return await call_next(request)

        # CORS preflight は常に通す
        if request.method == "OPTIONS":
            return await call_next(request)

        # 公開 path は素通し
        if _is_unauthenticated_path(request.url.path):
            return await call_next(request)

        # X-API-Key ヘッダ照合
        supplied = request.headers.get("x-api-key", "").strip()
        if not supplied:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required. Set 'X-API-Key' header.",
                    "code": "no_api_key",
                },
            )
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key.", "code": "invalid_api_key"},
            )

        return await call_next(request)
