"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  ChevronRight,
  SkipForward,
  Pause,
  Square,
  Play,
  Wifi,
  WifiOff,
  Clock,
  List,
  Check,
  Loader2,
} from "lucide-react";
import {
  fetchShows,
  fetchShow,
  startShow,
  goNextCue,
  gotoCue,
  pauseShow,
  stopShow,
  createShowWebSocket,
  type ShowData,
  type ShowListItem,
  type ShowStatus,
  type ShowCue,
  type ShowWsMessage,
} from "@/lib/api";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function cueTypeLabel(type: string): string {
  switch (type) {
    case "content":
      return "コンテンツ";
    case "transition":
      return "トランジション";
    case "trigger":
      return "トリガー";
    case "wait":
      return "待機";
    default:
      return type;
  }
}

function cueTypeColor(type: string): string {
  switch (type) {
    case "content":
      return "text-blue-400";
    case "transition":
      return "text-purple-400";
    case "trigger":
      return "text-amber-400";
    case "wait":
      return "text-neutral-400";
    default:
      return "text-neutral-300";
  }
}

// ─── CueRow ───────────────────────────────────────────────────────────────────

interface CueRowProps {
  cue: ShowCue;
  isActive: boolean;
  isCompleted: boolean;
  onJump: (cueId: number) => void;
  disabled: boolean;
}

function CueRow({ cue, isActive, isCompleted, onJump, disabled }: CueRowProps) {
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
        isActive
          ? "bg-blue-500/20 border border-blue-500/40"
          : isCompleted
          ? "bg-white/[0.02] border border-white/[0.04] opacity-50"
          : "bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.05]"
      }`}
    >
      {/* Cue status icon */}
      <div className="w-6 flex-shrink-0 flex items-center justify-center">
        {isCompleted ? (
          <Check size={14} className="text-emerald-500" />
        ) : isActive ? (
          <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
        ) : (
          <span className="text-xs text-neutral-600 font-mono">
            {cue.cue_number.toFixed(1)}
          </span>
        )}
      </div>

      {/* Cue info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${cueTypeColor(cue.cue_type)}`}>
            {cueTypeLabel(cue.cue_type)}
          </span>
          {cue.auto_follow && (
            <span className="text-[10px] text-neutral-500 border border-neutral-700 rounded px-1">
              自動
            </span>
          )}
          <span className="text-xs text-neutral-500">
            {cue.duration_seconds}s
          </span>
        </div>
        {cue.content_path && (
          <p className="text-xs text-neutral-400 truncate mt-0.5">
            {cue.content_path.split("/").pop()}
          </p>
        )}
        {cue.notes && (
          <p className="text-xs text-neutral-500 truncate mt-0.5">{cue.notes}</p>
        )}
      </div>

      {/* Jump button */}
      {!isActive && !isCompleted && (
        <button
          onClick={() => onJump(cue.id)}
          disabled={disabled}
          className="flex-shrink-0 p-1.5 rounded-lg text-neutral-500 hover:text-neutral-200 hover:bg-white/[0.06] disabled:opacity-30 transition-all"
          title="このキューへジャンプ"
        >
          <ChevronRight size={14} />
        </button>
      )}
    </div>
  );
}

// ─── ShowControlPanel ─────────────────────────────────────────────────────────

