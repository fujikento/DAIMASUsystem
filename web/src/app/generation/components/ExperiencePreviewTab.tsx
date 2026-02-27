"use client";

import { useState, useEffect, useRef } from "react";
import {
  Clock,
  Layers,
  Zap,
  Star,
  Gift,
  Users,
  ChevronRight,
  Info,
} from "lucide-react";

// ── 型定義 ──────────────────────────────────────────────────

interface CourseConfig {
  key: string;
  labelJa: string;
  emoji: string;
  durationMin: number;
  mode: "unified" | "zone" | "custom";
  transition: string;
  brightness: string;
  speed: string;
  preludeSec: number;
  mainSec: number;
  aftertouchSec: number;
  colorNote: string;
  intentNote: string;
  accentColor: string;
}

interface TimelinePhase {
  id: string;
  labelJa: string;
  startMin: number;
  durationMin: number;
  emotion: number;
  zones: (0 | 1 | 2 | 3)[];
  color: string;
  description: string;
}

interface ZoneEventPattern {
  name: string;
  description: string;
  pattern: (0 | 1 | 2 | 3)[][];
}

// ── 定数データ ───────────────────────────────────────────────

const COURSE_CONFIGS: CourseConfig[] = [
  {
    key: "welcome",
    labelJa: "ウェルカム",
    emoji: "✨",
    durationMin: 10,
    mode: "unified",
    transition: "フェードイン（3秒）",
    brightness: "65〜80%",
    speed: "0.5x（穏やか）",
    preludeSec: 20,
    mainSec: 40,
    aftertouchSec: 20,
    colorNote: "テーマカラー基準 / 彩度 +20%",
    intentNote: "初めての没入体験への招待。過度に圧倒せず、徐々に引き込む",
    accentColor: "#3b82f6",
  },
  {
    key: "appetizer",
    labelJa: "前菜",
    emoji: "🥗",
    durationMin: 20,
    mode: "custom",
    transition: "クロスフェード（2秒）",
    brightness: "55〜70%",
    speed: "0.4x（軽やか）",
    preludeSec: 15,
    mainSec: 900,
    aftertouchSec: 60,
    colorNote: "清潔感のある明るい色調 / 輝度 +10%",
    intentNote: "食欲を刺激する軽快な演出。各ゾーンの皿の周囲を個別に装飾",
    accentColor: "#10b981",
  },
  {
    key: "soup",
    labelJa: "スープ",
    emoji: "🍲",
    durationMin: 20,
    mode: "unified",
    transition: "クロスフェード（4秒）",
    brightness: "45〜60%",
    speed: "0.2x（ゆっくり）",
    preludeSec: 10,
    mainSec: 900,
    aftertouchSec: 90,
    colorNote: "温色系（アンバー / ゴールド） / 彩度 -10%",
    intentNote: "リラックスと会話。スープの温かさを空間全体で表現",
    accentColor: "#f59e0b",
  },
  {
    key: "main",
    labelJa: "メイン",
    emoji: "🍖",
    durationMin: 30,
    mode: "custom",
    transition: "カット → フェードイン",
    brightness: "提供前 90% → 食事中 55%",
    speed: "提供前 1.0x → 食事中 0.3x",
    preludeSec: 30,
    mainSec: 1800,
    aftertouchSec: 120,
    colorNote: "テーマ核心色 / コントラスト最大化",
    intentNote: "コースの主役。カットインサートでドラマティックな転換点を演出",
    accentColor: "#ef4444",
  },
  {
    key: "dessert",
    labelJa: "デザート",
    emoji: "🍰",
    durationMin: 25,
    mode: "custom",
    transition: "クロスフェード → フェードブラック",
    brightness: "85〜100% → 15%（余韻）",
    speed: "0.8x → 0.05x（余韻）",
    preludeSec: 45,
    mainSec: 60,
    aftertouchSec: 180,
    colorNote: "テーマ補色 / ゴールド / ホワイトパール",
    intentNote: "体験全体のクライマックス。長い余韻で記憶を刻む",
    accentColor: "#8b5cf6",
  },
];

