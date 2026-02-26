"""プロジェクション制御ルーター (OSC + WebSocket)"""

import io
import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.models.database import get_db
from api.models.schemas import (
    PlaybackLog,
    ProjectionConfig,
    ProjectionPlayRequest,
    ProjectionTriggerRequest,
    ProjectionStatusResponse,
    PlaybackLogResponse,
    BirthdayReservation,
)
from api.services.osc_controller import osc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projection", tags=["projection"])


# ─── 再生状態の管理 (インメモリ) ──────────────────────────────────────────

class ZoneState:
    """個別ゾーンの投影状態"""
    def __init__(self, zone_id: int):
        self.zone_id = zone_id
        self.content_path: Optional[str] = None
        self.brightness: float = 1.0
        self.is_playing: bool = False


class PlaybackState:
    def __init__(self):
        self.state: str = "idle"  # idle / playing / paused
        self.timeline_id: Optional[int] = None
        self.table_id: Optional[str] = None
        self.started_at: Optional[float] = None
        self.paused_elapsed: float = 0.0
        self.current_content: Optional[str] = None
        self._log_id: Optional[int] = None
        # ゾーン個別状態
        self.zones: dict[int, ZoneState] = {i: ZoneState(i) for i in range(1, 5)}

    @property
    def elapsed(self) -> float:
        if self.state == "playing" and self.started_at:
            return time.time() - self.started_at + self.paused_elapsed
        return self.paused_elapsed

    def to_response(self) -> ProjectionStatusResponse:
        return ProjectionStatusResponse(
            state=self.state,
            timeline_id=self.timeline_id,
            table_id=self.table_id,
            elapsed=round(self.elapsed, 2),
            current_content=self.current_content,
        )

    def zone_snapshot(self) -> dict:
        return {
            zone_id: {
                "zone_id": z.zone_id,
                "content_path": z.content_path,
                "brightness": z.brightness,
                "is_playing": z.is_playing,
            }
            for zone_id, z in self.zones.items()
        }


_playback = PlaybackState()

# プリセット保存ストア (インメモリ)
_presets: dict[str, dict] = {}

# WebSocket 接続管理
_ws_clients: set[WebSocket] = set()


async def _broadcast_status():
    """全WebSocketクライアントにステータスを配信"""
    data = _playback.to_response().model_dump_json()
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    _ws_clients.difference_update(disconnected)


# ─── リクエストスキーマ ──────────────────────────────────────────────────

class ZoneContentRequest(BaseModel):
    content_path: str = Field(..., description="投影するコンテンツの絶対ファイルパス")


class ZoneBrightnessRequest(BaseModel):
    brightness: float = Field(..., ge=0.0, le=1.0, description="輝度 0.0〜1.0")


class TransitionRequest(BaseModel):
    type: str = Field("crossfade", description="トランジション種類")
    duration: float = Field(1.5, ge=0.0, le=10.0, description="トランジション時間（秒）")
    from_zone: Optional[int] = Field(None, ge=1, le=4, description="元ゾーンID (ゾーン間トランジション用)")
    to_zone: Optional[int] = Field(None, ge=1, le=4, description="先ゾーンID (ゾーン間トランジション用)")


class PresetSaveRequest(BaseModel):
    preset_id: str = Field(..., description="プリセット識別子")
    name: str = Field("", description="プリセット表示名")
    description: str = Field("", description="プリセットの説明")


class PresetLoadRequest(BaseModel):
    preset_id: str = Field(..., description="読み込むプリセット識別子")


# ─── レスポンススキーマ ──────────────────────────────────────────────────

class ZoneStateResponse(BaseModel):
    zone_id: int
    content_path: Optional[str]
    brightness: float
    is_playing: bool


class PresetResponse(BaseModel):
    preset_id: str
    name: str
    description: str
    created_at: str
    zones: dict


class ProjectionPreviewResponse(BaseModel):
    zones: list[ZoneStateResponse]
    playback: dict
    canvas: dict


# ─── 既存エンドポイント ───────────────────────────────────────────────────

