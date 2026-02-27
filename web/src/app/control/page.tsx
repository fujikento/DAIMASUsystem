"use client";

import { useEffect, useState } from "react";
import {
  Play,
  Pause,
  Square,
  Cake,
  SkipForward,
  RotateCcw,
  Wifi,
  WifiOff,
  Sparkles,
} from "lucide-react";
import SpatialMapView from "./components/SpatialMapView";
import {
  getProjectionStatus,
  playProjection,
  pauseProjection,
  stopProjection,
  triggerEvent,
  createProjectionWebSocket,
  type ProjectionStatus,
} from "@/lib/api";
import { getTodayTheme } from "@/lib/themes";

export default function ControlPage() {
  const [status, setStatus] = useState<ProjectionStatus | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [actionFeedback, setActionFeedback] = useState("");
  const theme = getTodayTheme();

  useEffect(() => {
    getProjectionStatus()
      .then(setStatus)
      .catch(() => {});

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let destroyed = false;

    function connect() {
      if (destroyed) return;
      try {
        ws = createProjectionWebSocket((s) => {
          setStatus(s);
          setWsConnected(true);
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
    };
  }, []);

  function showFeedback(msg: string) {
    setActionFeedback(msg);
    setTimeout(() => setActionFeedback(""), 2000);
  }

  async function handlePlay() {
    try {
      const timelineId = status?.timeline_id ?? 1;
      const s = await playProjection(timelineId);
      setStatus(s);
      showFeedback("再生開始");
    } catch {
      showFeedback("エラー: APIに接続できません");
    }
  }

  async function handlePause() {
    try {
      const s = await pauseProjection();
      setStatus(s);
      showFeedback("一時停止");
    } catch {
      showFeedback("エラー: 一時停止に失敗しました");
    }
  }

  async function handleStop() {
    try {
      const s = await stopProjection();
      setStatus(s);
      showFeedback("停止");
    } catch {
      showFeedback("エラー: 停止に失敗しました");
    }
  }

  async function handleBirthday() {
    try {
      const s = await triggerEvent("birthday", {});
      setStatus(s);
      showFeedback("誕生日サプライズ発動！");
    } catch {
      showFeedback("エラー: 演出の発動に失敗しました");
    }
  }

  async function handleNextCourse() {
    try {
      const s = await triggerEvent("transition", {
        type: "crossfade",
        duration: 2.0,
      });
      setStatus(s);
      showFeedback("次のコースへ");
    } catch {
      showFeedback("エラー: コース切替に失敗しました");
    }
  }

  async function handleEncore() {
    try {
      const s = await triggerEvent("transition", {
        type: "sparkle",
        duration: 3.0,
      });
      setStatus(s);
      showFeedback("アンコール演出");
    } catch {
      showFeedback("エラー: 演出の発動に失敗しました");
    }
  }

  const isPlaying = status?.state === "playing";
  const isPaused = status?.state === "paused";
  const isIdle = !status || status.state === "idle";

  const stateConfig = isPlaying
    ? { label: "PLAYING", labelJa: "再生中", dotColor: "bg-emerald-400", glowColor: "shadow-emerald-500/30", badgeBg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300", ambientFrom: "from-emerald-950/40", ambientTo: "to-transparent" }
    : isPaused
    ? { label: "PAUSED", labelJa: "一時停止", dotColor: "bg-amber-400", glowColor: "shadow-amber-500/30", badgeBg: "bg-amber-500/10 border-amber-500/30 text-amber-300", ambientFrom: "from-amber-950/30", ambientTo: "to-transparent" }
    : { label: "STANDBY", labelJa: "待機中", dotColor: "bg-slate-500", glowColor: "shadow-slate-700/20", badgeBg: "bg-slate-700/30 border-slate-600/30 text-slate-400", ambientFrom: "from-slate-900/60", ambientTo: "to-transparent" };

  const elapsedMinutes = status?.elapsed !== undefined ? Math.floor(status.elapsed / 60) : 0;
  const elapsedSeconds = status?.elapsed !== undefined ? Math.floor(status.elapsed % 60) : 0;
  const elapsedFrames = status?.elapsed !== undefined ? Math.floor((status.elapsed % 1) * 30) : 0;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">

      {/* ── Page header with connection badge ─────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-white">投影制御</h2>
          <p className="text-xs text-slate-500 mt-0.5 tracking-wider uppercase">Projection Control System</p>
        </div>

        {/* Connection badge — small, elegant, corner-anchored */}
        {wsConnected ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 backdrop-blur-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
            </span>
            <span className="text-xs font-semibold tracking-widest text-emerald-300 uppercase">Live</span>
            <Wifi size={11} className="text-emerald-400" />
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/[0.08] border border-red-500/20 backdrop-blur-sm">
            <span className="relative flex h-2 w-2">
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
            <span className="text-xs font-semibold tracking-widest text-red-400 uppercase">Offline</span>
            <WifiOff size={11} className="text-red-400" />
          </div>
        )}
      </div>

      {/* ── Status display panel ───────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-[#0a1628]">
        {/* Ambient gradient that shifts with state */}
        <div className={`absolute inset-0 bg-gradient-to-br ${stateConfig.ambientFrom} ${stateConfig.ambientTo} pointer-events-none transition-all duration-1000`} />

        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: `linear-gradient(rgba(148,163,184,1) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,1) 1px, transparent 1px)`,
            backgroundSize: "32px 32px",
          }}
        />

        <div className="relative p-6 flex flex-col items-center gap-4">
          {/* State badge */}
          <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-semibold tracking-widest uppercase ${stateConfig.badgeBg}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${stateConfig.dotColor} ${isPlaying ? "animate-pulse" : ""}`} />
            {stateConfig.label}
          </div>

          {/* Broadcast timecode display */}
          <div className="flex items-baseline gap-1 select-none">
            <span className="font-mono text-5xl font-light tracking-tighter text-white tabular-nums">
              {String(elapsedMinutes).padStart(2, "0")}
            </span>
            <span className="font-mono text-3xl font-light text-slate-500 mb-0.5">:</span>
            <span className="font-mono text-5xl font-light tracking-tighter text-white tabular-nums">
              {String(elapsedSeconds).padStart(2, "0")}
            </span>
            <span className="font-mono text-xl font-light text-slate-600 mb-1 ml-1">
              :{String(elapsedFrames).padStart(2, "0")}
            </span>
          </div>

          {/* Theme label */}
          <p className="text-xs text-slate-500 tracking-wide">
            テーマ:{" "}
            <span className="font-medium" style={{ color: theme.color }}>
              {theme.icon} {theme.nameJa}
            </span>
          </p>

          {/* Feedback toast — inline flow to avoid overlap */}
          <div className="h-7 flex items-center justify-center">
            {actionFeedback && (
              <div className="px-4 py-1.5 rounded-full bg-blue-500/15 border border-blue-400/25 text-blue-300 text-xs font-medium tracking-wide animate-pulse whitespace-nowrap">
                {actionFeedback}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Transport controls — the visual centrepiece ────────────────── */}
      <div className="relative rounded-2xl border border-white/[0.07] bg-[#0a1628] p-6">
        {/* Subtle grid background */}
        <div
          className="absolute inset-0 rounded-2xl opacity-[0.025] pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(circle, rgba(148,163,184,1) 1px, transparent 1px)`,
            backgroundSize: "20px 20px",
          }}
        />

        <div className="relative flex items-center justify-center gap-6">

          {/* ── STOP — contained, dangerous-feel ── */}
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={handleStop}
              disabled={isIdle}
              className={`
                group relative w-12 h-12 rounded-xl flex items-center justify-center
                transition-all duration-200 active:scale-90
                ${isIdle
                  ? "bg-[#0d1a2d] border border-white/[0.05] cursor-not-allowed"
                  : "bg-[#1a0d0d] border border-red-500/25 hover:border-red-400/50 hover:bg-red-950/40 hover:scale-105 shadow-lg shadow-red-900/20 cursor-pointer"
                }
              `}
            >
              <Square
                size={18}
                className={`transition-colors duration-200 ${
                  isIdle ? "text-slate-700" : "text-red-400 group-hover:text-red-300"
                }`}
              />
              {/* Red inner ring — only visible when enabled */}
              {!isIdle && (
                <span className="absolute inset-0 rounded-xl ring-1 ring-red-500/10 group-hover:ring-red-500/30 transition-all" />
              )}
            </button>
            <span className={`text-[10px] font-medium tracking-widest uppercase ${isIdle ? "text-slate-700" : "text-red-400/70"}`}>
              Stop
            </span>
          </div>

          {/* ── PAUSE — pill-shaped, mid-weight ── */}
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={handlePause}
              disabled={!isPlaying}
              className={`
                group relative w-14 h-14 rounded-2xl flex items-center justify-center
                transition-all duration-200 active:scale-90
                ${!isPlaying
                  ? "bg-[#0d1a2d] border border-white/[0.05] cursor-not-allowed"
                  : isPaused
                    ? "bg-amber-900/30 border border-amber-400/40 shadow-lg shadow-amber-900/30 cursor-pointer"
                    : "bg-[#141f33] border border-amber-500/20 hover:border-amber-400/40 hover:bg-amber-950/30 hover:scale-105 shadow-md cursor-pointer"
                }
              `}
            >
              <Pause
                size={22}
                className={`transition-colors duration-200 ${
                  !isPlaying
                    ? "text-slate-700"
                    : isPaused
                      ? "text-amber-300"
                      : "text-amber-400/80 group-hover:text-amber-300"
                }`}
              />
              {/* Amber indicator dot when paused */}
              {isPaused && (
                <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              )}
            </button>
            <span className={`text-[10px] font-medium tracking-widest uppercase ${!isPlaying ? "text-slate-700" : isPaused ? "text-amber-400" : "text-amber-400/60"}`}>
              Pause
            </span>
          </div>

          {/* ── PLAY — circular, the centrepiece ── */}
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={handlePlay}
              disabled={isPlaying}
              className={`
                group relative w-20 h-20 rounded-full flex items-center justify-center
                transition-all duration-300 active:scale-90
                ${isPlaying
                  ? "cursor-not-allowed bg-emerald-900/30 border-2 border-emerald-500/40"
                  : "cursor-pointer bg-gradient-to-br from-emerald-600/80 to-emerald-800/60 border-2 border-emerald-500/50 hover:border-emerald-400/70 hover:scale-110 shadow-xl shadow-emerald-900/50 hover:shadow-emerald-800/60"
                }
              `}
            >
              {/* Outer glow ring */}
              <span className={`
                absolute inset-[-4px] rounded-full border pointer-events-none transition-all duration-300
                ${isPlaying
                  ? "border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.2)] animate-pulse"
                  : "border-emerald-500/15 group-hover:border-emerald-400/35 group-hover:shadow-[0_0_24px_rgba(16,185,129,0.25)]"
                }
              `} />
              {/* Second ring for idle state depth */}
              {!isPlaying && (
                <span className="absolute inset-[-9px] rounded-full border border-emerald-500/[0.06] pointer-events-none group-hover:border-emerald-400/12 transition-all duration-300" />
              )}

              <Play
                size={28}
                className={`ml-1 transition-all duration-200 ${
                  isPlaying
                    ? "text-emerald-400/60"
                    : "text-white group-hover:scale-105"
                }`}
                fill={isPlaying ? "rgba(52,211,153,0.4)" : "currentColor"}
              />

              {/* Playing pulse indicator */}
              {isPlaying && (
                <span className="absolute inset-0 rounded-full bg-emerald-400/5 animate-ping" />
              )}
            </button>
            <span className={`text-[10px] font-semibold tracking-widest uppercase ${isPlaying ? "text-emerald-400" : "text-emerald-400/70"}`}>
              Play
            </span>
          </div>

        </div>

        {/* Transport rail — decorative separator line */}
        <div className="absolute left-8 right-8 top-1/2 -translate-y-1/2 h-px bg-gradient-to-r from-transparent via-white/[0.04] to-transparent pointer-events-none" />
      </div>

      {/* ── Spatial Map ───────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-blue-400/10 bg-[#0e1d32] p-6">
        <SpatialMapView />
      </div>

      {/* ── Quick Actions ─────────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-[0.15em]">
            Quick Actions
          </span>
          <div className="flex-1 h-px bg-white/[0.04]" />
        </div>

        <div className="grid grid-cols-1 gap-2.5">

          {/* Birthday */}
          <button
            onClick={handleBirthday}
            className="group flex items-center gap-4 p-4 rounded-xl border border-pink-500/12 bg-pink-500/[0.04] hover:bg-pink-500/10 hover:border-pink-500/25 transition-all duration-200 active:scale-[0.99] text-left"
          >
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-pink-500/10 border border-pink-500/15 flex items-center justify-center group-hover:bg-pink-500/15 group-hover:border-pink-500/30 transition-all duration-200">
              <Cake size={18} className="text-pink-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-pink-300 group-hover:text-pink-200 transition-colors">誕生日サプライズ</p>
              <p className="text-xs text-pink-400/45 mt-0.5">キャラクターアニメーション＋バースデー演出</p>
            </div>
            <div className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-pink-500/30 group-hover:bg-pink-400/60 transition-all duration-200" />
          </button>

          {/* Next course */}
          <button
            onClick={handleNextCourse}
            className="group flex items-center gap-4 p-4 rounded-xl border border-amber-500/12 bg-amber-500/[0.04] hover:bg-amber-500/10 hover:border-amber-500/25 transition-all duration-200 active:scale-[0.99] text-left"
          >
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/15 flex items-center justify-center group-hover:bg-amber-500/15 group-hover:border-amber-500/30 transition-all duration-200">
              <SkipForward size={18} className="text-amber-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-amber-300 group-hover:text-amber-200 transition-colors">次のコースへ</p>
              <p className="text-xs text-amber-400/45 mt-0.5">クロスフェードで次のコンテンツに切替</p>
            </div>
            <div className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-amber-500/30 group-hover:bg-amber-400/60 transition-all duration-200" />
          </button>

          {/* Encore */}
          <button
            onClick={handleEncore}
            className="group flex items-center gap-4 p-4 rounded-xl border border-purple-500/12 bg-purple-500/[0.04] hover:bg-purple-500/10 hover:border-purple-500/25 transition-all duration-200 active:scale-[0.99] text-left"
          >
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/15 flex items-center justify-center group-hover:bg-purple-500/15 group-hover:border-purple-500/30 transition-all duration-200">
              <Sparkles size={18} className="text-purple-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-purple-300 group-hover:text-purple-200 transition-colors">アンコール演出</p>
              <p className="text-xs text-purple-400/45 mt-0.5">特別エフェクト付きの追加演出</p>
            </div>
            <div className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-purple-500/30 group-hover:bg-purple-400/60 transition-all duration-200" />
          </button>

        </div>
      </div>
    </div>
  );
}
