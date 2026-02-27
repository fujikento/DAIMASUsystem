"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Settings,
  Palette,
  RotateCcw,
  Save,
  CheckCircle2,
  XCircle,
  X,
} from "lucide-react";
import {
  fetchThemes,
  updateTheme,
  resetThemes,
  type DayThemeData,
} from "@/lib/api";
import { DAY_LABELS } from "@/lib/themes";

const PRESET_COLORS = [
  "#8B7355", "#FF4500", "#006994", "#228B22", "#FFD700",
  "#4B0082", "#FF69B4", "#DC143C", "#1E90FF", "#00CED1",
  "#FF8C00", "#9370DB", "#20B2AA", "#CD853F", "#708090",
];

const PRESET_ICONS = [
  "\u{1F38D}", "\u{1F525}", "\u{1F30A}", "\u{1F332}", "\u{2728}",
  "\u{1F680}", "\u{1F4D6}", "\u{1F338}", "\u{1F319}", "\u{2744}\u{FE0F}",
  "\u{1F308}", "\u{1F3B5}", "\u{1F48E}", "\u{1F30B}", "\u{1F3AD}",
  "\u{1F996}", "\u{1F9CA}", "\u{1F52E}", "\u{1F3A8}", "\u{1F341}",
];

const GRADIENT_OPTIONS = [
  { value: "from-blue-950 to-stone-900", label: "Blue / Stone" },
  { value: "from-red-950 to-orange-950", label: "Red / Orange" },
  { value: "from-cyan-950 to-blue-950", label: "Cyan / Blue" },
  { value: "from-green-950 to-emerald-950", label: "Green / Emerald" },
  { value: "from-yellow-950 to-blue-950", label: "Yellow / Blue" },
  { value: "from-indigo-950 to-purple-950", label: "Indigo / Purple" },
  { value: "from-pink-950 to-rose-950", label: "Pink / Rose" },
  { value: "from-slate-950 to-zinc-950", label: "Slate / Zinc" },
  { value: "from-teal-950 to-cyan-950", label: "Teal / Cyan" },
  { value: "from-violet-950 to-fuchsia-950", label: "Violet / Fuchsia" },
];