@router.post("/play", response_model=ProjectionStatusResponse)
async def play(body: ProjectionPlayRequest, db: Session = Depends(get_db)):
    """タイムライン再生を開始"""
    osc.play(body.timeline_id, body.table_id)

    _playback.state = "playing"
    _playback.timeline_id = body.timeline_id
    _playback.table_id = body.table_id
    _playback.started_at = time.time()
    _playback.paused_elapsed = 0.0

    # 再生ログを記録
    log = PlaybackLog(
        timeline_id=body.timeline_id,
        started_at=datetime.now(),
        table_id=body.table_id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    _playback._log_id = log.id

    await _broadcast_status()
    return _playback.to_response()


@router.post("/pause", response_model=ProjectionStatusResponse)
async def pause():
    """再生を一時停止"""
    if _playback.state == "playing":
        _playback.paused_elapsed = _playback.elapsed
        _playback.started_at = None
        _playback.state = "paused"
        osc.pause()
    await _broadcast_status()
    return _playback.to_response()


@router.post("/stop", response_model=ProjectionStatusResponse)
async def stop(db: Session = Depends(get_db)):
    """再生を停止"""
    osc.stop()

    # ログの完了時刻を記録
    if _playback._log_id:
        log = db.query(PlaybackLog).filter(PlaybackLog.id == _playback._log_id).first()
        if log:
            log.completed_at = datetime.now()
            db.commit()

    _playback.state = "idle"
    _playback.timeline_id = None
    _playback.table_id = None
    _playback.started_at = None
    _playback.paused_elapsed = 0.0
    _playback.current_content = None
    _playback._log_id = None

    await _broadcast_status()
    return _playback.to_response()


@router.post("/trigger/{event}", response_model=ProjectionStatusResponse)
async def trigger_event(
    event: str,
    body: Optional[ProjectionTriggerRequest] = None,
    db: Session = Depends(get_db),
):
    """特定イベントをトリガー (birthday, transition 等)"""
    data = body.data if body else {}

    if event == "birthday":
        # バースデー演出: reservation_id から情報を取得
        reservation_id = (data or {}).get("reservation_id")
        if reservation_id:
            reservation = (
                db.query(BirthdayReservation)
                .filter(BirthdayReservation.id == reservation_id)
                .first()
            )
            if reservation and reservation.character_video_path:
                osc.trigger_birthday(
                    reservation.guest_name,
                    reservation.character_video_path,
                )
                _playback.current_content = f"birthday:{reservation.guest_name}"

    elif event == "transition":
        transition_type = (data or {}).get("type", "crossfade")
        duration = (data or {}).get("duration", 1.0)
        osc.transition(transition_type, duration)

    await _broadcast_status()
    return _playback.to_response()


@router.get("/status", response_model=ProjectionStatusResponse)
def get_status():
    """現在の再生ステータスを取得"""
    return _playback.to_response()


# ─── ゾーン個別制御 ──────────────────────────────────────────────────────

@router.post("/zone/{zone_id}/content")
async def set_zone_content(zone_id: int, body: ZoneContentRequest):
    """特定ゾーンの映像を差し替え

    Args:
        zone_id: ゾーンID (1〜4)
        body.content_path: 投影するコンテンツの絶対ファイルパス
    """
    if zone_id not in range(1, 5):
        raise HTTPException(400, f"zone_id は 1〜4 の範囲で指定してください: {zone_id}")

    # OSCでTouchDesignerにゾーンコンテンツ切替を送信
    osc._send("/zone/content", zone_id, body.content_path)

    # インメモリ状態を更新
    _playback.zones[zone_id].content_path = body.content_path
    _playback.zones[zone_id].is_playing = True
    _playback.current_content = f"zone{zone_id}:{body.content_path}"

    await _broadcast_status()
    return {
        "zone_id": zone_id,
        "content_path": body.content_path,
        "status": "updated",
    }


@router.post("/zone/{zone_id}/brightness")
async def set_zone_brightness(zone_id: int, body: ZoneBrightnessRequest):
    """ゾーンの輝度を制御

    Args:
        zone_id: ゾーンID (1〜4)
        body.brightness: 輝度 0.0（消灯）〜1.0（最大輝度）
    """
    if zone_id not in range(1, 5):
        raise HTTPException(400, f"zone_id は 1〜4 の範囲で指定してください: {zone_id}")

    # OSCでTouchDesignerに輝度制御を送信
    osc._send("/zone/brightness", zone_id, body.brightness)

    # インメモリ状態を更新
    _playback.zones[zone_id].brightness = body.brightness

    return {
        "zone_id": zone_id,
        "brightness": body.brightness,
        "status": "updated",
    }


@router.get("/zone/{zone_id}", response_model=ZoneStateResponse)
def get_zone_state(zone_id: int):
    """ゾーンの現在状態を取得"""
    if zone_id not in range(1, 5):
        raise HTTPException(400, f"zone_id は 1〜4 の範囲で指定してください: {zone_id}")

    z = _playback.zones[zone_id]
    return ZoneStateResponse(
        zone_id=z.zone_id,
        content_path=z.content_path,
        brightness=z.brightness,
        is_playing=z.is_playing,
    )


@router.get("/zones")
def get_all_zones():
    """全ゾーンの状態を取得"""
    return {
        "zones": [
            {
                "zone_id": z.zone_id,
                "content_path": z.content_path,
                "brightness": z.brightness,
                "is_playing": z.is_playing,
            }
            for z in _playback.zones.values()
        ]
    }


# ─── トランジション制御 ───────────────────────────────────────────────────

@router.post("/transition")
async def execute_transition(body: TransitionRequest):
    """トランジションを実行

    ゾーン間トランジション (from_zone, to_zone 指定時):
        指定ゾーン間でエフェクトを適用

    全体トランジション (from_zone, to_zone 未指定時):
        テーブル全体にトランジションを適用
    """
    valid_types = [
        "crossfade", "cut", "fade_black", "fade_white",
        "wipe_left", "wipe_right", "sparkle", "ripple", "zoom_in",
    ]
    if body.type not in valid_types:
        raise HTTPException(400, f"無効なトランジションタイプ: {body.type}. 有効値: {valid_types}")

    if body.from_zone is not None and body.to_zone is not None:
        # ゾーン間トランジション
        osc._send("/zone_transition", body.from_zone, body.to_zone, body.type, body.duration)
        message = f"Zone{body.from_zone}→Zone{body.to_zone} {body.type} ({body.duration}s)"
    else:
        # 全体トランジション
        osc.transition(body.type, body.duration)
        message = f"全体 {body.type} ({body.duration}s)"

    await _broadcast_status()
    return {
        "type": body.type,
        "duration": body.duration,
        "from_zone": body.from_zone,
        "to_zone": body.to_zone,
        "message": message,
        "status": "triggered",
    }


# ─── プリセット管理 ───────────────────────────────────────────────────────

@router.post("/presets", response_model=PresetResponse)
def save_preset(body: PresetSaveRequest):
    """現在の投影パターンをプリセットとして保存

    保存内容:
        - 各ゾーンのコンテンツパス
        - 各ゾーンの輝度設定
        - 各ゾーンの再生状態
    """
    snapshot = _playback.zone_snapshot()
    preset = {
        "preset_id": body.preset_id,
        "name": body.name or body.preset_id,
        "description": body.description,
        "created_at": datetime.now().isoformat(),
        "zones": snapshot,
    }
    _presets[body.preset_id] = preset

    logger.info("Preset saved: %s", body.preset_id)
    return PresetResponse(**preset)


@router.get("/presets", response_model=list[PresetResponse])
def list_presets():
    """保存済みプリセット一覧を取得"""
    return [PresetResponse(**p) for p in _presets.values()]


@router.get("/presets/{preset_id}", response_model=PresetResponse)
def get_preset(preset_id: str):
    """指定プリセットを取得"""
    if preset_id not in _presets:
        raise HTTPException(404, f"プリセットが見つかりません: {preset_id}")
    return PresetResponse(**_presets[preset_id])


@router.post("/presets/{preset_id}/load")
async def load_preset(preset_id: str):
    """プリセットを読み込んで投影に適用

    各ゾーンの設定を一括でTouchDesignerに送信する
    """
    if preset_id not in _presets:
        raise HTTPException(404, f"プリセットが見つかりません: {preset_id}")

    preset = _presets[preset_id]

    # OSCでTouchDesignerにプリセット適用を通知
    osc._send("/preset/load", preset_id)

    # 各ゾーン状態を復元
    for zone_id_str, zone_data in preset["zones"].items():
        zone_id = int(zone_id_str)
        if zone_id in _playback.zones:
            _playback.zones[zone_id].content_path = zone_data.get("content_path")
            _playback.zones[zone_id].brightness = zone_data.get("brightness", 1.0)
            _playback.zones[zone_id].is_playing = zone_data.get("is_playing", False)

            # コンテンツがある場合はOSCに送信
            if zone_data.get("content_path"):
                osc._send("/zone/content", zone_id, zone_data["content_path"])
            osc._send("/zone/brightness", zone_id, zone_data.get("brightness", 1.0))

    await _broadcast_status()
    return {
        "preset_id": preset_id,
        "name": preset["name"],
        "status": "applied",
    }


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str):
    """プリセットを削除"""
    if preset_id not in _presets:
        raise HTTPException(404, f"プリセットが見つかりません: {preset_id}")
    del _presets[preset_id]
    return {"preset_id": preset_id, "status": "deleted"}


