"use client";

import React, { useState } from "react";
import {
  Video,
  Zap,
  Star,
  Clock,
  Sparkles,
  Lock,
  Unlock,
  ChevronDown,
  Info,
} from "lucide-react";

// ── プロバイダー定義 ──────────────────────────────────────────

const PROVIDERS = [
  {
    id: "runway",
    name: "Runway Gen-4.5",
    badge: "最高品質",
    badgeColor: "bg-blue-500/20 text-blue-300 border border-blue-400/30",
    description: "映画レベルの映像品質。モーション制御に優れる",
    resolutions: ["1920×1080", "1280×720"],
    defaultResolution: "1920×1080",
    estimatedTimes: {
      maximum: "8〜12分",
      balanced: "4〜6分",
      preview: "1〜2分",
    },
    estimatedCosts: {
      maximum: "約 $0.40/シーン",
      balanced: "約 $0.25/シーン",
      preview: "約 $0.10/シーン",
    },
    accentClass: "border-blue-400/40 bg-blue-500/[0.06]",
    accentSelected: "border-blue-400 bg-blue-500/[0.12] ring-1 ring-blue-400/40",
    dotColor: "bg-blue-400",
  },
  {
    id: "kling",
    name: "Kling 2.6",
    badge: "高フォトリアル",
    badgeColor: "bg-purple-500/20 text-purple-300 border border-purple-400/30",
    description: "超リアルな映像表現。長尺シーンに対応",
    resolutions: ["1920×1080", "1280×720"],
    defaultResolution: "1920×1080",
    estimatedTimes: {
      maximum: "10〜15分",
      balanced: "5〜8分",
      preview: "2〜3分",
    },
    estimatedCosts: {
      maximum: "約 $0.35/シーン",
      balanced: "約 $0.20/シーン",
      preview: "約 $0.08/シーン",
    },
    accentClass: "border-purple-400/40 bg-purple-500/[0.06]",
    accentSelected: "border-purple-400 bg-purple-500/[0.12] ring-1 ring-purple-400/40",
    dotColor: "bg-purple-400",
  },
  {
    id: "pika",
    name: "Pika 2.5",
    badge: "高速生成",
    badgeColor: "bg-amber-500/20 text-amber-300 border border-amber-400/30",
    description: "クリエイティブな映像スタイル。高速処理が強み",
    resolutions: ["1920×1080", "1280×720"],
    defaultResolution: "1280×720",
    estimatedTimes: {
      maximum: "4〜6分",
      balanced: "2〜3分",
      preview: "30〜60秒",
    },
    estimatedCosts: {
      maximum: "約 $0.25/シーン",
      balanced: "約 $0.15/シーン",
      preview: "約 $0.06/シーン",
    },
    accentClass: "border-amber-400/40 bg-amber-500/[0.06]",
    accentSelected: "border-amber-400 bg-amber-500/[0.12] ring-1 ring-amber-400/40",
    dotColor: "bg-amber-400",
  },
] as const;

type ProviderId = "runway" | "kling" | "pika";

// ── クオリティプリセット定義 ─────────────────────────────────

const QUALITY_PRESETS = [
  {
    id: "maximum",
    icon: <Star size={16} className="text-yellow-400" />,
    label: "最高品質",
    labelEn: "Maximum Quality",
    description: "最長の生成時間で最高の映像品質。本番公演に最適",
    color: "border-yellow-400/40 bg-yellow-500/[0.06]",
    colorSelected: "border-yellow-400 bg-yellow-500/[0.12] ring-1 ring-yellow-400/40",
    textColor: "text-yellow-300",
    motionDefault: "medium",
  },
  {
    id: "balanced",
    icon: <Zap size={16} className="text-blue-400" />,
    label: "バランス",
    labelEn: "Balanced",
    description: "品質と速度のバランス。通常のリハーサル・確認用",
    color: "border-blue-400/40 bg-blue-500/[0.06]",
    colorSelected: "border-blue-400 bg-blue-500/[0.12] ring-1 ring-blue-400/40",
    textColor: "text-blue-300",
    motionDefault: "medium",
  },
  {
    id: "preview",
    icon: <Video size={16} className="text-slate-400" />,
    label: "プレビュー",
    labelEn: "Preview",
    description: "最速で生成。クイックテスト・内容確認用",
    color: "border-slate-400/30 bg-slate-500/[0.04]",
    colorSelected: "border-slate-400 bg-slate-500/[0.10] ring-1 ring-slate-400/30",
    textColor: "text-slate-300",
    motionDefault: "fast",
  },
] as const;

type QualityPresetId = "maximum" | "balanced" | "preview";

const MOTION_OPTIONS = [
  { value: "slow", label: "スロー" },
  { value: "medium", label: "標準" },
  { value: "fast", label: "ダイナミック" },
];

// ── Props ─────────────────────────────────────────────────────