export default function SettingsPage() {
  const [themes, setThemes] = useState<DayThemeData[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingDay, setEditingDay] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Edit form state
  const [formNameJa, setFormNameJa] = useState("");
  const [formNameEn, setFormNameEn] = useState("");
  const [formColor, setFormColor] = useState("");
  const [formIcon, setFormIcon] = useState("");
  const [formGradient, setFormGradient] = useState("");
  const [saving, setSaving] = useState(false);

  const loadThemes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchThemes();
      setThemes(data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadThemes();
  }, [loadThemes]);

  function showFeedback(type: "success" | "error", message: string) {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 3000);
  }

  function startEdit(theme: DayThemeData) {
    setEditingDay(theme.day_of_week);
    setFormNameJa(theme.name_ja);
    setFormNameEn(theme.name_en);
    setFormColor(theme.color);
    setFormIcon(theme.icon);
    setFormGradient(theme.bg_gradient);
  }

  function cancelEdit() {
    setEditingDay(null);
  }

  async function handleSave() {
    if (!editingDay) return;
    setSaving(true);
    try {
      await updateTheme(editingDay, {
        name_ja: formNameJa,
        name_en: formNameEn,
        color: formColor,
        icon: formIcon,
        bg_gradient: formGradient,
      });
      showFeedback("success", `${DAY_LABELS[editingDay]}のテーマを更新しました`);
      setEditingDay(null);
      loadThemes();
    } catch {
      showFeedback("error", "更新に失敗しました");
    }
    setSaving(false);
  }

  async function handleReset() {
    if (!confirm("全てのテーマをデフォルトに戻しますか？")) return;
    try {
      await resetThemes();
      showFeedback("success", "デフォルトテーマにリセットしました");
      setEditingDay(null);
      loadThemes();
    } catch {
      showFeedback("error", "リセットに失敗しました");
    }
  }

  const editingTheme = themes.find((t) => t.day_of_week === editingDay);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">曜日テーマ設定</h2>
          <p className="text-neutral-400 text-sm mt-1">
            曜日ごとのテーマカラー・アイコン・背景をカスタマイズ
          </p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-4 py-2 bg-white/[0.06] hover:bg-white/[0.1] rounded-xl text-sm text-neutral-400 hover:text-white transition-all"
        >
          <RotateCcw size={15} /> デフォルトに戻す
        </button>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm ${
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
              : "bg-red-500/10 text-red-400 border border-red-500/15"
          }`}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 size={16} />
          ) : (
            <XCircle size={16} />
          )}
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Theme Grid */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2">
            <Palette size={16} className="text-neutral-500" />
            <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-widest">
              曜日テーマ一覧
            </h3>
          </div>

          {loading ? (
            <div className="text-center py-16 text-neutral-500 text-sm">
              読み込み中...
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {themes.map((theme) => {
                const isEditing = editingDay === theme.day_of_week;
                return (
                  <button
                    key={theme.day_of_week}
                    onClick={() => startEdit(theme)}
                    className={`text-left p-5 rounded-2xl border transition-all ${
                      isEditing
                        ? "bg-blue-500/10 border-blue-500/20 ring-1 ring-blue-500/20"
                        : "bg-[#141414] border-white/[0.06] hover:border-white/[0.12] hover:bg-[#181818]"
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      {/* Icon & color preview */}
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0"
                        style={{ backgroundColor: theme.color + "20" }}
                      >
                        {theme.icon}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-medium text-neutral-500">
                            {DAY_LABELS[theme.day_of_week]}
                          </span>
                          <div
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: theme.color }}
                          />
                        </div>
                        <h4 className="text-white font-medium mt-0.5 truncate">
                          {theme.name_ja}
                        </h4>
                        <p className="text-xs text-neutral-500 mt-0.5">
                          {theme.name_en}
                        </p>
                      </div>

                      {/* Color code */}
                      <span className="text-xs font-mono text-neutral-600 flex-shrink-0">
                        {theme.color}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Edit Panel */}
        <div>
          {editingTheme ? (
            <div className="bg-[#141414] rounded-2xl border border-white/[0.06] p-6 space-y-5 sticky top-8">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">
                  {DAY_LABELS[editingTheme.day_of_week]} テーマ編集
                </h3>
                <button
                  onClick={cancelEdit}
                  className="p-1 text-neutral-500 hover:text-white transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Preview */}
              <div
                className="rounded-xl p-4 text-center"
                style={{ backgroundColor: formColor + "15" }}
              >
                <span className="text-3xl">{formIcon}</span>
                <p
                  className="text-sm font-semibold mt-2"
                  style={{ color: formColor }}
                >
                  {formNameJa}
                </p>
              </div>

              {/* Name JA */}
              <div>
                <label className="block text-xs text-neutral-400 mb-1.5">
                  テーマ名（日本語）
                </label>
                <input
                  type="text"
                  value={formNameJa}
                  onChange={(e) => setFormNameJa(e.target.value)}
                  className="w-full px-3 py-2.5 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 transition-colors"
                  placeholder="和 〜 Japanese Zen"
                />
              </div>

              {/* Name EN */}
              <div>
                <label className="block text-xs text-neutral-400 mb-1.5">
                  テーマ名（英語）
                </label>
                <input
                  type="text"
                  value={formNameEn}
                  onChange={(e) => setFormNameEn(e.target.value)}
                  className="w-full px-3 py-2.5 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 transition-colors"
                  placeholder="Japanese Zen"
                />
              </div>

              {/* Color */}
              <div>
                <label className="block text-xs text-neutral-400 mb-1.5">
                  テーマカラー
                </label>
                <div className="flex items-center gap-3 mb-2">
                  <input
                    type="color"
                    value={formColor}
                    onChange={(e) => setFormColor(e.target.value)}
                    className="w-10 h-10 rounded-lg cursor-pointer border-0 bg-transparent"
                  />
                  <input
                    type="text"
                    value={formColor}
                    onChange={(e) => setFormColor(e.target.value)}
                    className="flex-1 px-3 py-2.5 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm font-mono text-white focus:border-blue-500/40 transition-colors"
                  />
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {PRESET_COLORS.map((c) => (
                    <button
                      key={c}
                      onClick={() => setFormColor(c)}
                      className={`w-6 h-6 rounded-md transition-all ${
                        formColor === c
                          ? "ring-2 ring-white ring-offset-2 ring-offset-[#141414]"
                          : "hover:scale-110"
                      }`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              {/* Icon */}
              <div>
                <label className="block text-xs text-neutral-400 mb-1.5">
                  アイコン
                </label>
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-white/[0.06] flex items-center justify-center text-xl">
                    {formIcon}
                  </div>
                  <input
                    type="text"
                    value={formIcon}
                    onChange={(e) => setFormIcon(e.target.value)}
                    className="flex-1 px-3 py-2.5 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white focus:border-blue-500/40 transition-colors"
                  />
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {PRESET_ICONS.map((icon, i) => (
                    <button
                      key={i}
                      onClick={() => setFormIcon(icon)}
                      className={`w-8 h-8 rounded-lg text-base flex items-center justify-center transition-all ${
                        formIcon === icon
                          ? "bg-blue-500/20 ring-1 ring-blue-500/30"
                          : "bg-white/[0.04] hover:bg-white/[0.08]"
                      }`}
                    >
                      {icon}
                    </button>
                  ))}
                </div>
              </div>

              {/* Gradient */}
              <div>
                <label className="block text-xs text-neutral-400 mb-1.5">
                  背景グラデーション
                </label>
                <select
                  value={formGradient}
                  onChange={(e) => setFormGradient(e.target.value)}
                  className="w-full px-3 py-2.5 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white focus:border-blue-500/40 transition-colors"
                >
                  {GRADIENT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Save */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-xl text-sm transition-colors"
                >
                  <Save size={15} />
                  {saving ? "保存中..." : "保存"}
                </button>
                <button
                  onClick={cancelEdit}
                  className="px-4 py-2.5 bg-white/[0.06] hover:bg-white/[0.1] rounded-xl text-sm text-neutral-400 hover:text-white transition-all"
                >
                  キャンセル
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-[#141414] rounded-2xl border border-white/[0.06] p-6 text-center">
              <Settings
                size={32}
                className="mx-auto text-neutral-600 mb-3"
              />
              <p className="text-sm text-neutral-400">
                左のテーマをクリックして編集
              </p>
              <div className="mt-6 text-left space-y-3">
                <h4 className="text-xs font-medium text-neutral-600 uppercase tracking-widest">
                  カスタマイズ項目
                </h4>
                <ul className="space-y-2 text-xs text-neutral-500">
                  <li>テーマ名（日本語・英語）</li>
                  <li>テーマカラー</li>
                  <li>アイコン絵文字</li>
                  <li>背景グラデーション</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