# ─── ライブプレビュー ─────────────────────────────────────────────────────

@router.get("/preview")
def get_projection_preview(db: Session = Depends(get_db)):
    """現在の投影状態の概要情報を返す

    テーブルスペック、全ゾーンの状態、再生ステータスを返す。
    実際のJPEGフレームキャプチャはTouchDesignerが対応している場合に有効。
    """
    # ProjectionConfig からテーブル仕様を取得
    config = db.query(ProjectionConfig).first()
    if config:
        full_width = (config.pj_width * config.pj_count) - (config.blend_overlap * (config.pj_count - 1))
        full_height = config.pj_height
        zone_width = full_width // config.zone_count
        zone_height = full_height
        pj_count = config.pj_count
        blend_overlap = config.blend_overlap
        table_width_mm = config.table_width_mm
        table_height_mm = config.table_height_mm
    else:
        full_width = 5520
        full_height = 1200
        zone_width = 1380
        zone_height = 1200
        pj_count = 3
        blend_overlap = 120
        table_width_mm = 8120
        table_height_mm = 600

    zones_data = []
    for zone_id, z in _playback.zones.items():
        zone_x = (zone_id - 1) * zone_width
        zones_data.append({
            "zone_id": zone_id,
            "content_path": z.content_path,
            "brightness": z.brightness,
            "is_playing": z.is_playing,
            "canvas_x": zone_x,
            "canvas_y": 0,
            "canvas_w": zone_width,
            "canvas_h": zone_height,
        })

    projectors = []
    for i in range(pj_count):
        pj_x = i * (1920 - blend_overlap)
        projectors.append({
            "pj_id": i + 1,
            "canvas_x": pj_x,
            "canvas_w": 1920,
        })

    return {
        "playback": {
            "state": _playback.state,
            "timeline_id": _playback.timeline_id,
            "elapsed": round(_playback.elapsed, 2),
            "current_content": _playback.current_content,
        },
        "canvas": {
            "width": full_width,
            "height": full_height,
            "zone_width": zone_width,
            "zone_height": zone_height,
            "table_width_mm": table_width_mm,
            "table_height_mm": table_height_mm,
            "projectors": projectors,
        },
        "zones": zones_data,
        "presets_count": len(_presets),
    }


# ─── WebSocket ────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_status(ws: WebSocket):
    """リアルタイムステータス配信 WebSocket"""
    await ws.accept()
    _ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))

    try:
        # 接続直後に現在のステータスを送信
        await ws.send_text(_playback.to_response().model_dump_json())

        while True:
            # クライアントからのメッセージを待機 (切断検知用)
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_clients))
