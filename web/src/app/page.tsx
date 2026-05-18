"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Wand2,
  Projector,
  ChevronRight,
  Clock,
  Loader2,
  Wifi,
  WifiOff,
  Sparkles,
  Image as ImageIcon,
  Video,
  Plus,
} from "lucide-react";
import {
  getProjectionStatus,
  createProjectionWebSocket,
  fetchStoryboards,
  type ProjectionStatus,
  type StoryboardListItem,
} from "@/lib/api";

const STATUS_META: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  draft: {
    label: "下書き",
    color: "text-neutral-400 bg-neutral-500/15 border-neutral-500/30",
    icon: <Sparkles size={11} />,
  },
  images_ready: {
    label: "画像できた",
    color: "text-blue-300 bg-blue-500/15 border-blue-500/30",
    icon: <ImageIcon size={11} />,
  },
  video_ready: {
    label: "動画完成",
    color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
    icon: <Video size={11} />,
  },
};

function relativeJa(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "たった今";
  if (min < 60) return `${min}分前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}時間前`;
  const day = Math.floor(hr / 24);
  if (day === 1) return "昨日";
  if (day < 7) return `${day}日前`;
  return new Date(iso).toLocaleDateString("ja-JP", { month: "short", day: "numeric" });
}

export default function HomeDashboard() {
  const [projection, setProjection] = useState<ProjectionStatus | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [storyboards, setStoryboards] = useState<StoryboardListItem[] | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchStoryboards();
      data.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setStoryboards(data);
    } catch {
      setStoryboards([]);
    }
  }, []);

  useEffect(() => {
    load();
    getProjectionStatus()
      .then(setProjection)
      .catch(() => {});

    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let dead = false;

    function connect() {
      if (dead) return;
      try {
        ws = createProjectionWebSocket((s) => {
          setProjection(s);
          setWsConnected(true);
        });
        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => {
          setWsConnected(false);
          if (!dead) timer = setTimeout(connect, 3000);
        };
        ws.onerror = () => {
          setWsConnected(false);
          ws?.close();
        };
      } catch {
        if (!dead) timer = setTimeout(connect, 3000);
      }
    }
    connect();

    return () => {
      dead = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [load]);

  const recent = (storyboards ?? []).slice(0, 4);
  const projLabel =
    projection?.state === "playing"
      ? "再生中"
      : projection?.state === "paused"
      ? "一時停止"
      : "待機中";
  const projColor =
    projection?.state === "playing"
      ? "text-emerald-300"
      : projection?.state === "paused"
      ? "text-yellow-300"
      : "text-neutral-400";

  return (
    <div className="space-y-10 max-w-5xl mx-auto py-2">
      {/* ─ Greeting ─ */}
      <div className="text-center space-y-2 pt-4">
        <p className="text-xs font-semibold tracking-[0.25em] uppercase text-blue-400/80">
          Immersive Dining
        </p>
        <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
          こんにちは。今日は何をしますか?
        </h1>
      </div>

      {/* ─ 2 big primary actions ─ */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Create */}
        <Link
          href="/create"
          className="group rounded-3xl p-7 bg-gradient-to-br from-blue-600 via-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 transition-all shadow-2xl shadow-blue-900/40 hover:shadow-blue-800/60 hover:scale-[1.015] active:scale-[0.99]"
        >
          <div className="flex items-start gap-4 mb-4">
            <div className="w-14 h-14 rounded-2xl bg-white/15 border border-white/20 flex items-center justify-center shrink-0 group-hover:bg-white/25 transition-colors">
              <Wand2 size={24} className="text-white" strokeWidth={2.3} />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-white">作る</h2>
              <p className="text-white/70 text-xs mt-0.5">
                台本 → 画像 → 動画 を作る
              </p>
            </div>
            <ChevronRight
              size={22}
              className="text-white/70 mt-2 group-hover:translate-x-1 transition-transform shrink-0"
            />
          </div>
          <p className="text-white/85 text-sm leading-relaxed">
            テーマを選んで AI に作らせる4ステップ。最短5分で完成。
          </p>
        </Link>

        {/* Project */}
        <Link
          href="/control"
          className="group rounded-3xl p-7 bg-gradient-to-br from-purple-700 via-purple-700 to-indigo-800 hover:from-purple-600 hover:to-indigo-700 transition-all shadow-2xl shadow-purple-900/40 hover:shadow-purple-800/60 hover:scale-[1.015] active:scale-[0.99]"
        >
          <div className="flex items-start gap-4 mb-4">
            <div className="w-14 h-14 rounded-2xl bg-white/15 border border-white/20 flex items-center justify-center shrink-0 group-hover:bg-white/25 transition-colors">
              <Projector size={24} className="text-white" strokeWidth={2.3} />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-white">流す</h2>
              <p className="text-white/70 text-xs mt-0.5">
                投影制御パネル
              </p>
            </div>
            <ChevronRight
              size={22}
              className="text-white/70 mt-2 group-hover:translate-x-1 transition-transform shrink-0"
            />
          </div>
          <div className="flex items-center gap-2 text-white/85 text-sm">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                projection?.state === "playing"
                  ? "bg-emerald-300 shadow-[0_0_6px_rgba(110,231,183,0.7)]"
                  : projection?.state === "paused"
                  ? "bg-yellow-300"
                  : "bg-white/40"
              }`}
            />
            <span>
              現在: <strong className={projColor}>{projLabel}</strong>
              {!wsConnected && (
                <span className="text-white/50 text-xs ml-2">
                  · システム未接続
                </span>
              )}
            </span>
          </div>
        </Link>
      </div>

      {/* ─ Recent works ─ */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-300">
            最近作ったもの
          </h3>
          <Link
            href="/create"
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            すべて見る <ChevronRight size={12} />
          </Link>
        </div>

        {storyboards === null ? (
          <div className="rounded-2xl bg-[#0e1d32] border border-blue-400/10 h-32 flex items-center justify-center">
            <Loader2 size={18} className="animate-spin text-neutral-600" />
          </div>
        ) : recent.length === 0 ? (
          <Link
            href="/create"
            className="block rounded-2xl bg-[#0e1d32] border border-dashed border-neutral-700 hover:border-blue-400/30 transition-colors p-8 text-center group"
          >
            <Plus size={26} className="text-neutral-600 group-hover:text-blue-400 mx-auto mb-2 transition-colors" />
            <p className="text-sm text-neutral-500 group-hover:text-neutral-300 transition-colors">
              まだ作品はありません。クリックして始めましょう。
            </p>
          </Link>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {recent.map((sb) => {
              const meta = STATUS_META[sb.status] ?? STATUS_META.draft;
              return (
                <Link
                  key={sb.id}
                  href={`/create/${sb.id}`}
                  className="group flex items-center gap-3 rounded-2xl bg-[#0e1d32] border border-blue-400/10 hover:border-blue-400/30 p-3 transition-all hover:bg-blue-400/[0.04]"
                >
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-[#0a1628] to-[#0d1f38] border border-white/[0.06] flex items-center justify-center shrink-0">
                    {sb.status === "video_ready" ? (
                      <Video size={20} className="text-emerald-400/70" />
                    ) : sb.status === "images_ready" ? (
                      <ImageIcon size={20} className="text-blue-400/70" />
                    ) : (
                      <Sparkles size={20} className="text-neutral-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-white text-sm font-semibold truncate">
                        {sb.title || "(無題)"}
                      </h4>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${meta.color}`}
                      >
                        {meta.icon}
                        {meta.label}
                      </span>
                      <span className="text-[11px] text-neutral-500 flex items-center gap-1">
                        <Clock size={10} />
                        {relativeJa(sb.created_at)}
                      </span>
                    </div>
                  </div>
                  <ChevronRight
                    size={16}
                    className="text-neutral-700 group-hover:text-blue-400 group-hover:translate-x-0.5 transition-all shrink-0"
                  />
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* ─ System status footer ─ */}
      <div className="flex items-center justify-center gap-2 text-xs text-neutral-600 pt-4">
        {wsConnected ? (
          <Wifi size={11} className="text-emerald-500/70" />
        ) : (
          <WifiOff size={11} />
        )}
        <span>
          システム {wsConnected ? "接続中" : "未接続"}
          {projection?.elapsed !== undefined && projection.elapsed > 0 && (
            <span className="ml-2 font-mono">
              · 経過 {Math.floor(projection.elapsed / 60)}:
              {String(Math.floor(projection.elapsed % 60)).padStart(2, "0")}
            </span>
          )}
        </span>
      </div>
    </div>
  );
}
