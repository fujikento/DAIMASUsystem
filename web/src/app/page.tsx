"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Film,
  Projector,
  ImageIcon,
  Video,
  ChevronRight,
  Plus,
  Clock,
  CheckCircle2,
  Circle,
  Wifi,
  WifiOff,
  Loader2,
  AlertCircle,
  Library,
  Play,
  Sparkles,
} from "lucide-react";
import {
  getProjectionStatus,
  createProjectionWebSocket,
  fetchTodayReservations,
  fetchStoryboards,
  type ProjectionStatus,
  type StoryboardListItem,
} from "@/lib/api";

// ─── Storyboard status helpers ─────────────────────────────────────────────

type StoryboardStatus = "draft" | "images_ready" | "video_ready" | string;

function getStatusBadge(status: StoryboardStatus): {
  label: string;
  className: string;
  icon: React.ReactNode;
} {
  switch (status) {
    case "draft":
      return {
        label: "下書き",
        className: "bg-neutral-500/20 text-neutral-400 border border-neutral-500/30",
        icon: <Circle size={10} className="fill-neutral-500 stroke-none" />,
      };
    case "images_ready":
      return {
        label: "画像完成",
        className: "bg-blue-500/20 text-blue-400 border border-blue-500/30",
        icon: <CheckCircle2 size={10} className="text-blue-400" />,
      };
    case "video_ready":
      return {
        label: "動画完成",
        className: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
        icon: <CheckCircle2 size={10} className="text-emerald-400" />,
      };
    default:
      return {
        label: status,
        className: "bg-neutral-700/30 text-neutral-500 border border-neutral-600/30",
        icon: <Circle size={10} className="fill-neutral-600 stroke-none" />,
      };
  }
}

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "たった今";
  if (diffMin < 60) return `${diffMin}分前`;
  if (diffHour < 24) return `${diffHour}時間前`;
  if (diffDay === 1) return "昨日";
  if (diffDay < 7) return `${diffDay}日前`;
  return date.toLocaleDateString("ja-JP", { month: "short", day: "numeric" });
}

// ─── Thumbnail placeholder ──────────────────────────────────────────────────

function StoryboardThumbnail({ storyboard }: { storyboard: StoryboardListItem }) {
  const { className } = getStatusBadge(storyboard.status);
  const isVideosReady = storyboard.status === "video_ready";
  const isImagesReady = storyboard.status === "images_ready";

  return (
    <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-gradient-to-br from-[#0a1628] to-[#0d1f38] border border-white/[0.06] flex items-center justify-center shrink-0">
      {isVideosReady ? (
        <div className="flex flex-col items-center gap-2 text-emerald-400/60">
          <Video size={28} strokeWidth={1.5} />
          <span className="text-[10px] font-medium tracking-wider uppercase">動画あり</span>
        </div>
      ) : isImagesReady ? (
        <div className="flex flex-col items-center gap-2 text-blue-400/60">
          <ImageIcon size={28} strokeWidth={1.5} />
          <span className="text-[10px] font-medium tracking-wider uppercase">画像あり</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 text-neutral-600">
          <Film size={28} strokeWidth={1.5} />
          <span className="text-[10px] font-medium tracking-wider uppercase">下書き</span>
        </div>
      )}

      {/* Subtle scanline overlay for cinematic feel */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.04]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.15) 2px, rgba(255,255,255,0.15) 3px)",
        }}
      />
    </div>
  );
}

// ─── Workflow step indicator ────────────────────────────────────────────────