export default function ShowControlPanel() {
  const [shows, setShows] = useState<ShowListItem[]>([]);
  const [selectedShow, setSelectedShow] = useState<ShowData | null>(null);
  const [showStatus, setShowStatus] = useState<ShowStatus | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [elapsedInCue, setElapsedInCue] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedBaseRef = useRef<number>(0);

  // ─── elapsed タイマー ───────────────────────────────────────────
  const startElapsedTimer = useCallback((base: number) => {
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
    elapsedBaseRef.current = base;
    const start = Date.now();
    elapsedTimerRef.current = setInterval(() => {
      setElapsedInCue(base + (Date.now() - start) / 1000);
    }, 100);
  }, []);

  const stopElapsedTimer = useCallback(() => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
  }, []);

  // ─── ショー一覧取得 ─────────────────────────────────────────────
  useEffect(() => {
    fetchShows()
      .then(setShows)
      .catch(() => {});
  }, []);

  // ─── ショー選択 ─────────────────────────────────────────────────
  const selectShow = useCallback(
    async (showId: number) => {
      setLoading(true);
      try {
        const [show] = await Promise.all([fetchShow(showId)]);
        setSelectedShow(show);
        setShowStatus(null);
        setElapsedInCue(0);
      } catch {
        showFeedback("ショー情報の取得に失敗しました");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // ─── WebSocket 接続 ─────────────────────────────────────────────
  useEffect(() => {
    if (!selectedShow) return;
    const currentShow = selectedShow;

    wsRef.current?.close();

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let destroyed = false;

    function connect() {
      if (destroyed) return;
      try {
        ws = createShowWebSocket((msg: ShowWsMessage) => {
          if (msg.channel === "status" && msg.data) {
            setShowStatus(msg.data);
            if (msg.data.status === "running") {
              startElapsedTimer(msg.data.elapsed_in_cue);
            } else {
              stopElapsedTimer();
              setElapsedInCue(msg.data.elapsed_in_cue);
            }
            // 選択ショーのステータスが変わった場合にショーデータを再取得
            if (msg.data.show_id === currentShow.id) {
              fetchShow(currentShow.id)
                .then(setSelectedShow)
                .catch(() => {});
            }
          }
        });
        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => {
          setWsConnected(false);
          if (!destroyed) {
            reconnectTimer = setTimeout(connect, 3000);
          }
        };
        ws.onerror = () => {
          setWsConnected(false);
          ws?.close();
        };
        wsRef.current = ws;
      } catch {
        setWsConnected(false);
        if (!destroyed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      }
    }

    connect();

    return () => {
      destroyed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
      stopElapsedTimer();
    };
  }, [selectedShow?.id, startElapsedTimer, stopElapsedTimer]);

  // ─── クリーンアップ ─────────────────────────────────────────────
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      stopElapsedTimer();
    };
  }, [stopElapsedTimer]);

  // ─── アクション ─────────────────────────────────────────────────
  function showFeedback(msg: string) {
    setFeedback(msg);
    setTimeout(() => setFeedback(""), 2500);
  }

  async function handleStart() {
    if (!selectedShow) return;
    setLoading(true);
    try {
      const status = await startShow(selectedShow.id);
      setShowStatus(status);
      startElapsedTimer(0);
      showFeedback("ショー開始");
      const updated = await fetchShow(selectedShow.id);
      setSelectedShow(updated);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "エラー";
      showFeedback(`開始失敗: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleGo() {
    if (!selectedShow) return;
    setLoading(true);
    try {
      const status = await goNextCue(selectedShow.id);
      setShowStatus(status);
      startElapsedTimer(0);
      showFeedback("次のキューへ進みました");
      const updated = await fetchShow(selectedShow.id);
      setSelectedShow(updated);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "エラー";
      showFeedback(`GO失敗: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  async function handlePause() {
    if (!selectedShow) return;
    try {
      const status = await pauseShow(selectedShow.id);
      setShowStatus(status);
      stopElapsedTimer();
      showFeedback("一時停止");
    } catch {
      showFeedback("一時停止に失敗しました");
    }
  }

  async function handleStop() {
    if (!selectedShow) return;
    try {
      const status = await stopShow(selectedShow.id);
      setShowStatus(status);
      stopElapsedTimer();
      setElapsedInCue(0);
      showFeedback("ショー終了");
      const updated = await fetchShow(selectedShow.id);
      setSelectedShow(updated);
    } catch {
      showFeedback("停止に失敗しました");
    }
  }

  async function handleJumpToCue(cueId: number) {
    if (!selectedShow) return;
    setLoading(true);
    try {
      const status = await gotoCue(selectedShow.id, cueId);
      setShowStatus(status);
      startElapsedTimer(0);
      showFeedback("キューへジャンプしました");
      const updated = await fetchShow(selectedShow.id);
      setSelectedShow(updated);
    } catch {
      showFeedback("ジャンプに失敗しました");
    } finally {
      setLoading(false);
    }
  }

  // ─── 現在のキュー情報 ───────────────────────────────────────────
  const currentCue = selectedShow?.cues.find(
    (c) => c.id === showStatus?.current_cue_id
  ) ?? null;

  const isRunning = showStatus?.status === "running";
  const isPaused = showStatus?.status === "paused";
  const isStandby = !showStatus || showStatus.status === "standby";
  const isCompleted = showStatus?.status === "completed";

  const completedCueIds = new Set<number>();
  if (selectedShow && showStatus?.current_cue_id) {
    const currentIdx = selectedShow.cues.findIndex(
      (c) => c.id === showStatus.current_cue_id
    );
    selectedShow.cues.slice(0, currentIdx).forEach((c) => completedCueIds.add(c.id));
  }
  if (isCompleted && selectedShow) {
    selectedShow.cues.forEach((c) => completedCueIds.add(c.id));
  }

  const remainingInCue =
    currentCue && currentCue.duration_seconds > 0
      ? Math.max(0, currentCue.duration_seconds - elapsedInCue)
      : null;

  // ─── レンダリング ───────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">ショーコントロール</h2>
        {wsConnected ? (
          <span className="flex items-center gap-1.5 text-emerald-400 text-xs">
            <Wifi size={13} /> リアルタイム
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-neutral-500 text-xs">
            <WifiOff size={13} /> 未接続
          </span>
        )}
      </div>

      {/* Show Selector */}
      <div className="bg-[#0e1d32] rounded-2xl border border-white/[0.06] p-4">
        <p className="text-xs text-neutral-500 mb-3 uppercase tracking-widest font-medium">
          ショーを選択
        </p>
        {shows.length === 0 ? (
          <p className="text-sm text-neutral-500">ショーがありません</p>
        ) : (
          <div className="space-y-2">
            {shows.map((s) => (
              <button
                key={s.id}
                onClick={() => selectShow(s.id)}
                className={`w-full text-left flex items-center justify-between px-3 py-2.5 rounded-xl transition-all ${
                  selectedShow?.id === s.id
                    ? "bg-blue-500/20 border border-blue-500/30 text-white"
                    : "bg-white/[0.03] border border-white/[0.06] text-neutral-300 hover:bg-white/[0.06]"
                }`}
              >
                <div>
                  <p className="text-sm font-medium">{s.name}</p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    {s.status === "standby" && "待機中"}
                    {s.status === "running" && "実行中"}
                    {s.status === "paused" && "一時停止"}
                    {s.status === "completed" && "完了"}
                  </p>
                </div>
                {s.status === "running" && (
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Show Control Area */}
      {selectedShow && (
        <>
          {/* Status Display */}
          <div className="bg-[#080f1a] rounded-2xl border border-white/[0.06] p-6 text-center space-y-3">
            <div className="flex items-center justify-center gap-2">
              <div
                className={`w-3 h-3 rounded-full ${
                  isRunning
                    ? "bg-emerald-500 animate-pulse"
                    : isPaused
                    ? "bg-amber-500"
                    : isCompleted
                    ? "bg-neutral-600"
                    : "bg-neutral-700"
                }`}
              />
              <span className="text-lg font-bold text-white">
                {isRunning && "実行中"}
                {isPaused && "一時停止"}
                {isStandby && "待機中"}
                {isCompleted && "完了"}
              </span>
            </div>

            {/* Current Cue */}
            {currentCue && (
              <div className="text-sm text-neutral-400">
                <span className={`font-medium ${cueTypeColor(currentCue.cue_type)}`}>
                  {cueTypeLabel(currentCue.cue_type)}
                </span>
                {currentCue.notes && (
                  <span className="ml-2 text-neutral-500">{currentCue.notes}</span>
                )}
              </div>
            )}

            {/* Timer */}
            {(isRunning || isPaused) && (
              <div className="flex items-center justify-center gap-6 text-center">
                <div>
                  <p className="text-3xl font-mono text-white">
                    {formatTime(elapsedInCue)}
                  </p>
                  <p className="text-xs text-neutral-500 mt-1">経過</p>
                </div>
                {remainingInCue !== null && (
                  <div>
                    <p className="text-2xl font-mono text-neutral-400">
                      {formatTime(remainingInCue)}
                    </p>
                    <p className="text-xs text-neutral-500 mt-1">残り</p>
                  </div>
                )}
              </div>
            )}

            {/* Cue Progress */}
            {showStatus && showStatus.total_cues > 0 && (
              <div className="text-xs text-neutral-500">
                {showStatus.completed_cues} / {showStatus.total_cues} キュー完了
              </div>
            )}

            {/* Feedback */}
            {feedback && (
              <p className="text-blue-400 text-sm animate-pulse">{feedback}</p>
            )}
          </div>

          {/* GO Button */}
          <div className="flex gap-3">
            {isStandby ? (
              <button
                onClick={handleStart}
                disabled={loading || selectedShow.cues.length === 0}
                className="flex-1 flex items-center justify-center gap-3 py-5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-30 rounded-2xl transition-all text-white font-bold text-xl active:scale-95"
              >
                {loading ? (
                  <Loader2 size={28} className="animate-spin" />
                ) : (
                  <Play size={28} />
                )}
                START
              </button>
            ) : (
              <>
                {/* GO button */}
                <button
                  onClick={handleGo}
                  disabled={
                    loading ||
                    isCompleted ||
                    (!isRunning && !isPaused)
                  }
                  className="flex-1 flex items-center justify-center gap-3 py-5 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 rounded-2xl transition-all text-white font-bold text-2xl active:scale-[0.97]"
                >
                  {loading ? (
                    <Loader2 size={32} className="animate-spin" />
                  ) : (
                    <SkipForward size={32} />
                  )}
                  GO
                </button>

                {/* Pause */}
                <button
                  onClick={handlePause}
                  disabled={!isRunning}
                  className="w-16 flex flex-col items-center justify-center gap-1 py-4 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-600/30 disabled:opacity-30 rounded-2xl transition-all text-amber-400 active:scale-95"
                >
                  <Pause size={20} />
                  <span className="text-[10px]">一時停止</span>
                </button>

                {/* Stop */}
                <button
                  onClick={handleStop}
                  disabled={isCompleted && !isRunning && !isPaused}
                  className="w-16 flex flex-col items-center justify-center gap-1 py-4 bg-red-600/20 hover:bg-red-600/30 border border-red-600/30 disabled:opacity-30 rounded-2xl transition-all text-red-400 active:scale-95"
                >
                  <Square size={20} />
                  <span className="text-[10px]">停止</span>
                </button>
              </>
            )}
          </div>

          {/* Cue List */}
          <div className="bg-[#0e1d32] rounded-2xl border border-white/[0.06] p-4 space-y-3">
            <div className="flex items-center gap-2">
              <List size={14} className="text-neutral-500" />
              <p className="text-xs text-neutral-500 uppercase tracking-widest font-medium">
                キューリスト ({selectedShow.cues.length})
              </p>
            </div>

            {selectedShow.cues.length === 0 ? (
              <p className="text-sm text-neutral-500 text-center py-4">
                キューがありません
              </p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {selectedShow.cues.map((cue) => (
                  <CueRow
                    key={cue.id}
                    cue={cue}
                    isActive={cue.id === showStatus?.current_cue_id}
                    isCompleted={completedCueIds.has(cue.id)}
                    onJump={handleJumpToCue}
                    disabled={loading || isCompleted}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Auto follow indicator */}
          {currentCue?.auto_follow && isRunning && (
            <div className="flex items-center gap-2 px-4 py-3 bg-amber-500/10 border border-amber-500/20 rounded-xl">
              <Clock size={14} className="text-amber-400 flex-shrink-0" />
              <p className="text-xs text-amber-300">
                自動進行モード: {currentCue.auto_follow_delay > 0
                  ? `${currentCue.duration_seconds + currentCue.auto_follow_delay}秒後に次のキューへ`
                  : `${currentCue.duration_seconds}秒後に次のキューへ`
                }
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
