"""TouchDesignerとのOSC通信コントローラー"""

import logging
from typing import Optional

from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder

logger = logging.getLogger(__name__)

# TouchDesigner のデフォルト受信先
TD_HOST = "127.0.0.1"
TD_PORT = 7000


class OSCController:
    """TouchDesigner へ OSC メッセージを送信するコントローラー"""

    def __init__(self, host: str = TD_HOST, port: int = TD_PORT):
        self.host = host
        self.port = port
        self._client: Optional[udp_client.SimpleUDPClient] = None

    @property
    def client(self) -> udp_client.SimpleUDPClient:
        if self._client is None:
            self._client = udp_client.SimpleUDPClient(self.host, self.port)
            logger.info("OSC client connected: %s:%d", self.host, self.port)
        return self._client

    def _send(self, address: str, *args) -> bool:
        """OSCメッセージを送信。失敗時は False を返す"""
        try:
            self.client.send_message(address, list(args))
            logger.info("OSC sent: %s %s", address, args)
            return True
        except Exception as e:
            logger.error("OSC send error: %s – %s", address, e)
            return False

    # ── 再生制御 ──────────────────────────────────────────────

    def play(self, timeline_id: int, table_id: Optional[str] = None) -> bool:
        """タイムライン再生開始"""
        args = [timeline_id]
        if table_id:
            args.append(table_id)
        return self._send("/play", *args)

    def pause(self) -> bool:
        return self._send("/pause")

    def stop(self) -> bool:
        return self._send("/stop")

    # ── コンテンツ ────────────────────────────────────────────

    def load_content(self, file_path: str, zone: str) -> bool:
        """指定ゾーンにコンテンツをロード"""
        return self._send("/content/load", file_path, zone)

    def transition(self, transition_type: str, duration: float = 1.0) -> bool:
        """トランジション実行"""
        return self._send("/transition", transition_type, duration)

    # ── バースデー演出 ────────────────────────────────────────

    def trigger_birthday(self, guest_name: str, video_path: str) -> bool:
        """バースデー演出をトリガー"""
        return self._send("/birthday/trigger", guest_name, video_path)

    # ── 料理同期 ──────────────────────────────────────────────

    def course_serve(self, session_id: int, course_key: str) -> bool:
        """料理提供トリガー: テーブルへ配膳完了時に発火"""
        return self._send("/course/serve", session_id, course_key)

    def course_clear(self, session_id: int, course_key: str) -> bool:
        """皿下げトリガー: 皿を下げた後に発火"""
        return self._send("/course/clear", session_id, course_key)

    def course_preload(self, course_key: str) -> bool:
        """次コース演出の事前ロード（提供 30 秒前）"""
        return self._send("/course/preload", course_key)

    def allergen_alert(self, session_id: int) -> bool:
        """アレルギー対応コース提供時の視覚的アラート"""
        return self._send("/course/allergen_alert", session_id)

    def session_start(self, session_id: int, table_number: int) -> bool:
        """セッション開始通知"""
        return self._send("/session/start", session_id, table_number)

    def session_complete(self, session_id: int) -> bool:
        """セッション完了通知"""
        return self._send("/session/complete", session_id)


# シングルトンインスタンス
osc = OSCController()
