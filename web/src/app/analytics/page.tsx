"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart2,
  Activity,
  DollarSign,
  TrendingUp,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  AlertTriangle,
  Database,
} from "lucide-react";
import {
  fetchAnalyticsDashboard,
  fetchAnalyticsGeneration,
  fetchAnalyticsCosts,
  fetchAnalyticsThemes,
  fetchAnalyticsEvents,
  fetchAnalyticsHealth,
  type DashboardSummary,
  type ProviderStats,
  type CostDataPoint,
  type ThemeUsageStats,
  type EventLogEntry,
  type HealthStatus,
} from "@/lib/api";

// ─── ヘルパー ──────────────────────────────────────────────────────────────

const DAY_LABEL: Record<string, string> = {
  monday: "月曜",
  tuesday: "火曜",
  wednesday: "水曜",
  thursday: "木曜",
  friday: "金曜",
  saturday: "土曜",
  sunday: "日曜",
};

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatCost(cost: number): string {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

// ─── サマリーカード ────────────────────────────────────────────────────────

function SummaryCard({
  title,
  value,
  sub,
  icon: Icon,
  accent = "blue",
}: {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent?: "blue" | "green" | "yellow" | "red";
}) {
  const colors: Record<string, string> = {
    blue: "text-blue-400 bg-blue-500/10",
    green: "text-emerald-400 bg-emerald-500/10",
    yellow: "text-yellow-400 bg-yellow-500/10",
    red: "text-red-400 bg-red-500/10",
  };
  return (
    <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-1">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colors[accent]}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

// ─── 水平バーチャート ──────────────────────────────────────────────────────

function HBar({ label, value, max, color = "#3b82f6", sub }: {
  label: string;
  value: number;
  max: number;
  color?: string;
  sub?: string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs text-slate-300 font-mono">{sub ?? value}</span>
      </div>
      <div className="h-1.5 bg-blue-400/[0.07] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

// ─── プロバイダー別パフォーマンステーブル ─────────────────────────────────

function ProviderTable({ providers }: { providers: ProviderStats[] }) {
  if (providers.length === 0) {
    return (
      <p className="text-xs text-slate-600 py-6 text-center">データなし</p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-blue-400/[0.08]">
            <th className="text-left py-2 pr-3">プロバイダー</th>
            <th className="text-left py-2 pr-3">種別</th>
            <th className="text-right py-2 pr-3">成功率</th>
            <th className="text-right py-2 pr-3">平均API時間</th>
            <th className="text-right py-2 pr-3">平均合計時間</th>
            <th className="text-right py-2">コスト</th>
          </tr>
        </thead>
        <tbody>
          {providers.map((p, i) => (
            <tr key={i} className="border-b border-blue-400/[0.04] hover:bg-blue-400/[0.02]">
              <td className="py-2 pr-3 text-white font-medium">{p.provider}</td>
              <td className="py-2 pr-3 text-slate-400">{p.generation_type}</td>
              <td className="py-2 pr-3 text-right">
                <span className={p.success_rate >= 90 ? "text-emerald-400" : p.success_rate >= 70 ? "text-yellow-400" : "text-red-400"}>
                  {p.success_rate.toFixed(1)}%
                </span>
                <span className="text-slate-600 ml-1">({p.success_count}/{p.total_count})</span>
              </td>
              <td className="py-2 pr-3 text-right text-slate-300 font-mono">{formatMs(p.avg_api_duration_ms)}</td>
              <td className="py-2 pr-3 text-right text-slate-300 font-mono">{formatMs(p.avg_total_duration_ms)}</td>
              <td className="py-2 text-right text-slate-300 font-mono">{formatCost(p.total_cost_estimate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── コスト積み上げビュー ──────────────────────────────────────────────────

function CostTimeline({ data }: { data: CostDataPoint[] }) {
  if (data.length === 0) {
    return <p className="text-xs text-slate-600 py-6 text-center">データなし</p>;
  }

  // 日付ごとにプロバイダー別コストを集計
  const byDate = new Map<string, { total: number; providers: Record<string, number> }>();
  for (const d of data) {
    if (!byDate.has(d.date)) byDate.set(d.date, { total: 0, providers: {} });
    const entry = byDate.get(d.date)!;
    entry.providers[d.provider] = (entry.providers[d.provider] ?? 0) + d.cost_estimate;
    entry.total += d.cost_estimate;
  }
  const dates = Array.from(byDate.keys()).sort();
  const maxTotal = Math.max(...Array.from(byDate.values()).map((v) => v.total), 0.001);

  const providers = Array.from(new Set(data.map((d) => d.provider)));
  const providerColors: string[] = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

  return (
    <div>
      <div className="flex gap-4 mb-4 flex-wrap">
        {providers.map((p, i) => (
          <div key={p} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: providerColors[i % providerColors.length] }} />
            <span className="text-xs text-slate-400">{p}</span>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {dates.slice(-14).map((date) => {
          const entry = byDate.get(date)!;
          return (
            <div key={date} className="flex items-center gap-3">
              <span className="text-[10px] text-slate-600 w-20 shrink-0">{date.slice(5)}</span>
              <div className="flex-1 h-3 bg-blue-400/[0.07] rounded-full overflow-hidden flex">
                {providers.map((p, i) => {
                  const cost = entry.providers[p] ?? 0;
                  const pct = (cost / maxTotal) * 100;
                  if (pct < 0.5) return null;
                  return (
                    <div
                      key={p}
                      className="h-full"
                      style={{ width: `${pct}%`, backgroundColor: providerColors[i % providerColors.length] }}
                      title={`${p}: ${formatCost(cost)}`}
                    />
                  );
                })}
              </div>
              <span className="text-[10px] text-slate-500 font-mono w-16 text-right">{formatCost(entry.total)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── イベントログ ─────────────────────────────────────────────────────────

const CATEGORY_COLOR: Record<string, string> = {
  session: "bg-blue-500/20 text-blue-300",
  course: "bg-emerald-500/20 text-emerald-300",
  show: "bg-purple-500/20 text-purple-300",
  generation: "bg-yellow-500/20 text-yellow-300",
  system: "bg-slate-500/20 text-slate-300",
};

function EventLogTable({ events }: { events: EventLogEntry[] }) {
  if (events.length === 0) {
    return <p className="text-xs text-slate-600 py-6 text-center">イベントなし</p>;
  }
  return (
    <div className="space-y-1 max-h-72 overflow-y-auto pr-1">
      {events.map((e) => (
        <div key={e.id} className="flex items-start gap-3 py-1.5 border-b border-blue-400/[0.04]">
          <span className="text-[10px] text-slate-600 font-mono w-36 shrink-0 pt-0.5">
            {new Date(e.timestamp).toLocaleString("ja-JP", { hour12: false })}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${CATEGORY_COLOR[e.event_category] ?? "bg-slate-700 text-slate-300"}`}>
            {e.event_category}
          </span>
          <span className="text-xs text-slate-300 break-all">{e.event_type}</span>
        </div>
      ))}
    </div>
  );
}

// ─── メインページ ─────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [providers, setProviders] = useState<ProviderStats[]>([]);
  const [costs, setCosts] = useState<CostDataPoint[]>([]);
  const [themes, setThemes] = useState<ThemeUsageStats[]>([]);
  const [events, setEvents] = useState<EventLogEntry[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, g, c, t, ev, h] = await Promise.allSettled([
        fetchAnalyticsDashboard(),
        fetchAnalyticsGeneration(7),
        fetchAnalyticsCosts(30),
        fetchAnalyticsThemes(),
        fetchAnalyticsEvents({ limit: 50 }),
        fetchAnalyticsHealth(),
      ]);
      if (s.status === "fulfilled") setSummary(s.value);
      if (g.status === "fulfilled") setProviders(g.value.providers);
      if (c.status === "fulfilled") setCosts(c.value.data);
      if (t.status === "fulfilled") setThemes(t.value.themes);
      if (ev.status === "fulfilled") setEvents(ev.value);
      if (h.status === "fulfilled") setHealth(h.value);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const maxThemeCount = Math.max(...themes.map((t) => t.storyboard_count), 1);

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/20 flex items-center justify-center">
            <BarChart2 size={18} className="text-blue-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">分析ダッシュボード</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              最終更新: {lastRefresh.toLocaleTimeString("ja-JP", { hour12: false })}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {health && (
            <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border ${
              health.status === "ok"
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-red-500/10 border-red-500/20 text-red-400"
            }`}>
              <Database size={12} />
              {health.status === "ok" ? "システム正常" : "システム異常"}
            </div>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg border border-blue-400/[0.10] hover:border-blue-400/30 transition-all disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            更新
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-center gap-3 text-red-400 text-sm">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {/* サマリーカード */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="今日のセッション"
          value={summary?.total_sessions ?? "—"}
          icon={Activity}
          accent="blue"
        />
        <SummaryCard
          title="今日の生成数"
          value={summary?.total_generations ?? "—"}
          sub={summary ? `成功率 ${summary.generation_success_rate}%` : undefined}
          icon={TrendingUp}
          accent={
            summary?.generation_success_rate == null
              ? "blue"
              : summary.generation_success_rate >= 90
              ? "green"
              : summary.generation_success_rate >= 70
              ? "yellow"
              : "red"
          }
        />
        <SummaryCard
          title="今日のコスト"
          value={summary ? formatCost(summary.total_cost_estimate) : "—"}
          icon={DollarSign}
          accent="yellow"
        />
        <SummaryCard
          title="システムヘルス"
          value={health?.db_connected ? "正常" : "異常"}
          sub={health ? `5分間イベント: ${health.recent_events_5min}件` : undefined}
          icon={health?.db_connected ? CheckCircle : XCircle}
          accent={health?.db_connected ? "green" : "red"}
        />
      </div>

      {/* 2カラムグリッド */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI生成パフォーマンス */}
        <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Clock size={15} className="text-blue-400" />
            <h2 className="text-sm font-semibold">AI生成パフォーマンス（7日間）</h2>
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center">
              <RefreshCw size={16} className="animate-spin text-slate-600" />
            </div>
          ) : (
            <>
              <ProviderTable providers={providers} />
              {summary && (
                <div className="mt-4 pt-4 border-t border-blue-400/[0.08] grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-1">平均画像生成時間</p>
                    <p className="text-lg font-bold text-blue-300 font-mono">{formatMs(summary.avg_image_duration_ms)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-1">平均動画生成時間</p>
                    <p className="text-lg font-bold text-purple-300 font-mono">{formatMs(summary.avg_video_duration_ms)}</p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* コスト分析 */}
        <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <DollarSign size={15} className="text-yellow-400" />
            <h2 className="text-sm font-semibold">コスト分析（30日間）</h2>
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center">
              <RefreshCw size={16} className="animate-spin text-slate-600" />
            </div>
          ) : (
            <CostTimeline data={costs} />
          )}
        </div>
      </div>

      {/* テーマ別利用ランキング + イベントカテゴリー */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* テーマ別ランキング */}
        <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <BarChart2 size={15} className="text-emerald-400" />
            <h2 className="text-sm font-semibold">テーマ別利用ランキング</h2>
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center">
              <RefreshCw size={16} className="animate-spin text-slate-600" />
            </div>
          ) : themes.length === 0 ? (
            <p className="text-xs text-slate-600 py-6 text-center">データなし</p>
          ) : (
            <div>
              {themes
                .sort((a, b) => b.storyboard_count - a.storyboard_count)
                .map((t) => (
                  <HBar
                    key={t.day_of_week}
                    label={DAY_LABEL[t.day_of_week] ?? t.day_of_week}
                    value={t.storyboard_count}
                    max={maxThemeCount}
                    color="#10b981"
                    sub={`${t.storyboard_count}件 (画像:${t.image_ready_count} / 動画:${t.video_ready_count})`}
                  />
                ))}
            </div>
          )}
        </div>

        {/* 今日のイベントカテゴリー分布 */}
        <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-5">
            <Activity size={15} className="text-purple-400" />
            <h2 className="text-sm font-semibold">今日のイベント分布</h2>
          </div>
          {loading ? (
            <div className="h-40 flex items-center justify-center">
              <RefreshCw size={16} className="animate-spin text-slate-600" />
            </div>
          ) : summary && Object.keys(summary.event_counts_by_category).length > 0 ? (
            <div>
              {Object.entries(summary.event_counts_by_category)
                .sort((a, b) => b[1] - a[1])
                .map(([cat, count]) => {
                  const maxCount = Math.max(...Object.values(summary.event_counts_by_category));
                  return (
                    <HBar
                      key={cat}
                      label={cat}
                      value={count}
                      max={maxCount}
                      color="#8b5cf6"
                      sub={`${count}件`}
                    />
                  );
                })}
            </div>
          ) : (
            <p className="text-xs text-slate-600 py-6 text-center">今日のイベントなし</p>
          )}
        </div>
      </div>

      {/* 最近のイベントログ */}
      <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Activity size={15} className="text-slate-400" />
            <h2 className="text-sm font-semibold">最近のイベントログ</h2>
          </div>
          <span className="text-[10px] text-slate-600">{events.length}件表示</span>
        </div>
        {loading ? (
          <div className="h-24 flex items-center justify-center">
            <RefreshCw size={16} className="animate-spin text-slate-600" />
          </div>
        ) : (
          <EventLogTable events={events} />
        )}
      </div>

      {/* システムヘルス詳細 */}
      {health?.last_generation_error && (
        <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <XCircle size={14} className="text-red-400" />
            <h2 className="text-sm font-semibold text-red-400">最後の生成エラー</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div>
              <p className="text-slate-600 mb-1">プロバイダー</p>
              <p className="text-slate-300">{health.last_generation_error.provider}</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">発生時刻</p>
              <p className="text-slate-300">{new Date(health.last_generation_error.timestamp).toLocaleString("ja-JP", { hour12: false })}</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">エラー内容</p>
              <p className="text-red-300 break-all">{health.last_generation_error.error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
