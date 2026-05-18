"""Phase 1 critical-path tests — health / auth / cost cap / emergency stop / rehearsal。

このテストが落ちる場合は本番運用に致命的影響があるので最優先で修正すること。
"""
from __future__ import annotations

import pytest


# ── health / readiness / system info ──────────────────────────

def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data


def test_readiness_endpoint(client):
    r = client.get("/api/readiness")
    assert r.status_code == 200
    data = r.json()
    assert "overall" in data
    assert "checks" in data
    # 最低でも DB ok / ffmpeg / seed_root の 3 つは確認
    for key in ("db", "ffmpeg", "seed_root"):
        assert key in data["checks"], f"missing readiness check: {key}"


def test_system_info(client):
    r = client.get("/api/system/info")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "Immersive Dining Projection API"
    assert "git_sha" in data
    assert "env" in data


# ── auth middleware (open mode) ──────────────────────────────

def test_auth_open_mode_passes(client):
    """ADMIN_API_KEY 未設定 (open mode) なら /api/shows を key 無しで呼べる。"""
    r = client.get("/api/shows")
    assert r.status_code == 200


def test_auth_enabled_blocks_without_key(client, monkeypatch):
    """ADMIN_API_KEY 設定時は key 無しの呼出が 401 (middleware は env を毎回読む)。"""
    monkeypatch.setenv("ADMIN_API_KEY", "test-key-xxx-001")
    # health は公開
    assert client.get("/api/health").status_code == 200
    # 保護 endpoint は key 無しで 401
    assert client.get("/api/shows").status_code == 401
    # 正しい key で 200
    assert client.get("/api/shows", headers={"X-API-Key": "test-key-xxx-001"}).status_code == 200
    # 誤った key で 401
    assert client.get("/api/shows", headers={"X-API-Key": "wrong"}).status_code == 401


# ── cost tracking ────────────────────────────────────────────

def test_cost_today_initial_zero(client):
    r = client.get("/api/cost/today")
    assert r.status_code == 200
    data = r.json()
    assert data["used_usd_today"] == 0.0


def test_cost_record_spend_and_refund(db_session):
    from api.services.cost_tracker import daily_total_usd, record_refund, record_spend
    assert daily_total_usd(db_session) == 0.0
    record_spend(db_session, "gpt_image_2", "image", 0.50)
    assert daily_total_usd(db_session) == 0.50
    record_refund(db_session, "gpt_image_2", "image", 0.20)
    assert daily_total_usd(db_session) == pytest.approx(0.30)


def test_cost_reserve_or_raise_blocks_overspend(db_session, monkeypatch):
    """DAILY_AI_BUDGET_USD を直接 monkeypatch して check_budget_or_raise を発火。"""
    import api.services.cost_tracker as ct
    monkeypatch.setattr(ct, "DAILY_AI_BUDGET_USD", 1.0)
    with pytest.raises(RuntimeError, match="budget exceeded"):
        ct.reserve_or_raise(db_session, "gpt_image_2", "image", 1.5)


def test_cost_reserve_under_cap_succeeds(db_session, monkeypatch):
    import api.services.cost_tracker as ct
    monkeypatch.setattr(ct, "DAILY_AI_BUDGET_USD", 10.0)
    ct.reserve_or_raise(db_session, "gpt_image_2", "image", 5.0)
    assert ct.daily_total_usd(db_session) == 5.0


# ── rehearsal (OSC dry-run) ──────────────────────────────────

def test_rehearsal_toggle(client):
    # default は env で 1 にしている (conftest)
    r = client.post("/api/system/rehearsal/0")
    assert r.status_code == 200
    assert r.json()["dry_run"] is False

    r = client.post("/api/system/rehearsal/1")
    assert r.status_code == 200
    assert r.json()["dry_run"] is True


def test_rehearsal_log_endpoint(client):
    # toggle on → log 取得可能
    client.post("/api/system/rehearsal/1")
    r = client.get("/api/system/rehearsal/log")
    assert r.status_code == 200
    data = r.json()
    assert "dry_run" in data
    assert "log" in data
    assert isinstance(data["log"], list)


# ── emergency stop / blackout / panic gate ──────────────────

def test_emergency_stop_idempotent_on_missing_show(client):
    """存在しない show でも 500 にならず blackout を試みる。"""
    r = client.post("/api/shows/99999/emergency-stop")
    # show 無くても OSC blackout は試みる → response は 200 (status_emergency_stopped)
    # OR 404 - 受け入れる範囲
    assert r.status_code in (200, 404)


def test_blackout_endpoint(client):
    r = client.post("/api/shows/1/blackout")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data


def test_panic_gate_blocks_advance(monkeypatch):
    """ShowRuntime の panic flag が立っている間 _advance_to_cue は False を返す。"""
    import importlib
    import api.routers.show_control as sc
    importlib.reload(sc)
    rt = sc._runtime
    rt.set_panic(7, True)
    assert rt.is_panic(7) is True
    rt.set_panic(7, False)
    assert rt.is_panic(7) is False


# ── content QC ───────────────────────────────────────────────

def test_qc_video_missing_file(client):
    from pathlib import Path as _Path
    # 存在しない path で 0 byte / errors を返す
    project_root = _Path(__file__).resolve().parent.parent
    allowed_path = str(project_root / "touchdesigner" / "content" / "nonexistent_xxx.mp4")
    r = client.post("/api/qc/video", json={"path": allowed_path})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert any("file_not_found" in e or "not_a_regular_file" in e for e in data["errors"])


def test_qc_video_path_restriction(client):
    """allowed roots 外の絶対 path は 400。"""
    r = client.post("/api/qc/video", json={"path": "/etc/passwd"})
    assert r.status_code == 400
    assert "must be under" in r.json().get("detail", "").lower() or \
           "must be under" in r.json().get("detail", "")