function WorkflowStep({
  step,
  label,
  active,
}: {
  step: number;
  label: string;
  active: boolean;
}) {
  return (
    <div className={`flex items-center gap-2 ${active ? "text-white" : "text-neutral-600"}`}>
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${
          active
            ? "bg-blue-600 border-blue-500 text-white"
            : "bg-neutral-800 border-neutral-700 text-neutral-600"
        }`}
      >
        {step}
      </div>
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function Dashboard() {
  const [projectionStatus, setProjectionStatus] = useState<ProjectionStatus | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [storyboards, setStoryboards] = useState<StoryboardListItem[]>([]);
  const [storyboardsLoading, setStoryboardsLoading] = useState(true);
  const [storyboardsError, setStoryboardsError] = useState(false);
  const [activeTableCount, setActiveTableCount] = useState<number | null>(null);

  // ─── Fetch storyboards ─────────────────────────────────────────────────

  const loadStoryboards = useCallback(async () => {
    setStoryboardsLoading(true);
    setStoryboardsError(false);
    try {
      const data = await fetchStoryboards();
      // Sort by created_at descending (newest first)
      const sorted = [...data].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setStoryboards(sorted);
    } catch {
      setStoryboardsError(true);
    } finally {
      setStoryboardsLoading(false);
    }
  }, []);

  // ─── Fetch reservation count for the secondary indicator ───────────────

  const loadTableCount = useCallback(async () => {
    try {
      const reservations = await fetchTodayReservations();
      const active = reservations.filter((r) => r.status !== "cancelled");
      setActiveTableCount(active.length);
    } catch {
      setActiveTableCount(null);
    }
  }, []);

  useEffect(() => {
    loadStoryboards();
    loadTableCount();

    getProjectionStatus()
      .then(setProjectionStatus)
      .catch(() => {});

    // WebSocket for live projection status
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let destroyed = false;

    function connectWs() {
      if (destroyed) return;
      try {
        ws = createProjectionWebSocket((s) => {
          setProjectionStatus(s);
          setWsConnected(true);
        });
        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => {
          setWsConnected(false);
          if (!destroyed) reconnectTimer = setTimeout(connectWs, 3000);
        };
        ws.onerror = () => {
          setWsConnected(false);
          ws?.close();
        };
      } catch {
        setWsConnected(false);
        if (!destroyed) reconnectTimer = setTimeout(connectWs, 3000);
      }
    }

    connectWs();

    return () => {
      destroyed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [loadStoryboards, loadTableCount]);

  // ─── Derived stats ─────────────────────────────────────────────────────

  const totalStoryboards = storyboards.length;
  const videosReadyCount = storyboards.filter((s) => s.status === "video_ready").length;
  const imagesReadyCount = storyboards.filter((s) => s.status === "images_ready").length;
  const latestStoryboard = storyboards[0] ?? null;

  const projectionStateLabel =
    projectionStatus?.state === "playing"
      ? "再生中"
      : projectionStatus?.state === "paused"
      ? "一時停止"
      : "待機中";

  const projectionStateColor =
    projectionStatus?.state === "playing"
      ? "text-emerald-400"
      : projectionStatus?.state === "paused"
      ? "text-yellow-400"
      : "text-neutral-500";

  const recentStoryboards = storyboards.slice(0, 6);

  return (
    <div className="space-y-8">

      {/* ── Hero Section ──────────────────────────────────────────────────── */}

      <div className="relative rounded-2xl overflow-hidden border border-blue-500/[0.15] bg-gradient-to-br from-[#0d1f38] via-[#0e1d32] to-[#080f1a]">
        {/* Decorative grid lines */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        {/* Glow accent top-right */}
        <div className="absolute top-0 right-0 w-72 h-72 rounded-full bg-blue-600/10 blur-3xl pointer-events-none" />

        <div className="relative px-8 py-8 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
                <Projector size={16} className="text-blue-400" />
              </div>
              <span className="text-xs font-semibold tracking-[0.2em] uppercase text-blue-400/80">
                Immersive Dining
              </span>
            </div>
            <h1 className="text-3xl font-bold text-white leading-tight tracking-tight">
              プロジェクションシステム
            </h1>
            <p className="text-neutral-400 text-sm max-w-md leading-relaxed">
              台本を作成し、画像・動画を生成して、没入型ダイニング体験を制作します。
            </p>

            {/* Workflow steps */}
            <div className="flex items-center gap-1 pt-1 flex-wrap">
              <WorkflowStep step={1} label="台本作成" active />
              <ChevronRight size={14} className="text-neutral-700 mx-1" />
              <WorkflowStep step={2} label="画像生成" active={imagesReadyCount > 0} />
              <ChevronRight size={14} className="text-neutral-700 mx-1" />
              <WorkflowStep step={3} label="動画生成" active={videosReadyCount > 0} />
            </div>
          </div>

          {/* CTA */}
          <div className="flex flex-col gap-3 shrink-0">
            <a
              href="/generation"
              className="group flex items-center gap-3 px-6 py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all duration-200 shadow-lg shadow-blue-900/40 hover:shadow-blue-800/50 hover:scale-[1.02]"
            >
              <Plus size={18} className="shrink-0" />
              <span>新しい台本を作成</span>
              <ChevronRight size={16} className="ml-auto opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-transform" />
            </a>
            <a
              href="/control"
              className="flex items-center gap-3 px-6 py-3 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] text-neutral-300 font-medium text-sm transition-colors border border-white/[0.07]"
            >
              <Play size={15} className="shrink-0" />
              <span>投影制御パネル</span>
              <ChevronRight size={14} className="ml-auto opacity-40" />
            </a>
          </div>
        </div>
      </div>

      {/* ── Stats Row ──────────────────────────────────────────────────────── */}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total storyboards */}
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <div className="flex items-center justify-between">
            <Film size={18} className="text-blue-400" />
            <span className="text-xs text-neutral-600 font-medium uppercase tracking-widest">台本数</span>
          </div>
          <div>
            <p className="text-3xl font-bold text-white tabular-nums">
              {storyboardsLoading ? (
                <Loader2 size={20} className="animate-spin text-neutral-600" />
              ) : (
                totalStoryboards
              )}
            </p>
            <p className="text-neutral-600 text-xs mt-0.5">作成済み</p>
          </div>
        </div>

        {/* Videos ready */}
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <div className="flex items-center justify-between">
            <Video size={18} className="text-emerald-400" />
            <span className="text-xs text-neutral-600 font-medium uppercase tracking-widest">動画</span>
          </div>
          <div>
            <p className="text-3xl font-bold text-white tabular-nums">
              {storyboardsLoading ? (
                <Loader2 size={20} className="animate-spin text-neutral-600" />
              ) : (
                videosReadyCount
              )}
            </p>
            <p className="text-neutral-600 text-xs mt-0.5">動画生成完了</p>
          </div>
        </div>

        {/* Latest storyboard status */}
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <div className="flex items-center justify-between">
            <Sparkles size={18} className="text-amber-400" />
            <span className="text-xs text-neutral-600 font-medium uppercase tracking-widest">最新</span>
          </div>
          <div>
            {!storyboardsLoading && latestStoryboard ? (
              <>
                <div className="flex items-center gap-1.5 mb-0.5">
                  {(() => {
                    const badge = getStatusBadge(latestStoryboard.status);
                    return (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}>
                        {badge.icon}
                        {badge.label}
                      </span>
                    );
                  })()}
                </div>
                <p className="text-neutral-500 text-xs truncate max-w-[120px]" title={latestStoryboard.title}>
                  {latestStoryboard.title}
                </p>
              </>
            ) : storyboardsLoading ? (
              <Loader2 size={20} className="animate-spin text-neutral-600" />
            ) : (
              <p className="text-neutral-600 text-sm">台本なし</p>
            )}
          </div>
        </div>

        {/* System status */}
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <div className="flex items-center justify-between">
            {wsConnected ? (
              <Wifi size={18} className="text-emerald-400" />
            ) : (
              <WifiOff size={18} className="text-neutral-600" />
            )}
            <span className="text-xs text-neutral-600 font-medium uppercase tracking-widest">投影</span>
          </div>
          <div>
            <p className={`text-lg font-bold ${projectionStateColor}`}>{projectionStateLabel}</p>
            <p className="text-neutral-600 text-xs mt-0.5">
              {wsConnected ? "システム接続中" : "未接続"}
              {activeTableCount !== null && ` · 予約 ${activeTableCount}件`}
            </p>
          </div>
        </div>
      </div>

      {/* ── Main Content: Recent Storyboards + Quick Actions ───────────────── */}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent storyboards — takes 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-neutral-300 tracking-wide">最近の台本</h2>
            <a
              href="/generation"
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
            >
              すべて見る <ChevronRight size={12} />
            </a>
          </div>

          {storyboardsLoading ? (
            <div className="flex items-center justify-center h-48 rounded-2xl bg-[#0e1d32] border border-blue-400/[0.10]">
              <div className="flex items-center gap-2.5 text-neutral-500">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">読み込み中...</span>
              </div>
            </div>
          ) : storyboardsError ? (
            <div className="flex items-center justify-center h-48 rounded-2xl bg-[#0e1d32] border border-red-500/10">
              <div className="text-center space-y-2">
                <AlertCircle size={24} className="text-red-400/50 mx-auto" />
                <p className="text-neutral-500 text-sm">台本の読み込みに失敗しました</p>
                <button
                  onClick={loadStoryboards}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  再試行
                </button>
              </div>
            </div>
          ) : recentStoryboards.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 rounded-2xl bg-[#0e1d32] border border-dashed border-neutral-700/60 gap-3">
              <Film size={28} className="text-neutral-700" strokeWidth={1.5} />
              <p className="text-neutral-600 text-sm">台本がまだありません</p>
              <a
                href="/generation"
                className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
              >
                <Plus size={13} />
                最初の台本を作成する
              </a>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {recentStoryboards.map((sb) => {
                const badge = getStatusBadge(sb.status);
                return (
                  <div
                    key={sb.id}
                    className="group bg-[#0e1d32] rounded-2xl border border-blue-400/[0.08] hover:border-blue-400/[0.20] transition-all duration-200 overflow-hidden hover:shadow-lg hover:shadow-blue-950/50"
                  >
                    {/* Thumbnail */}
                    <div className="p-3 pb-0">
                      <StoryboardThumbnail storyboard={sb} />
                    </div>

                    {/* Info */}
                    <div className="px-4 py-3 space-y-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold text-white leading-snug truncate flex-1">
                          {sb.title}
                        </h3>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap shrink-0 ${badge.className}`}
                        >
                          {badge.icon}
                          {badge.label}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 text-xs text-neutral-600">
                        <Clock size={11} />
                        <span>{formatRelativeDate(sb.created_at)}</span>
                        {sb.day_of_week && (
                          <>
                            <span className="text-neutral-700">·</span>
                            <span>{sb.theme ?? sb.day_of_week}</span>
                          </>
                        )}
                      </div>

                      {/* Quick action buttons */}
                      <div className="flex items-center gap-2 pt-1 border-t border-white/[0.05]">
                        <a
                          href="/generation"
                          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-neutral-400 hover:text-white text-xs font-medium transition-colors"
                        >
                          <Film size={12} />
                          編集
                        </a>
                        {sb.status === "images_ready" || sb.status === "draft" ? (
                          <a
                            href="/generation"
                            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 text-xs font-medium transition-colors"
                          >
                            <ImageIcon size={12} />
                            画像生成
                          </a>
                        ) : null}
                        {sb.status === "video_ready" && (
                          <a
                            href="/control"
                            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 text-xs font-medium transition-colors"
                          >
                            <Play size={12} />
                            投影開始
                          </a>
                        )}
                        {sb.status === "images_ready" && (
                          <a
                            href="/generation"
                            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-purple-600/10 hover:bg-purple-600/20 text-purple-400 text-xs font-medium transition-colors"
                          >
                            <Video size={12} />
                            動画生成
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Quick Actions Panel — 1 col */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-neutral-300 tracking-wide">クイックアクション</h2>

          <div className="bg-[#0e1d32] rounded-2xl border border-blue-400/[0.10] overflow-hidden">
            {/* Primary action */}
            <a
              href="/generation"
              className="group flex items-center gap-4 px-5 py-5 hover:bg-blue-600/10 transition-colors border-b border-white/[0.05]"
            >
              <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 group-hover:bg-blue-600/30 transition-colors">
                <Plus size={18} className="text-blue-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-semibold">新規台本作成</p>
                <p className="text-neutral-500 text-xs mt-0.5">AI台本生成 / シーン編集</p>
              </div>
              <ChevronRight size={15} className="text-neutral-600 group-hover:text-blue-400 transition-colors shrink-0" />
            </a>

            {/* Projection control */}
            <a
              href="/control"
              className="group flex items-center gap-4 px-5 py-4 hover:bg-white/[0.04] transition-colors border-b border-white/[0.05]"
            >
              <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
                <Projector size={18} className="text-neutral-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-neutral-200 text-sm font-medium">投影制御</p>
                <p className="text-neutral-600 text-xs mt-0.5">ショー再生 / キュー操作</p>
              </div>
              <ChevronRight size={15} className="text-neutral-700 group-hover:text-neutral-400 transition-colors shrink-0" />
            </a>

            {/* Content library */}
            <a
              href="/content"
              className="group flex items-center gap-4 px-5 py-4 hover:bg-white/[0.04] transition-colors"
            >
              <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0">
                <Library size={18} className="text-neutral-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-neutral-200 text-sm font-medium">コンテンツライブラリ</p>
                <p className="text-neutral-600 text-xs mt-0.5">動画 / 画像アセット管理</p>
              </div>
              <ChevronRight size={15} className="text-neutral-700 group-hover:text-neutral-400 transition-colors shrink-0" />
            </a>
          </div>

          {/* Projection status mini-card */}
          <div className="bg-[#0e1d32] rounded-2xl border border-blue-400/[0.10] p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-neutral-500 uppercase tracking-widest">投影ステータス</span>
              {wsConnected ? (
                <span className="flex items-center gap-1 text-emerald-400 text-xs">
                  <Wifi size={11} /> 接続中
                </span>
              ) : (
                <span className="flex items-center gap-1 text-neutral-600 text-xs">
                  <WifiOff size={11} /> 未接続
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div
                className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                  projectionStatus?.state === "playing"
                    ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"
                    : projectionStatus?.state === "paused"
                    ? "bg-yellow-400"
                    : "bg-neutral-700"
                }`}
              />
              <span className={`text-base font-bold ${projectionStateColor}`}>
                {projectionStateLabel}
              </span>
            </div>

            {projectionStatus?.elapsed !== undefined && projectionStatus.elapsed > 0 && (
              <div className="text-xs text-neutral-500 font-mono">
                経過: {Math.floor(projectionStatus.elapsed / 60)}:{String(Math.floor(projectionStatus.elapsed % 60)).padStart(2, "0")}
              </div>
            )}

            <a
              href="/control"
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-neutral-400 hover:text-white text-xs font-medium transition-colors border border-white/[0.06]"
            >
              <Play size={12} />
              コントロールパネルを開く
            </a>
          </div>

          {/* Workflow guide */}
          <div className="bg-gradient-to-b from-blue-950/30 to-transparent rounded-2xl border border-blue-500/[0.12] p-5 space-y-3">
            <p className="text-xs font-semibold text-blue-400/80 uppercase tracking-widest">制作フロー</p>
            <div className="space-y-2.5">
              {[
                { step: "01", label: "台本を作成する", sub: "AIでシーンを自動生成" },
                { step: "02", label: "画像を生成する", sub: "各シーンのビジュアル制作" },
                { step: "03", label: "動画を生成する", sub: "最高品質でレンダリング" },
                { step: "04", label: "投影開始", sub: "テーブルに映像を投影" },
              ].map(({ step, label, sub }) => (
                <div key={step} className="flex items-start gap-3">
                  <span className="text-[10px] font-mono font-bold text-blue-500/60 mt-0.5 w-5 shrink-0">{step}</span>
                  <div>
                    <p className="text-xs font-medium text-neutral-300">{label}</p>
                    <p className="text-[10px] text-neutral-600">{sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
