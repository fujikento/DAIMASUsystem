"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertTriangle,
  Plus,
  Table as TableIcon,
} from "lucide-react";
import {
  createStoryboard,
  fetchTables,
  type ProjectionTable,
} from "@/lib/api";
import WizardProgress from "../components/WizardProgress";

// ─ Theme presets (sober palette, flat swatches) ──────────────
const THEMES: Array<{
  key: string;
  jp: string;
  desc: string;
  swatch: string;
  day: string;
}> = [
  { key: "zen", jp: "禅", desc: "静謐・墨と石庭", swatch: "#3a4045", day: "monday" },
  { key: "fire", jp: "炎", desc: "情熱・灯火と火花", swatch: "#7c2d1e", day: "tuesday" },
  { key: "ocean", jp: "海", desc: "深い青・水中の光", swatch: "#1e3a5f", day: "wednesday" },
  { key: "forest", jp: "森", desc: "緑と苔・木漏れ日", swatch: "#1f3b29", day: "thursday" },
  { key: "gold", jp: "金", desc: "金色の輝き", swatch: "#7a5810", day: "friday" },
  { key: "space", jp: "宇宙", desc: "星雲・銀河", swatch: "#2a1e4a", day: "saturday" },
  { key: "fairytale", jp: "童話", desc: "夢のような色彩", swatch: "#6b2a4f", day: "sunday" },
];

const DAY_LABEL: Record<string, string> = {
  monday: "月", tuesday: "火", wednesday: "水", thursday: "木",
  friday: "金", saturday: "土", sunday: "日",
};

export default function NewWizardStep1() {
  const router = useRouter();
  const [tables, setTables] = useState<ProjectionTable[] | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<string>("zen");
  const [title, setTitle] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTables()
      .then((data) => {
        setTables(data);
        const def = data.find((t) => t.is_default) ?? data[0];
        if (def) setSelectedTableId(def.id);
      })
      .catch(() => setTables([]));
  }, []);

  const theme = THEMES.find((t) => t.key === selectedTheme) ?? THEMES[0];
  const selectedTable = tables?.find((t) => t.id === selectedTableId) ?? null;

  async function handleSubmit() {
    if (!selectedTableId) {
      setError("席 (テーブル) を選んでください");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const sb = await createStoryboard({
        title: title.trim() || `${theme.jp}の夜`,
        theme: selectedTheme,
        day_of_week: theme.day,
        projection_config_id: selectedTableId,
        auto_generate_scenes: true,
      });
      router.push(`/create/${sb.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "台本の作成に失敗しました");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <WizardProgress current={1} />

      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-white">新規台本</h1>
        <p className="text-xs text-neutral-500">
          席と曜日テーマを選んで、AIに台本を書かせる準備をします。
        </p>
      </div>

      {/* ─ Section: Table picker ─ */}
      <section className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
        <div className="px-4 py-2 border-b border-white/10 bg-white/[0.02] flex items-center justify-between">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
            1. どの席用ですか
          </h2>
          <Link
            href="/tables"
            className="inline-flex items-center gap-1 text-[11px] text-neutral-500 hover:text-blue-300 transition-colors"
          >
            <Plus size={11} />
            席を追加
          </Link>
        </div>
        <div className="p-3">
          {tables === null ? (
            <div className="flex items-center justify-center py-4 text-neutral-500">
              <Loader2 size={14} className="animate-spin" />
            </div>
          ) : tables.length === 0 ? (
            <div className="text-center py-6 space-y-2">
              <TableIcon size={20} className="text-neutral-600 mx-auto" />
              <p className="text-xs text-neutral-500">
                席が登録されていません。先に席を登録してください。
              </p>
              <Link
                href="/tables"
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
              >
                <Plus size={11} />
                席を登録する
              </Link>
            </div>
          ) : (
            <div className="space-y-1">
              {tables.map((t) => {
                const active = t.id === selectedTableId;
                return (
                  <button
                    key={t.id}
                    onClick={() => setSelectedTableId(t.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded text-left transition-colors ${
                      active
                        ? "bg-blue-500/10 border border-blue-400/40"
                        : "bg-transparent border border-transparent hover:bg-white/[0.03]"
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full border-2 shrink-0 ${
                        active
                          ? "border-blue-400 bg-blue-400"
                          : "border-neutral-600"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-white font-medium">{t.name}</span>
                        {t.is_default && (
                          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">
                            (default)
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-neutral-500 tabular-nums">
                        {t.table_width_mm}×{t.table_height_mm}mm · 投影 {t.full_width}×{t.full_height}px · PJ {t.pj_count}台
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ─ Section: Theme picker ─ */}
      <section className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
        <div className="px-4 py-2 border-b border-white/10 bg-white/[0.02]">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
            2. テーマ
          </h2>
        </div>
        <div className="p-3 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          {THEMES.map((t) => {
            const active = t.key === selectedTheme;
            return (
              <button
                key={t.key}
                onClick={() => setSelectedTheme(t.key)}
                className={`relative p-3 rounded transition-all text-left ${
                  active
                    ? "ring-1 ring-blue-400 bg-white/[0.04]"
                    : "hover:bg-white/[0.03]"
                }`}
              >
                <div
                  className="w-full h-12 rounded mb-2"
                  style={{ backgroundColor: t.swatch }}
                />
                <div className="flex items-baseline justify-between gap-1">
                  <span className="text-sm font-medium text-white">{t.jp}</span>
                  <span className="text-[10px] text-neutral-500">
                    {DAY_LABEL[t.day]}
                  </span>
                </div>
                <p className="text-[10px] text-neutral-500 leading-snug mt-0.5">
                  {t.desc}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      {/* ─ Section: Title ─ */}
      <section className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
        <div className="px-4 py-2 border-b border-white/10 bg-white/[0.02]">
          <h2 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
            3. タイトル (任意)
          </h2>
        </div>
        <div className="p-3 space-y-1.5">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={`空欄なら「${theme.jp}の夜」`}
            maxLength={50}
            className="w-full bg-[#0a0d12] border border-white/10 rounded px-3 py-2 text-sm text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none"
          />
          {selectedTable && (
            <p className="text-[11px] text-neutral-500">
              席「<span className="text-neutral-300">{selectedTable.name}</span>」用に作成。
              動画解像度は {selectedTable.full_width}×{selectedTable.full_height}px に最適化。
            </p>
          )}
        </div>
      </section>

      {/* ─ Error ─ */}
      {error && (
        <div className="rounded-md bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-300 flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* ─ Footer nav ─ */}
      <div className="flex items-center justify-between pt-2 border-t border-white/[0.04] -mx-2 px-2">
        <Link
          href="/create"
          className="inline-flex items-center gap-1 text-sm text-neutral-400 hover:text-white transition-colors"
        >
          <ChevronLeft size={14} />
          一覧
        </Link>
        <button
          onClick={handleSubmit}
          disabled={submitting || !selectedTableId}
          className="inline-flex items-center gap-1.5 px-5 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? (
            <>
              <Loader2 size={13} className="animate-spin" />
              作成中
            </>
          ) : (
            <>
              次へ:台本
              <ChevronRight size={13} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