export interface VideoQualitySettings {
  provider: ProviderId;
  qualityPreset: QualityPresetId;
  resolution: string;
  motionIntensity: string;
  styleConsistency: boolean;
}

interface VideoQualityPanelProps {
  settings: VideoQualitySettings;
  onSettingsChange: (settings: VideoQualitySettings) => void;
  sceneCount: number;
  sceneDurationSeconds?: number;
  compact?: boolean;
}

// ── メインコンポーネント ──────────────────────────────────────

export default function VideoQualityPanel({
  settings,
  onSettingsChange,
  sceneCount,
  sceneDurationSeconds = 120,
  compact = false,
}: VideoQualityPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const selectedProvider = PROVIDERS.find((p) => p.id === settings.provider) ?? PROVIDERS[0];
  const selectedPreset = QUALITY_PRESETS.find((q) => q.id === settings.qualityPreset) ?? QUALITY_PRESETS[0];
  const totalDuration = Math.round((sceneCount * sceneDurationSeconds) / 60);

  function update(partial: Partial<VideoQualitySettings>) {
    onSettingsChange({ ...settings, ...partial });
  }

  return (
    <div className="space-y-5">

      {/* ── ヘッダー ── */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles size={15} className="text-blue-400" />
            動画品質設定
          </h3>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {sceneCount}シーン — 合計約{totalDuration}分の映像
          </p>
        </div>

        {/* クオリティサマリーバッジ */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-medium ${
            settings.qualityPreset === "maximum"
              ? "bg-yellow-500/[0.10] border-yellow-400/30 text-yellow-300"
              : settings.qualityPreset === "balanced"
              ? "bg-blue-500/[0.10] border-blue-400/30 text-blue-300"
              : "bg-slate-500/[0.10] border-slate-400/20 text-slate-400"
          }`}
        >
          {selectedPreset.icon}
          {selectedPreset.label}
        </div>
      </div>

      {/* ── プロバイダー選択 ── */}
      <div>
        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-widest mb-3">
          動画生成プロバイダー
        </p>
        <div className="grid grid-cols-3 gap-2.5">
          {PROVIDERS.map((provider) => {
            const isSelected = settings.provider === provider.id;
            return (
              <button
                key={provider.id}
                onClick={() => update({ provider: provider.id as ProviderId })}
                className={`relative flex flex-col gap-2 p-3.5 rounded-xl border text-left transition-all ${
                  isSelected ? provider.accentSelected : provider.accentClass + " hover:border-opacity-60"
                }`}
              >
                {/* 選択インジケーター */}
                {isSelected && (
                  <div
                    className={`absolute top-2 right-2 w-2 h-2 rounded-full ${provider.dotColor}`}
                    style={{ boxShadow: `0 0 6px currentColor` }}
                  />
                )}

                <div className="space-y-1">
                  <p className="text-xs font-semibold text-white">{provider.name}</p>
                  <span className={`inline-block text-[9px] px-1.5 py-0.5 rounded-full font-medium ${provider.badgeColor}`}>
                    {provider.badge}
                  </span>
                </div>

                {!compact && (
                  <p className="text-[10px] text-slate-500 leading-relaxed">{provider.description}</p>
                )}

                {/* 予想時間 */}
                <div className="flex items-center gap-1 text-[10px] text-slate-600">
                  <Clock size={9} />
                  <span>
                    {provider.estimatedTimes[settings.qualityPreset]}/シーン
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 品質プリセット ── */}
      <div>
        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-widest mb-3">
          品質プリセット
        </p>
        <div className="grid grid-cols-3 gap-2.5">
          {QUALITY_PRESETS.map((preset) => {
            const isSelected = settings.qualityPreset === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => update({ qualityPreset: preset.id as QualityPresetId })}
                className={`flex flex-col gap-2 p-4 rounded-xl border text-left transition-all ${
                  isSelected ? preset.colorSelected : preset.color + " hover:border-opacity-60"
                }`}
              >
                <div className="flex items-center gap-2">
                  {preset.icon}
                  <div>
                    <p className={`text-xs font-semibold ${isSelected ? preset.textColor : "text-slate-300"}`}>
                      {preset.label}
                    </p>
                    <p className="text-[9px] text-slate-600">{preset.labelEn}</p>
                  </div>
                </div>

                {!compact && (
                  <p className="text-[10px] text-slate-500 leading-relaxed">{preset.description}</p>
                )}

                {/* 時間・コスト */}
                <div className="space-y-1 pt-1 border-t border-white/[0.04]">
                  <div className="flex items-center gap-1 text-[10px] text-slate-500">
                    <Clock size={9} />
                    <span>{selectedProvider.estimatedTimes[preset.id]}</span>
                  </div>
                  <div className="text-[10px] text-slate-600">
                    {selectedProvider.estimatedCosts[preset.id]}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 解像度 + 総尺 ── */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.10]">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-2">出力解像度</p>
          <div className="relative">
            <select
              value={settings.resolution}
              onChange={(e) => update({ resolution: e.target.value })}
              className="w-full pl-3 pr-7 py-2 bg-[#132040] border border-blue-400/[0.10] rounded-lg text-sm text-white focus:border-blue-500/40 focus:outline-none appearance-none"
            >
              {selectedProvider.resolutions.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          </div>
          <p className="text-[10px] text-slate-600 mt-1.5">
            {settings.resolution === "1920×1080" ? "フルHD 16:9" : "HD 16:9"}
          </p>
        </div>

        <div className="bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.10]">
          <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-2">合計映像時間</p>
          <p className="text-xl font-bold font-mono text-white">{totalDuration}</p>
          <p className="text-[10px] text-slate-500 mt-1">
            分 ({sceneCount}シーン × {sceneDurationSeconds}秒)
          </p>
        </div>
      </div>

      {/* ── スタイル一貫性 ── */}
      <div className="bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.10]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {settings.styleConsistency ? (
              <Lock size={14} className="text-blue-400" />
            ) : (
              <Unlock size={14} className="text-slate-500" />
            )}
            <div>
              <p className="text-xs font-medium text-slate-200">スタイル一貫性</p>
              <p className="text-[10px] text-slate-500 mt-0.5">
                {settings.styleConsistency
                  ? "全シーンで同一のビジュアルスタイルを維持"
                  : "各シーンが独立したスタイルで生成される"}
              </p>
            </div>
          </div>
          <button
            onClick={() => update({ styleConsistency: !settings.styleConsistency })}
            className={`relative w-10 h-[22px] rounded-full transition-all flex-shrink-0 ${
              settings.styleConsistency ? "bg-blue-600" : "bg-slate-700"
            }`}
            style={{ height: 22, width: 40 }}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${
                settings.styleConsistency ? "translate-x-5" : "translate-x-0.5"
              }`}
              style={{ height: 18, width: 18 }}
            />
          </button>
        </div>
      </div>

      {/* ── 詳細設定 (折りたたみ) ── */}
      <div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ChevronDown
            size={12}
            className={`transition-transform ${showAdvanced ? "" : "-rotate-90"}`}
          />
          詳細設定
          {showAdvanced && (
            <span className="text-[10px] text-blue-400/60 ml-1">
              モーション強度
            </span>
          )}
        </button>

        {showAdvanced && (
          <div className="mt-3 bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.08] space-y-3">
            <div>
              <label className="block text-[10px] text-slate-500 mb-2">モーション強度</label>
              <div className="flex gap-2">
                {MOTION_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => update({ motionIntensity: opt.value })}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                      settings.motionIntensity === opt.value
                        ? "bg-blue-500/[0.15] border-blue-400/30 text-blue-300"
                        : "bg-[#132040] border-blue-400/[0.08] text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-slate-600 mt-1.5">
                映像内の動きの激しさを制御します
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── 推定サマリー ── */}
      <div
        className="rounded-xl p-4 border space-y-2"
        style={{
          background: "linear-gradient(135deg, rgba(59,130,246,0.06) 0%, rgba(99,102,241,0.04) 100%)",
          borderColor: "rgba(59,130,246,0.15)",
        }}
      >
        <div className="flex items-center gap-1.5 mb-3">
          <Info size={11} className="text-blue-400/70" />
          <p className="text-[10px] text-blue-300/70 font-medium uppercase tracking-widest">
            生成サマリー
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] text-slate-500">プロバイダー</p>
            <p className="text-xs text-white font-medium mt-0.5">{selectedProvider.name}</p>
          </div>
          <div>
            <p className="text-[10px] text-slate-500">品質</p>
            <p className={`text-xs font-medium mt-0.5 ${selectedPreset.textColor}`}>
              {selectedPreset.label}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-slate-500">予想時間/シーン</p>
            <p className="text-xs text-white font-medium mt-0.5">
              {selectedProvider.estimatedTimes[settings.qualityPreset]}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-slate-500">推定コスト/シーン</p>
            <p className="text-xs text-white font-medium mt-0.5">
              {selectedProvider.estimatedCosts[settings.qualityPreset]}
            </p>
          </div>
          <div className="col-span-2 pt-1 border-t border-blue-400/[0.08]">
            <p className="text-[10px] text-slate-500">
              全{sceneCount}シーン合計予想時間
            </p>
            <p className="text-sm text-blue-300 font-semibold mt-0.5">
              {sceneCount}シーン
              {settings.qualityPreset === "maximum"
                ? " — 約" + Math.round(sceneCount * 10) + "分"
                : settings.qualityPreset === "balanced"
                ? " — 約" + Math.round(sceneCount * 5) + "分"
                : " — 約" + Math.round(sceneCount * 1.5) + "分"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
