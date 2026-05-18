"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Sparkles,
  Mountain,
  Flame,
  Waves,
  Trees,
  Crown,
  Stars,
  Wand2,
  Calendar,
} from "lucide-react";
import { createStoryboard } from "@/lib/api";
import WizardProgress from "../components/WizardProgress";

// ─ Theme presets (mirrors backend day_to_theme) ─────────────────────────
const THEMES: Array<{
  key: string;
  label: string;
  jp: string;
  desc: string;
  icon: React.ReactNode;
  color: string;
  day: string;
}> = [
  {
    key: "zen",
    label: "Zen",
    jp: "禅",
    desc: "静謐な和の世界、墨と石庭",
    icon: <Mountain size={26} />,
    color: "from-slate-700 to-slate-900",
    day: "monday",
  },
  {
    key: "fire",
    label: "Fire",
    jp: "炎",
    desc: "情熱の赤、灯火と火花",
    icon: <Flame size={26} />,
    color: "from-red-700 to-orange-900",
    day: "tuesday",
  },
  {
    key: "ocean",
    label: "Ocean",
    jp: "海",
    desc: "深い青、波と水中の光",
    icon: <Waves size={26} />,
    color: "from-blue-700 to-cyan-900",
    day: "wednesday",
  },
  {
    key: "forest",
    label: "Forest",
    jp: "森",
    desc: "緑と苔、木漏れ日",
    icon: <Trees size={26} />,
    color: "from-emerald-700 to-green-900",
    day: "thursday",
  },
  {
    key: "gold",
    label: "Gold",
    jp: "金",
    desc: "豪華絢爛、金色の輝き",
    icon: <Crown size={26} />,
    color: "from-amber-600 to-yellow-800",
    day: "friday",
  },
  {
    key: "space",
    label: "Space",
    jp: "宇宙",
    desc: "星雲と銀河、無限の暗闇",
    icon: <Stars size={26} />,
    color: "from-indigo-800 to-purple-900",
    day: "saturday",
  },
  {
    key: "fairytale",
    label: "Fairytale",
    jp: "童話",
    desc: "夢のような色彩、メルヘン",
    icon: <Wand2 size={26} />,
    color: "from-pink-600 to-fuchsia-800",
    day: "sunday",
  },
];

const DAY_LABEL: Record<string, string> = {
  monday: "月曜",
  tuesday: "火曜",
  wednesday: "水曜",
  thursday: "木曜",
  friday: "金曜",
  saturday: "土曜",
  sunday: "日曜",
};

export default function NewWizardStep1() {
  const router = useRouter();
  const [selectedTheme, setSelectedTheme] = useState<string>("zen");
  const [title, setTitle] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const theme = THEMES.find((t) => t.key === selectedTheme) ?? THEMES[0];

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const sb = await createStoryboard({
        title: title.trim() || `${theme.jp}の夜`,
        theme: selectedTheme,
        day_of_week: theme.day,
        auto_generate_scenes: true,
      });
      router.push(`/create/${sb.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "台本の作成に失敗しました");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      <WizardProgress current={1} />

      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-white tracking-tight">
          テーマを選んでください
        </h1>
        <p className="text-neutral-400 text-sm">
          テーマで世界観・色合い・雰囲気が決まります。後で変更も可能です。
        </p>
      </div>

      {/* ─ Theme grid ─ */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {THEMES.map((t) => {
          const active = t.key === selectedTheme;
          return (
            <button
              key={t.key}
              onClick={() => setSelectedTheme(t.key)}
              className={`group relative rounded-2xl p-5 text-left transition-all border-2 ${
                active
                  ? "border-blue-400 shadow-lg shadow-blue-900/40 scale-[1.02]"
                  : "border-white/[0.06] hover:border-white/20"
              }`}
            >
              <div
                className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${t.color} ${
                  active ? "opacity-90" : "opacity-50 group-hover:opacity-70"
                } transition-opacity`}
              />
              <div className="relative z-10 space-y-2">
                <div className="flex items-start justify-between">
                  <div className="text-white">{t.icon}</div>
                  <span className="text-[10px] font-bold tracking-wider uppercase text-white/70">
                    {DAY_LABEL[t.day]}
                  </span>
                </div>
                <div>
                  <p className="text-white text-2xl font-bold leading-none">
                    {t.jp}
                  </p>
                  <p className="text-white/60 text-[10px] uppercase tracking-widest mt-1">
                    {t.label}
                  </p>
                </div>
                <p className="text-white/80 text-xs leading-relaxed pt-1">
                  {t.desc}
                </p>
              </div>
              {active && (
                <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-blue-500 border-2 border-white flex items-center justify-center z-20">
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="white"
                    strokeWidth="3"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* ─ Title input ─ */}
      <div className="bg-[#0e1d32] rounded-2xl border border-blue-400/10 p-5 space-y-3">
        <label className="flex items-center gap-2 text-sm font-semibold text-neutral-300">
          <Sparkles size={14} className="text-blue-400" />
          台本のタイトル
          <span className="text-xs text-neutral-600 font-normal">
            (空欄なら自動: 「{theme.jp}の夜」)
          </span>
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={`${theme.jp}の夜`}
          maxLength={50}
          className="w-full bg-[#0a1628] border border-white/10 rounded-xl px-4 py-3 text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none transition-colors"
        />
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <Calendar size={11} />
          <span>
            曜日テーマ: <strong className="text-neutral-400">{DAY_LABEL[theme.day]}</strong>{" "}
            (この曜日の予約に自動で使われます)
          </span>
        </div>
      </div>

      {/* ─ Error display ─ */}
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* ─ Footer nav ─ */}
      <div className="flex items-center justify-between pt-2">
        <Link
          href="/create"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-white transition-colors"
        >
          <ChevronLeft size={16} />
          戻る
        </Link>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-base shadow-lg shadow-blue-900/40 transition-all hover:scale-[1.02] active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {submitting ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              作成中...
            </>
          ) : (
            <>
              次へ:台本を作る
              <ChevronRight size={18} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