const TIMELINE_PHASES: TimelinePhase[] = [
  {
    id: "standby",
    labelJa: "待機",
    startMin: 0,
    durationMin: 5,
    emotion: 20,
    zones: [0, 0, 0, 0],
    color: "#1e3a5f",
    description: "環境光のみ。テーマカラーで静かに呼吸",
  },
  {
    id: "arrival",
    labelJa: "着席",
    startMin: 5,
    durationMin: 5,
    emotion: 45,
    zones: [1, 1, 1, 1],
    color: "#1d4ed8",
    description: "輝度が徐々に上昇。ウェルカムパルス発光",
  },
  {
    id: "welcome",
    labelJa: "ウェルカム",
    startMin: 10,
    durationMin: 10,
    emotion: 75,
    zones: [3, 3, 3, 3],
    color: "#2563eb",
    description: "テーマのオープニング。中央から外へ展開",
  },
  {
    id: "appetizer_pre",
    labelJa: "前菜 盛り上げ",
    startMin: 20,
    durationMin: 3,
    emotion: 80,
    zones: [2, 3, 3, 2],
    color: "#059669",
    description: "粒子収束演出。皿の位置へ視線を誘導",
  },
  {
    id: "appetizer",
    labelJa: "前菜",
    startMin: 23,
    durationMin: 17,
    emotion: 60,
    zones: [1, 2, 2, 1],
    color: "#10b981",
    description: "unified + zone強調。食事に集中させる輝度",
  },
  {
    id: "interval1",
    labelJa: "インターバル",
    startMin: 40,
    durationMin: 5,
    emotion: 30,
    zones: [0, 0, 0, 0],
    color: "#1e3a5f",
    description: "フェードブラック → ゆっくりリビール",
  },
  {
    id: "soup_pre",
    labelJa: "スープ 盛り上げ",
    startMin: 45,
    durationMin: 2,
    emotion: 65,
    zones: [2, 2, 2, 2],
    color: "#b45309",
    description: "温かみのある収束演出",
  },
  {
    id: "soup",
    labelJa: "スープ",
    startMin: 47,
    durationMin: 18,
    emotion: 45,
    zones: [1, 1, 1, 1],
    color: "#f59e0b",
    description: "unified 低輝度。会話を妨げない演出",
  },
  {
    id: "interval2",
    labelJa: "インターバル",
    startMin: 65,
    durationMin: 5,
    emotion: 25,
    zones: [0, 0, 0, 0],
    color: "#1e3a5f",
    description: "メインへの静寂。期待感の醸成",
  },
  {
    id: "main_pre",
    labelJa: "メイン 盛り上げ",
    startMin: 70,
    durationMin: 3,
    emotion: 95,
    zones: [3, 3, 3, 3],
    color: "#b91c1c",
    description: "最大の盛り上がり。カット演出",
  },
  {
    id: "main",
    labelJa: "メイン",
    startMin: 73,
    durationMin: 27,
    emotion: 55,
    zones: [2, 2, 2, 2],
    color: "#ef4444",
    description: "custom モード。食事中は落ち着いた輝度",
  },
  {
    id: "interval3",
    labelJa: "インターバル",
    startMin: 100,
    durationMin: 5,
    emotion: 30,
    zones: [0, 0, 0, 0],
    color: "#1e3a5f",
    description: "最後のリセット。デザートへの準備",
  },
  {
    id: "dessert_pre",
    labelJa: "デザート 盛り上げ",
    startMin: 105,
    durationMin: 5,
    emotion: 90,
    zones: [3, 3, 3, 3],
    color: "#6d28d9",
    description: "クライマックスへの45秒前奏",
  },
  {
    id: "dessert",
    labelJa: "デザート クライマックス",
    startMin: 110,
    durationMin: 10,
    emotion: 100,
    zones: [3, 3, 3, 3],
    color: "#8b5cf6",
    description: "最大輝度。テーマが完全展開",
  },
  {
    id: "afterglow",
    labelJa: "余韻",
    startMin: 120,
    durationMin: 15,
    emotion: 25,
    zones: [1, 1, 1, 1],
    color: "#4c1d95",
    description: "ゆっくりフェードアウト。記憶への刻印",
  },
];

