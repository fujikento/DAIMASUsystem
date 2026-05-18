"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Plus,
  Wand2,
  Projector,
  Table as TableIcon,
  Loader2,
  Wifi,
  WifiOff,
  ChevronRight,
  Clock,
  AlertTriangle,
  Activity,
} from "lucide-react";
import {
  getProjectionStatus,
  createProjectionWebSocket,
  fetchStoryboards,
  fetchTables,
  type ProjectionStatus,
  type StoryboardListItem,
  type ProjectionTable,
} from "@/lib/api";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  draft: {
    label: "下書き",
    cls: "text-neutral-400 bg-neutral-500/15 border-neutral-500/30",
  },
  images_ready: {
    label: "画像完了",
    cls: "text-blue-300 bg-blue-500/15 border-blue-500/30",
  },
  video_ready: {
    label: "動画完了",
    cls: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
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
  const [tables, setTables] = useState<ProjectionTable[]>([]);

  const load = useCallback(async () => {
    try {
      const [sbs, tbls] = await Promise.all([
        fetchStoryboards(),
        fetchTables().catch(() => [] as ProjectionTable[]),
      ]);
      sbs.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setStoryboards(sbs);
      setTables(tbls);
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

  // ─ Stats ─
  const totalSb = storyboards?.length ?? 0;
  const draftCount = storyboards?.filter((s) => s.status === "draft").length ?? 0;
  const videoReadyCount =
    storyboards?.filter((s) => s.status === "video_ready").length ?? 0;
  const recent = (storyboards ?? []).slice(0, 5);
  const tableCount = tables.length;

  const projLabel =
    projection?.state === "playing"
      ? "再生中"
      : projection?.state === "paused"
      ? "一時停止"
      : "待機中";
  const projDot =
    projection?.state === "playing"
      ? "bg-emerald-400"
      : projection?.state === "paused"
      ? "bg-yellow-400"
      : "bg-neutral-600";

  function tableNameFor(id: number | null | undefined): string {
    if (!id) return "—";
    return tables.find((t) => t.id === id)?.name ?? `席 #${id}`;
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* ─ Header ─ */}
      <div className="flex items-end justify-between gap-3 pb-3 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white">ホーム</h1>
          <p className="text-xs text-neutral-500 mt-1">
            全体の状況・最近の作業
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/create/new"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
          >
            <Plus size={14} />
            新規台本
          </Link>
        </div>
      </div>

      {/* ─ KPI strip ─ */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <KpiCard
          label="台本"
          value={totalSb}
          sub={`下書き ${draftCount} / 完成 ${videoReadyCount}`}
          icon={<Wand2 size={13} />}
        />
        <KpiCard
          label="席"
          value={tableCount}
          sub={tableCount === 0 ? "未登録" : "登録済み"}
          icon={<TableIcon size={13} />}
        />
        <KpiCard
          label="投影"
          value={projLabel}
          sub={wsConnected ? "システム接続中" : "未接続"}
          icon={<Projector size={13} />}
          dot={projDot}
        />
        <KpiCard
          label="経過"
          value={
            projection?.elapsed && projection.elapsed > 0
              ? `${Math.floor(projection.elapsed / 60)}:${String(Math.floor(projection.elapsed % 60)).padStart(2, "0")}`
              : "—"
          }
          sub="再生時間"
          icon={<Activity size={13} />}
          isMono
        />
      </div>

      {/* ─ Setup warning if no tables ─ */}
      {tables.length === 0 && (
        <div className="rounded-md bg-amber-500/10 border border-amber-500/30 p-3 text-sm flex items-start gap-2.5">
          <AlertTriangle size={14} className="text-amber-300 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-amber-200 font-medium">セットアップが完了していません</p>
            <p className="text-amber-300/70 text-xs mt-0.5">
              席 (テーブル) を登録すると、サイズに合わせて動画が作れるようになります。
            </p>
          </div>
          <Link
            href="/tables"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 text-xs font-medium transition-colors shrink-0"
          >
            席を登録
            <ChevronRight size={11} />
          </Link>
        </div>
      )}

      {/* ─ Two-column: recent storyboards + tables ─ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent storyboards (2 cols) */}
        <section className="lg:col-span-2 space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
              最近の台本
            </h2>
            <Link
              href="/create"
              className="text-[11px] text-neutral-500 hover:text-blue-300 transition-colors"
            >
              すべて →
            </Link>
          </div>
          {storyboards === null ? (
            <div className="rounded-md bg-[#11141a] border border-white/10 h-24 flex items-center justify-center">
              <Loader2 size={14} className="animate-spin text-neutral-500" />
            </div>
          ) : recent.length === 0 ? (
            <div className="rounded-md bg-[#11141a] border border-dashed border-white/10 p-8 text-center">
              <p className="text-xs text-neutral-500">
                台本がありません。「新規台本」から作成します。
              </p>
            </div>
          ) : (
            <div className="rounded-md bg-[#11141a] border border-white/10 divide-y divide-white/[0.04] overflow-hidden">
              {recent.map((sb) => {
                const meta = STATUS_META[sb.status] ?? STATUS_META.draft;
                return (
                  <Link
                    key={sb.id}
                    href={`/create/${sb.id}`}
                    className="flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-white/[0.02] transition-colors group"
                  >
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold border shrink-0 ${meta.cls}`}
                    >
                      {meta.label}
                    </span>
                    <span className="text-white font-medium truncate flex-1">
                      {sb.title || "(無題)"}
                    </span>
                    <span className="text-[11px] text-neutral-500 truncate hidden sm:block">
                      {tableNameFor(sb.projection_config_id)}
                    </span>
                    <span className="text-[11px] text-neutral-500 flex items-center gap-1 shrink-0">
                      <Clock size={10} />
                      {relativeJa(sb.created_at)}
                    </span>
                    <ChevronRight
                      size={13}
                      className="text-neutral-700 group-hover:text-blue-400 transition-colors shrink-0"
                    />
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        {/* Tables sidebar */}
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
              席 (テーブル)
            </h2>
            <Link
              href="/tables"
              className="text-[11px] text-neutral-500 hover:text-blue-300 transition-colors"
            >
              管理 →
            </Link>
          </div>
          {tables.length === 0 ? (
            <div className="rounded-md bg-[#11141a] border border-dashed border-white/10 p-6 text-center">
              <TableIcon size={18} className="text-neutral-700 mx-auto mb-1" />
              <p className="text-xs text-neutral-500">未登録</p>
            </div>
          ) : (
            <div className="rounded-md bg-[#11141a] border border-white/10 divide-y divide-white/[0.04] overflow-hidden">
              {tables.slice(0, 6).map((t) => (
                <div key={t.id} className="px-3 py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium truncate">{t.name}</span>
                    {t.is_default && (
                      <span className="text-[10px] text-neutral-500 uppercase">default</span>
                    )}
                  </div>
                  <div className="text-[11px] text-neutral-500 tabular-nums">
                    {t.table_width_mm}×{t.table_height_mm}mm · {t.full_width}×{t.full_height}px
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* ─ Footer status bar ─ */}
      <div className="flex items-center justify-center gap-2 text-[11px] text-neutral-600 pt-3">
        {wsConnected ? (
          <Wifi size={11} className="text-emerald-500/70" />
        ) : (
          <WifiOff size={11} />
        )}
        <span>システム {wsConnected ? "接続中" : "未接続"}</span>
      </div>
    </div>
  );
}

// ─── KPI card ────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  icon,
  dot,
  isMono,
}: {
  label: string;
  value: string | number;
  sub: string;
  icon: React.ReactNode;
  dot?: string;
  isMono?: boolean;
}) {
  return (
    <div className="rounded-md bg-[#11141a] border border-white/10 px-3 py-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">
          {label}
        </span>
        <span className="text-neutral-600">{icon}</span>
      </div>
      <div className="flex items-baseline gap-2">
        {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
        <span
          className={`text-xl font-semibold text-white ${
            isMono ? "tabular-nums font-mono" : ""
          }`}
        >
          {value}
        </span>
      </div>
      <div className="text-[10px] text-neutral-600 mt-0.5">{sub}</div>
    </div>
  );
}
