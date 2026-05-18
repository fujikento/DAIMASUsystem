"""TouchDesignerとのOSC通信コントローラー

精度上の要件 (audit 2026-05-16):
- UDP は fire-and-forget なのでパケットロスを検知できない。送信側は
  sequence id と monotonic timestamp を付けることで、TouchDesigner 側
  ロガーで欠損を検知できるようにする。
- ack を返す TD パッチがある場合 (env OSC_ACK_ENABLED=1) は ack を待ち、
  timeout したら retry する。ack 無効環境では送信のみ。
- send は thread-safe にする。FastAPI background task と show_control
  asyncio task から同時に呼ばれる前提。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

logger = logging.getLogger(__name__)

# TouchDesigner のデフォルト受信先
TD_HOST = os.environ.get("OSC_TD_HOST", "127.0.0.1")
TD_PORT = int(os.environ.get("OSC_TD_PORT", "7000"))

# Ack 機能 (TouchDesigner 側パッチが /ack/<seq> を返す前提)
OSC_ACK_ENABLED = os.environ.get("OSC_ACK_ENABLED", "0") == "1"
OSC_ACK_HOST = os.environ.get("OSC_ACK_HOST", "127.0.0.1")
OSC_ACK_PORT = int(os.environ.get("OSC_ACK_PORT", "7001"))
OSC_ACK_TIMEOUT = float(os.environ.get("OSC_ACK_TIMEOUT", "0.5"))  # seconds
OSC_RETRY = int(os.environ.get("OSC_RETRY", "2"))


@dataclass
class OscSendResult:
    """OSC 送信結果。fire-and-forget でも返り値は持つ。"""

    address: str
    seq: int
    sent: bool                 # socket write 成功
    acked: bool                # TD からの ack 受信 (ack 無効環境では常に False)
    attempts: int              # 試行回数
    latency_ms: Optional[float]  # ack mode 時の往復遅延
    ack_required: bool = False   # この送信が ack を期待していたか
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """シーケンスとして「成功」と見なせるか。ack 期待の送信は acked、それ以外は sent。"""
        if self.ack_required:
            return self.acked
        return self.sent


class OSCController:
    """TouchDesigner へ OSC メッセージを送信するコントローラー

    Thread-safe: 内部 lock で複数スレッドから同時呼び出しを直列化する。
    Ack mode: OSC_ACK_ENABLED=1 のとき、各送信に seq を埋め込んで TD から
    /ack/<seq> を待つ。timeout 時は OSC_RETRY 回まで再送。
    """

    def __init__(
        self,
        host: str = TD_HOST,
        port: int = TD_PORT,
        ack_enabled: Optional[bool] = None,
        ack_host: str = OSC_ACK_HOST,
        ack_port: int = OSC_ACK_PORT,
        ack_timeout: float = OSC_ACK_TIMEOUT,
        retry: int = OSC_RETRY,
    ):
        self.host = host
        self.port = port
        self._client: Optional[udp_client.SimpleUDPClient] = None
        self._send_lock = threading.Lock()
        self._seq = 0

        self.ack_enabled = OSC_ACK_ENABLED if ack_enabled is None else ack_enabled
        self.ack_host = ack_host
        self.ack_port = ack_port
        self.ack_timeout = ack_timeout
        self.retry = max(0, retry)

        # ── Phase 1.6 rehearsal mode ──
        # dry_run=True なら client.send_message を呼ばずに ok=True を返す。
        # ステージリハーサルで TouchDesigner を起動せずに show flow / timing を
        # 検証する。env OSC_DRY_RUN=1 で起動時に有効化、または set_dry_run() で
        # 動的に切替可能。
        self._dry_run = os.environ.get("OSC_DRY_RUN", "0") == "1"
        # dry_run 中の送信を記録 (UI で「rehearsal で何が送られたか」を確認)
        self._dry_run_log: list[dict] = []
        self._dry_run_log_max = 500

        # ack 受信用イベント: seq -> threading.Event + arrival time
        self._ack_events: dict[int, threading.Event] = {}
        self._ack_times: dict[int, float] = {}
        self._ack_lock = threading.Lock()

        self._ack_server: Optional[ThreadingOSCUDPServer] = None
        self._ack_thread: Optional[threading.Thread] = None

        if self.ack_enabled:
            self._start_ack_server()

    # ── rehearsal (dry-run) mode 制御 ─────────────────────────
    def set_dry_run(self, enabled: bool) -> None:
        """rehearsal mode の動的切替。TD 不在でも show flow を流せる。"""
        self._dry_run = bool(enabled)
        if not enabled:
            self._dry_run_log.clear()
        logger.info("[OSC] dry_run = %s", self._dry_run)

    def is_dry_run(self) -> bool:
        return self._dry_run

    def get_dry_run_log(self, limit: int = 100) -> list[dict]:
        """rehearsal 中に「送るはずだったメッセージ」のログを返す。"""
        return self._dry_run_log[-limit:]

    # ── ack サーバー (TD → API) ────────────────────────────────

    def _on_ack(self, address: str, *args) -> None:
        """Ack を受信する。

        対応する 2 形式:
        - `/ack <seq>` -- args[0] に seq
        - `/ack/<seq>` -- address path 末尾に seq (args 空でもOK)
        """
        seq: Optional[int] = None
        if args:
            try:
                seq = int(args[0])
            except (TypeError, ValueError):
                seq = None
        if seq is None and "/" in address:
            tail = address.rsplit("/", 1)[-1]
            try:
                seq = int(tail)
            except ValueError:
                return
        if seq is None:
            return
        with self._ack_lock:
            self._ack_times[seq] = time.monotonic()
            event = self._ack_events.get(seq)
            if event is not None:
                event.set()

    def _start_ack_server(self) -> None:
        try:
            dispatcher = Dispatcher()
            dispatcher.map("/ack", self._on_ack)
            dispatcher.map("/ack/*", self._on_ack)
            self._ack_server = ThreadingOSCUDPServer(
                (self.ack_host, self.ack_port), dispatcher
            )
            self._ack_thread = threading.Thread(
                target=self._ack_server.serve_forever,
                name="OSCAckServer",
                daemon=True,
            )
            self._ack_thread.start()
            logger.info(
                "OSC ack server listening on %s:%d (timeout=%.2fs, retry=%d)",
                self.ack_host, self.ack_port, self.ack_timeout, self.retry,
            )
        except Exception as e:
            logger.error("OSC ack server failed to start: %s. Falling back to fire-and-forget.", e)
            self.ack_enabled = False
            self._ack_server = None
            self._ack_thread = None

    # ── 送信 ──────────────────────────────────────────────────

    @property
    def client(self) -> udp_client.SimpleUDPClient:
        if self._client is None:
            self._client = udp_client.SimpleUDPClient(self.host, self.port)
            logger.info("OSC client connected: %s:%d", self.host, self.port)
        return self._client

    def _next_seq(self) -> int:
        with self._send_lock:
            self._seq += 1
            return self._seq

    def send(self, address: str, *args, wait_ack: Optional[bool] = None) -> OscSendResult:
        """OSC メッセージを送信し、結果を返す。

        Args:
            address: OSC アドレス
            *args: ペイロード
            wait_ack: True なら ack を待つ。None のときは self.ack_enabled に従う。

        ワイヤープロトコル:
            - ack mode 有効時のみ ``[seq, ts_ms, *args]`` を送信する。
              TD 側パッチは args[0]/args[1] を seq/ts として読み取り、残りを実引数として使う。
            - fire-and-forget 時は ``args`` をそのまま送信する。
              既存 TD パッチが ``/play <timeline_id>`` のように 1 引数目を実データとして
              扱うため、seq 等を勝手に prepend すると後方互換が壊れる
              (codex review 2026-05-16 P1)。
        """
        seq = self._next_seq()
        do_wait = self.ack_enabled if wait_ack is None else wait_ack

        # ── rehearsal mode: 実送信しない、ログだけ残して ok=True を返す ──
        if self._dry_run:
            entry = {
                "seq": seq, "address": address, "args": list(args),
                "ts_ms": int(time.monotonic() * 1000),
            }
            self._dry_run_log.append(entry)
            if len(self._dry_run_log) > self._dry_run_log_max:
                self._dry_run_log = self._dry_run_log[-self._dry_run_log_max:]
            logger.debug("[OSC dry_run] %s %s", address, args)
            return OscSendResult(
                address=address, seq=seq, sent=True, acked=True,
                attempts=1, latency_ms=0.0,
                ack_required=do_wait,
            )

        if do_wait and self._ack_server is not None:
            ts_ms = int(time.monotonic() * 1000)
            full_args = [seq, ts_ms, *args]
            return self._send_with_ack(address, seq, full_args)
        # 後方互換: 既存の args をそのまま送る
        return self._send_once(address, seq, list(args))

    def _send_once(self, address: str, seq: int, full_args: list) -> OscSendResult:
        try:
            with self._send_lock:
                self.client.send_message(address, full_args)
            logger.info("OSC sent: %s seq=%d args=%s", address, seq, full_args)
            return OscSendResult(address=address, seq=seq, sent=True, acked=False,
                                 attempts=1, latency_ms=None, ack_required=False)
        except Exception as e:
            logger.error("OSC send error: %s seq=%d – %s", address, seq, e)
            return OscSendResult(address=address, seq=seq, sent=False, acked=False,
                                 attempts=1, latency_ms=None, ack_required=False, error=str(e))

    def _send_with_ack(self, address: str, seq: int, full_args: list) -> OscSendResult:
        event = threading.Event()
        with self._ack_lock:
            self._ack_events[seq] = event

        last_error: Optional[str] = None
        attempts = 0
        sent_ok = False
        try:
            for attempt in range(self.retry + 1):
                attempts = attempt + 1
                start = time.monotonic()
                try:
                    with self._send_lock:
                        self.client.send_message(address, full_args)
                    sent_ok = True
                except Exception as e:
                    sent_ok = False
                    last_error = str(e)
                    logger.error("OSC send error (attempt %d): %s – %s", attempts, address, e)

                if not sent_ok:
                    continue

                if event.wait(self.ack_timeout):
                    latency_ms = (time.monotonic() - start) * 1000
                    logger.info(
                        "OSC ack: %s seq=%d latency=%.1fms attempt=%d",
                        address, seq, latency_ms, attempts,
                    )
                    return OscSendResult(
                        address=address, seq=seq, sent=True, acked=True,
                        attempts=attempts, latency_ms=latency_ms,
                        ack_required=True,
                    )
                last_error = f"ack timeout {self.ack_timeout}s"
                logger.warning(
                    "OSC ack timeout: %s seq=%d attempt=%d", address, seq, attempts,
                )

            return OscSendResult(
                address=address, seq=seq, sent=sent_ok, acked=False,
                attempts=attempts, latency_ms=None,
                ack_required=True, error=last_error,
            )
        finally:
            with self._ack_lock:
                self._ack_events.pop(seq, None)
                self._ack_times.pop(seq, None)

    # Backward-compat shim: 旧コードが返り値を bool で見ているケースに対応。
    def _send(self, address: str, *args) -> bool:
        return self.send(address, *args).ok

    # ── 再生制御 ──────────────────────────────────────────────

    def play(self, timeline_id: int, table_id: Optional[str] = None) -> OscSendResult:
        args = [timeline_id]
        if table_id:
            args.append(table_id)
        return self.send("/play", *args)

    def pause(self) -> OscSendResult:
        return self.send("/pause")

    def stop(self) -> OscSendResult:
        return self.send("/stop")

    # ── コンテンツ ────────────────────────────────────────────

    def load_content(self, file_path: str, zone: str) -> OscSendResult:
        """指定ゾーンにコンテンツをロード。

        ack mode かつ TD が /ack/<seq> を返す環境では、戻り値.acked が True
        になるまで実 transition は呼ばない (呼び出し側で順序保証する)。
        """
        return self.send("/content/load", file_path, zone)

    def transition(self, transition_type: str, duration: float = 1.0) -> OscSendResult:
        return self.send("/transition", transition_type, duration)

    # ── バースデー演出 ────────────────────────────────────────

    def trigger_birthday(self, guest_name: str, video_path: str) -> OscSendResult:
        return self.send("/birthday/trigger", guest_name, video_path)

    # ── 料理同期 ──────────────────────────────────────────────

    def course_serve(self, session_id: int, course_key: str) -> OscSendResult:
        return self.send("/course/serve", session_id, course_key)

    def course_clear(self, session_id: int, course_key: str) -> OscSendResult:
        return self.send("/course/clear", session_id, course_key)

    def course_preload(self, course_key: str) -> OscSendResult:
        return self.send("/course/preload", course_key)

    def allergen_alert(self, session_id: int) -> OscSendResult:
        return self.send("/course/allergen_alert", session_id)

    def session_start(self, session_id: int, table_number: int) -> OscSendResult:
        return self.send("/session/start", session_id, table_number)

    def session_complete(self, session_id: int) -> OscSendResult:
        return self.send("/session/complete", session_id)


# シングルトンインスタンス
osc = OSCController()