const ZONE_PATTERNS: ZoneEventPattern[] = [
  {
    name: "Wave Forward",
    description: "Zone1 から Zone4 へ波が流れる",
    pattern: [
      [3, 0, 0, 0],
      [2, 3, 0, 0],
      [1, 2, 3, 0],
      [0, 1, 2, 3],
      [0, 0, 1, 2],
      [0, 0, 0, 1],
    ],
  },
  {
    name: "Convergence",
    description: "両端から中央へ収束（料理提供前奏）",
    pattern: [
      [3, 0, 0, 3],
      [2, 3, 3, 2],
      [1, 2, 2, 1],
      [0, 3, 3, 0],
      [0, 2, 2, 0],
      [0, 3, 3, 0],
    ],
  },
  {
    name: "Alternating",
    description: "奇数偶数ゾーンが交互点滅（祝祭演出）",
    pattern: [
      [3, 0, 3, 0],
      [0, 3, 0, 3],
      [3, 0, 3, 0],
      [0, 3, 0, 3],
      [3, 0, 3, 0],
      [0, 3, 0, 3],
    ],
  },
  {
    name: "Birthday Burst",
    description: "Zone2 に集中してから全体に拡散",
    pattern: [
      [0, 3, 0, 0],
      [0, 3, 3, 0],
      [1, 3, 3, 1],
      [2, 3, 3, 2],
      [3, 3, 3, 3],
      [2, 2, 2, 2],
    ],
  },
];

// ── ユーティリティ ───────────────────────────────────────────

const TOTAL_MINUTES = 135;

function getEmotionColor(emotion: number): string {
  if (emotion >= 90) return "#8b5cf6";
  if (emotion >= 70) return "#3b82f6";
  if (emotion >= 50) return "#10b981";
  if (emotion >= 30) return "#f59e0b";
  return "#1e3a5f";
}

function formatMin(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}分`;
  return `${h}時間${m > 0 ? m + "分" : ""}`;
}

function getModeLabel(mode: string): string {
  if (mode === "unified") return "統一";
  if (mode === "zone") return "区画";
  return "カスタム";
}

function getModeColor(mode: string): string {
  if (mode === "unified") return "bg-blue-500/10 text-blue-400 border-blue-500/20";
  if (mode === "zone") return "bg-purple-500/10 text-purple-400 border-purple-500/20";
  return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
}

const ZONE_LEVEL_OPACITY: Record<number, string> = {
  0: "bg-slate-800/40",
  1: "bg-blue-500/20",
  2: "bg-blue-500/50",
  3: "bg-blue-400/90",
};

// ── サブコンポーネント ────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-4">
      {children}
    </p>
  );
}

function Pill({
  children,
  colorClass,
}: {
  children: React.ReactNode;
  colorClass: string;
}) {
  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${colorClass}`}
    >
      {children}
    </span>
  );
}

// ── タイムライン可視化 ────────────────────────────────────────

