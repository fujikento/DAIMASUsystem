"""Pytest fixtures — テスト用 DB + TestClient + env cleanup。

戦略: session-scope で env を 1 度だけセットし、function-scope で DB tables を
drop+create することで isolated state を保つ (module reload は副作用が多すぎるので避ける)。
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

# プロジェクトルートを sys.path に
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# === session-scope env setup (must be set BEFORE any api.* import) ===
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db", prefix="daimasu_pytest_")
os.close(_TEST_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["OSC_ACK_ENABLED"] = "0"
os.environ["OSC_DRY_RUN"] = "1"
os.environ["OPENAI_API_KEY"] = ""
os.environ["FAL_API_KEY"] = ""
os.environ["RUNWAY_API_KEY"] = ""
os.environ["ADMIN_API_KEY"] = ""
os.environ["DAILY_AI_BUDGET_USD"] = "50.0"


@pytest.fixture(autouse=True)
def reset_db():
    """各テストで tables を drop+create して isolated state を保つ。"""
    from api.models.database import Base, engine
    # 既存テーブル全削除 → 全モデルを import してから再作成
    import api.models.schemas  # noqa: F401  ensure all models register on Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def temp_db():
    """互換: session DB path を返す (古いテストとの互換)。"""
    yield _TEST_DB_PATH


@pytest.fixture
def client():
    """TestClient — session-scope app。"""
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    """SessionLocal を直接使うテスト用。"""
    from api.models.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


def pytest_sessionfinish(session, exitstatus):
    """テスト session 終了時に temp DB を削除。"""
    try:
        os.remove(_TEST_DB_PATH)
    except OSError:
        pass