function GuestTimeline() {
  const [hoveredPhase, setHoveredPhase] = useState<string | null>(null);

  const hovered = TIMELINE_PHASES.find((p) => p.id === hoveredPhase);

  return (
    <div className="space-y-4">
      <SectionTitle>ゲスト体験タイムライン（約2時間）</SectionTitle>

      {/* 感情カーブ */}
      <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10] overflow-hidden">
        <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-3">
          感情カーブ
        </p>
        <div className="relative h-16">
          {/* グリッドライン */}
          {[25, 50, 75, 100].map((v) => (
            <div
              key={v}
              className="absolute inset-x-0 border-t border-blue-400/[0.05]"
              style={{ bottom: `${v}%` }}
            />
          ))}

          {/* フェーズバー */}
          <div className="absolute inset-0 flex items-end gap-px">
            {TIMELINE_PHASES.map((phase) => {
              const widthPct = (phase.durationMin / TOTAL_MINUTES) * 100;
              const heightPct = phase.emotion;
              const isHovered = hoveredPhase === phase.id;
              return (
                <div
                  key={phase.id}
                  className="relative flex-shrink-0 h-full flex items-end cursor-pointer group"
                  style={{ width: `${widthPct}%` }}
                  onMouseEnter={() => setHoveredPhase(phase.id)}
                  onMouseLeave={() => setHoveredPhase(null)}
                >
                  <div
                    className="w-full rounded-t-sm transition-all duration-200"
                    style={{
                      height: `${heightPct}%`,
                      backgroundColor: isHovered
                        ? phase.color
                        : phase.color + "99",
                      minHeight: 2,
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* 時間軸ラベル */}
        <div className="relative flex mt-1">
          {TIMELINE_PHASES.map((phase) => {
            const widthPct = (phase.durationMin / TOTAL_MINUTES) * 100;
            return (
              <div
                key={phase.id}
                className="flex-shrink-0 overflow-hidden"
                style={{ width: `${widthPct}%` }}
              >
                {phase.id === "welcome" ||
                phase.id === "main" ||
                phase.id === "dessert" ? (
                  <span className="text-[8px] text-slate-600 truncate block">
                    {phase.startMin}m
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      {/* ホバー詳細 */}
      <div className="h-12 flex items-center">
        {hovered ? (
          <div className="flex items-center gap-3 px-4 py-2.5 bg-[#080f1a] rounded-xl border border-blue-400/[0.10] w-full">
            <div
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: hovered.color }}
            />
            <span className="text-sm font-medium text-white">
              {hovered.labelJa}
            </span>
            <span className="text-xs text-slate-400">{hovered.description}</span>
            <span className="text-xs text-slate-500 ml-auto">
              感情強度 {hovered.emotion}%
            </span>
          </div>
        ) : (
          <p className="text-xs text-slate-600 pl-2">
            バーにカーソルを合わせると詳細が表示されます
          </p>
        )}
      </div>

      {/* 4ゾーン × 時間軸グリッド */}
      <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10]">
        <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-3">
          4ゾーン活性化マップ（横軸=時間 / 縦軸=Zone）
        </p>
        <div className="space-y-1.5">
          {[4, 3, 2, 1].map((zoneNum) => (
            <div key={zoneNum} className="flex items-center gap-2">
              <span className="text-[9px] text-slate-600 font-mono w-10 flex-shrink-0 text-right">
                Zone {zoneNum}
              </span>
              <div className="flex-1 flex h-6 gap-px">
                {TIMELINE_PHASES.map((phase) => {
                  const widthPct = (phase.durationMin / TOTAL_MINUTES) * 100;
                  const level = phase.zones[zoneNum - 1] ?? 0;
                  const isHovered = hoveredPhase === phase.id;
                  return (
                    <div
                      key={phase.id}
                      className={`h-full rounded-sm transition-all duration-150 cursor-pointer ${ZONE_LEVEL_OPACITY[level]} ${
                        isHovered ? "ring-1 ring-white/20" : ""
                      }`}
                      style={{ width: `${widthPct}%`, minWidth: 2 }}
                      onMouseEnter={() => setHoveredPhase(phase.id)}
                      onMouseLeave={() => setHoveredPhase(null)}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* 凡例 */}
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-blue-400/[0.06]">
          <span className="text-[9px] text-slate-600">輝度レベル:</span>
          {[
            { level: 0, label: "オフ" },
            { level: 1, label: "低" },
            { level: 2, label: "中" },
            { level: 3, label: "高" },
          ].map(({ level, label }) => (
            <div key={level} className="flex items-center gap-1">
              <div
                className={`w-4 h-3 rounded-sm ${ZONE_LEVEL_OPACITY[level]}`}
              />
              <span className="text-[9px] text-slate-500">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── コース別演出パネル ────────────────────────────────────────

function CoursePatternsPanel() {
  const [selectedCourse, setSelectedCourse] = useState<string>("welcome");

  const course = COURSE_CONFIGS.find((c) => c.key === selectedCourse)!;
  const totalSec = course.preludeSec + course.mainSec + course.aftertouchSec;

  return (
    <div className="space-y-4">
      <SectionTitle>コース別演出パターン</SectionTitle>

      {/* コースセレクター */}
      <div className="flex gap-2 flex-wrap">
        {COURSE_CONFIGS.map((c) => (
          <button
            key={c.key}
            onClick={() => setSelectedCourse(c.key)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium border transition-all ${
              selectedCourse === c.key
                ? "text-white border-opacity-50"
                : "bg-[#080f1a] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/[0.20]"
            }`}
            style={
              selectedCourse === c.key
                ? {
                    backgroundColor: c.accentColor + "22",
                    borderColor: c.accentColor + "60",
                    color: c.accentColor,
                  }
                : {}
            }
          >
            <span>{c.emoji}</span>
            <span>{c.labelJa}</span>
          </button>
        ))}
      </div>

      {/* 詳細パネル */}
      <div className="grid grid-cols-2 gap-4">
        {/* 左: 設定値 */}
        <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10] space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{course.emoji}</span>
            <span className="font-semibold text-white">{course.labelJa}</span>
            <Pill colorClass={getModeColor(course.mode)}>
              {getModeLabel(course.mode)}
            </Pill>
          </div>

          <div className="space-y-2.5">
            {[
              { label: "トランジション", value: course.transition },
              { label: "輝度", value: course.brightness },
              { label: "速度", value: course.speed },
              { label: "色調", value: course.colorNote },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="flex justify-between items-start gap-3 py-2 border-b border-blue-400/[0.06]"
              >
                <span className="text-xs text-slate-500 flex-shrink-0">
                  {label}
                </span>
                <span className="text-xs text-slate-300 text-right">
                  {value}
                </span>
              </div>
            ))}
          </div>

          <div className="pt-1 flex items-start gap-2 p-3 bg-blue-400/[0.04] rounded-lg border border-blue-400/[0.08]">
            <Info size={12} className="text-blue-400/60 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-slate-400 leading-relaxed">
              {course.intentNote}
            </p>
          </div>
        </div>

        {/* 右: 演出時間配分 */}
        <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10] space-y-3">
          <p className="text-[10px] text-slate-600 uppercase tracking-widest">
            演出時間配分（合計 {totalSec >= 60 ? formatMin(Math.round(totalSec / 60)) : `${totalSec}秒`}）
          </p>

          {/* 時間配分バー */}
          <div className="flex h-8 rounded-lg overflow-hidden gap-0.5">
            {[
              {
                label: "前奏",
                sec: course.preludeSec,
                color: course.accentColor + "60",
              },
              {
                label: "メイン",
                sec: course.mainSec,
                color: course.accentColor + "cc",
              },
              {
                label: "余韻",
                sec: course.aftertouchSec,
                color: course.accentColor + "40",
              },
            ].map(({ label, sec, color }) => {
              const pct = (sec / totalSec) * 100;
              return (
                <div
                  key={label}
                  className="h-full flex items-center justify-center text-[9px] font-medium text-white/80 rounded-sm min-w-0"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: color,
                    minWidth: pct > 5 ? "auto" : 0,
                  }}
                  title={`${label}: ${sec}秒`}
                >
                  {pct > 12 ? label : ""}
                </div>
              );
            })}
          </div>

          {/* 凡例 */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "前奏", sec: course.preludeSec, key: "prelude" },
              { label: "メイン", sec: course.mainSec, key: "main" },
              { label: "余韻", sec: course.aftertouchSec, key: "after" },
            ].map(({ label, sec }) => (
              <div
                key={label}
                className="text-center py-2 bg-[#0e1d32] rounded-lg border border-blue-400/[0.08]"
              >
                <p className="text-[9px] text-slate-500">{label}</p>
                <p className="text-sm font-bold font-mono text-white mt-0.5">
                  {sec >= 60
                    ? `${Math.floor(sec / 60)}m`
                    : `${sec}s`}
                </p>
              </div>
            ))}
          </div>

          {/* ゾーン投影プレビュー（ミニ） */}
          <div>
            <p className="text-[9px] text-slate-600 uppercase tracking-widest mb-2">
              ゾーン投影イメージ
            </p>
            <div className="flex gap-1 h-10">
              {[1, 2, 3, 4].map((z) => {
                const isHighlight =
                  course.mode === "zone"
                    ? z === 2
                    : course.mode === "custom"
                    ? true
                    : true;
                return (
                  <div
                    key={z}
                    className="flex-1 rounded-md flex items-center justify-center text-[9px] font-mono transition-all"
                    style={{
                      backgroundColor: isHighlight
                        ? course.accentColor + (course.mode === "zone" && z !== 2 ? "15" : "30")
                        : "#0e1d32",
                      border: `1px solid ${course.accentColor}${
                        isHighlight ? "40" : "10"
                      }`,
                      color: course.accentColor + "cc",
                    }}
                  >
                    Z{z}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── マルチゾーン協調演出 ──────────────────────────────────────

function MultiZonePanel() {
  const [activePattern, setActivePattern] = useState(0);
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pattern = ZONE_PATTERNS[activePattern];
  const currentStep = tick % pattern.pattern.length;
  const currentFrame = pattern.pattern[currentStep];

  // インターバルを playing 状態に連動させる
  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setTick((t) => t + 1);
      }, 500);
    } else {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing]);

  const handlePlayToggle = () => {
    setPlaying((prev) => !prev);
  };

  return (
    <div className="space-y-4">
      <SectionTitle>マルチゾーン協調演出パターン</SectionTitle>

      {/* パターンセレクター */}
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {ZONE_PATTERNS.map((p, i) => (
          <button
            key={i}
            onClick={() => {
              setActivePattern(i);
              setTick(0);
              setPlaying(false);
            }}
            className={`px-3 py-2.5 rounded-xl text-xs font-medium border text-left transition-all ${
              activePattern === i
                ? "bg-blue-500/10 border-blue-500/20 text-blue-400"
                : "bg-[#080f1a] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/[0.20]"
            }`}
          >
            <p className="font-semibold mb-0.5">{p.name}</p>
            <p className="text-[9px] text-slate-500 leading-relaxed">
              {p.description}
            </p>
          </button>
        ))}
      </div>

      {/* アニメーション可視化 */}
      <div className="bg-[#080f1a] rounded-xl p-5 border border-blue-400/[0.10]">
        <div className="flex items-center justify-between mb-4">
          <p className="text-[10px] text-slate-600 uppercase tracking-widest">
            {pattern.name}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setTick((t) => Math.max(0, t - 1))}
              className="px-2 py-1 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-xs transition-colors"
            >
              前へ
            </button>
            <button
              onClick={() => setTick((t) => t + 1)}
              className="px-2 py-1 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-xs transition-colors"
            >
              次へ
            </button>
            <span className="text-[9px] text-slate-600 font-mono">
              Step {currentStep + 1}/{pattern.pattern.length}
            </span>
          </div>
        </div>

        {/* ゾーン表示 */}
        <div className="flex gap-3 h-20">
          {[0, 1, 2, 3].map((zIdx) => {
            const level = currentFrame[zIdx] as 0 | 1 | 2 | 3;
            const opacities: Record<number, number> = { 0: 0.05, 1: 0.2, 2: 0.5, 3: 1 };
            const opacity = opacities[level];
            return (
              <div
                key={zIdx}
                className="flex-1 rounded-xl flex flex-col items-center justify-center gap-1 transition-all duration-500"
                style={{
                  backgroundColor: `rgba(59, 130, 246, ${opacity * 0.25})`,
                  border: `1px solid rgba(59, 130, 246, ${opacity * 0.6})`,
                  boxShadow:
                    level >= 3
                      ? "0 0 20px rgba(59, 130, 246, 0.3)"
                      : "none",
                }}
              >
                <span
                  className="text-xs font-medium font-mono transition-all duration-500"
                  style={{
                    color: `rgba(147, 197, 253, ${Math.max(0.3, opacity)})`,
                  }}
                >
                  Z{zIdx + 1}
                </span>
                <span
                  className="text-[9px] font-mono transition-all duration-500"
                  style={{
                    color: `rgba(147, 197, 253, ${Math.max(0.2, opacity * 0.8)})`,
                  }}
                >
                  Lv.{level}
                </span>
              </div>
            );
          })}
        </div>

        {/* ステップドット */}
        <div className="flex items-center justify-center gap-1.5 mt-4">
          {pattern.pattern.map((_, i) => (
            <button
              key={i}
              onClick={() => setTick(i)}
              className="w-1.5 h-1.5 rounded-full transition-all"
              style={{
                backgroundColor:
                  i === currentStep
                    ? "rgba(59, 130, 246, 0.9)"
                    : "rgba(59, 130, 246, 0.2)",
              }}
            />
          ))}
        </div>
      </div>

      {/* 切り替えタイミング早見表 */}
      <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10]">
        <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-3">
          unified vs zone 切り替えタイミング
        </p>
        <div className="space-y-1">
          {[
            { phase: "待機・インターバル", mode: "unified", reason: "統一感・リセット感" },
            { phase: "ウェルカム演出", mode: "unified → zone展開", reason: "インパクト後の細部演出" },
            { phase: "前菜提供", mode: "custom", reason: "全体の雰囲気 + 個別の皿" },
            { phase: "スープ提供", mode: "unified", reason: "温かさの統一表現" },
            { phase: "メイン提供前奏", mode: "zone → unified", reason: "緊張感から解放" },
            { phase: "デザート", mode: "zone → unified → zone", reason: "個から全への展開" },
            { phase: "特別イベント", mode: "zone → unified拡散", reason: "集中から共有へ" },
          ].map(({ phase, mode, reason }) => (
            <div
              key={phase}
              className="flex items-center gap-3 py-2 border-b border-blue-400/[0.05] last:border-0"
            >
              <span className="text-xs text-slate-400 w-36 flex-shrink-0">
                {phase}
              </span>
              <span className="text-xs font-medium text-blue-400 w-44 flex-shrink-0">
                {mode}
              </span>
              <span className="text-xs text-slate-500">{reason}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 特別イベント演出 ──────────────────────────────────────────

function SpecialEventsPanel() {
  const [activeEvent, setActiveEvent] = useState<"birthday" | "seasonal" | "vip">(
    "birthday"
  );

  const events = [
    { id: "birthday" as const, label: "バースデー", icon: <Gift size={14} /> },
    { id: "seasonal" as const, label: "季節イベント", icon: <Star size={14} /> },
    { id: "vip" as const, label: "VIPゲスト", icon: <Users size={14} /> },
  ];

  return (
    <div className="space-y-4">
      <SectionTitle>特別イベント演出</SectionTitle>

      {/* タブ */}
      <div className="flex gap-1.5">
        {events.map((e) => (
          <button
            key={e.id}
            onClick={() => setActiveEvent(e.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium border transition-all ${
              activeEvent === e.id
                ? "bg-blue-500/10 border-blue-500/20 text-blue-400"
                : "bg-[#080f1a] border-blue-400/[0.10] text-slate-400 hover:text-white"
            }`}
          >
            {e.icon}
            {e.label}
          </button>
        ))}
      </div>

      {/* バースデー */}
      {activeEvent === "birthday" && (
        <div className="space-y-3">
          <div className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10]">
            <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-4">
              バースデーサプライズ 演出フロー
            </p>
            <div className="space-y-2">
              {[
                {
                  time: "スタッフ操作",
                  label: "バースデーモード選択 / 対象ゾーン指定",
                  color: "#3b82f6",
                },
                {
                  time: "1分前",
                  label: "全テーブルを低輝度に落とす",
                  color: "#1d4ed8",
                },
                {
                  time: "30秒前",
                  label: "対象ゾーン以外をフェードブラック",
                  color: "#1e3a5f",
                },
                {
                  time: "0秒",
                  label: "対象ゾーンに光の爆発 + AIキャラクター登場",
                  color: "#8b5cf6",
                },
                {
                  time: "+10秒",
                  label: "全ゾーンに拡散（Wave Forward）",
                  color: "#7c3aed",
                },
                {
                  time: "+30秒",
                  label: "全体統一でお祝いループ（60秒）",
                  color: "#6d28d9",
                },
                {
                  time: "+90秒",
                  label: "通常コース演出に戻る（クロスフェード8秒）",
                  color: "#3b82f6",
                },
              ].map(({ time, label, color }, i, arr) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="flex flex-col items-center flex-shrink-0">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-bold text-white"
                      style={{ backgroundColor: color }}
                    >
                      {i + 1}
                    </div>
                    {i < arr.length - 1 && (
                      <div className="w-px flex-1 bg-blue-400/[0.15] mt-1" style={{ minHeight: 12 }} />
                    )}
                  </div>
                  <div className="pb-3">
                    <span className="text-[9px] text-slate-500 font-mono">
                      {time}
                    </span>
                    <p className="text-xs text-slate-300 mt-0.5">{label}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 季節イベント */}
      {activeEvent === "seasonal" && (
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              name: "クリスマス",
              period: "12/1〜12/25",
              emoji: "🎄",
              color: "#dc2626",
              details: [
                "雪の結晶オーバーレイ",
                "+赤 / +ゴールド 色調シフト",
                "雪が舞う カーテン効果（コース切替時）",
                "鐘の音タイミングで輝度フラッシュ",
              ],
            },
            {
              name: "バレンタイン",
              period: "2/1〜2/14",
              emoji: "💝",
              color: "#db2777",
              details: [
                "ハートの軌跡 波状演出",
                "+ローズ / +マゼンタ 色調シフト",
                "Zone1→2→3→4 の順に波連続",
                "デザート: 全面ピンク/レッド 最大輝度",
              ],
            },
            {
              name: "ハロウィン",
              period: "10/15〜10/31",
              emoji: "🎃",
              color: "#ea580c",
              details: [
                "シルエット アニメーション重ね",
                "+オレンジ / +パープル 色調シフト",
                "コントラスト +30%",
                "ランダム雷フラッシュ効果",
              ],
            },
          ].map(({ name, period, emoji, color, details }) => (
            <div
              key={name}
              className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10]"
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">{emoji}</span>
                <div>
                  <p className="text-sm font-medium text-white">{name}</p>
                  <p className="text-[9px] text-slate-500">{period}</p>
                </div>
              </div>
              <ul className="space-y-1.5">
                {details.map((d) => (
                  <li key={d} className="flex items-start gap-1.5">
                    <ChevronRight
                      size={10}
                      className="flex-shrink-0 mt-0.5"
                      style={{ color }}
                    />
                    <span className="text-[10px] text-slate-400">{d}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* VIP */}
      {activeEvent === "vip" && (
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              title: "専用ウェルカム演出",
              icon: <Star size={16} />,
              description:
                "通常より長い120秒のオープニング。より精緻なアニメーションでテーマを展開",
              color: "#f59e0b",
            },
            {
              title: "個人名プロジェクション",
              icon: <Zap size={16} />,
              description:
                "デザートコース時にゲストの名前（漢字 / ローマ字）を光で描く演出",
              color: "#8b5cf6",
            },
            {
              title: "カスタムカラー",
              icon: <Layers size={16} />,
              description:
                "ゲストの好みやブランドカラーに合わせた色調調整。全コースに反映",
              color: "#10b981",
            },
            {
              title: "記念撮影モード",
              icon: <Clock size={16} />,
              description:
                "静的で美しい光のパターンを保持し、ゲストの撮影に最適な構図を維持",
              color: "#3b82f6",
            },
          ].map(({ title, icon, description, color }) => (
            <div
              key={title}
              className="bg-[#080f1a] rounded-xl p-4 border border-blue-400/[0.10] flex gap-3"
            >
              <div
                className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: color + "22", color }}
              >
                {icon}
              </div>
              <div>
                <p className="text-sm font-medium text-white mb-1">{title}</p>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {description}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── メインコンポーネント ──────────────────────────────────────

type SubTabId = "timeline" | "courses" | "multizone" | "events";

export default function ExperiencePreviewTab() {
  const [activeSubTab, setActiveSubTab] = useState<SubTabId>("timeline");

  const subTabs: { id: SubTabId; label: string; icon: React.ReactNode }[] = [
    { id: "timeline", label: "体験タイムライン", icon: <Clock size={14} /> },
    {
      id: "courses",
      label: "コース別演出",
      icon: <Layers size={14} />,
    },
    {
      id: "multizone",
      label: "マルチゾーン",
      icon: <Zap size={14} />,
    },
    {
      id: "events",
      label: "特別イベント",
      icon: <Star size={14} />,
    },
  ];

  return (
    <div className="space-y-5">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">体験プレビュー</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            ゲスト体験の演出フローとゾーン設定を視覚的に確認
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-400/[0.06] rounded-xl border border-blue-400/[0.10]">
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
          <span className="text-[10px] text-blue-400/80">
            4ゾーン / 8席 / 5コース
          </span>
        </div>
      </div>

      {/* サブタブ */}
      <div className="flex gap-1 bg-[#080f1a] rounded-xl p-1 border border-blue-400/[0.10]">
        {subTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-colors flex-1 justify-center ${
              activeSubTab === tab.id
                ? "bg-blue-500/10 text-blue-400"
                : "text-slate-500 hover:text-slate-300 hover:bg-blue-400/[0.05]"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* タブコンテンツ */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10]">
        {activeSubTab === "timeline" && <GuestTimeline />}
        {activeSubTab === "courses" && <CoursePatternsPanel />}
        {activeSubTab === "multizone" && <MultiZonePanel />}
        {activeSubTab === "events" && <SpecialEventsPanel />}
      </div>
    </div>
  );
}
