"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  BookOpen,
  FileText,
  Image,
  Video,
  ArrowRight,
  Check,
  RefreshCw,
  Trash2,
  Plus,
  Edit3,
  ChevronDown,
  ChevronRight,
  Clock,
  Sparkles,
  Loader2,
  ArrowUp,
  ArrowDown,
  X,
} from "lucide-react";
import {
  fetchStoryboards,
  fetchStoryboard,
  createStoryboard,
  deleteStoryboard,
  updateStoryboard,
  updateScene,
  addScene,
  deleteScene,
  reorderScenes,
  generateStoryboardImages,
  regenerateSceneImage,
  approveStoryboardImages,
  generateStoryboardVideos,
  regenerateSceneVideo,
  fetchGenerationStatus,
  fetchScenesStatus,
  subscribeToStoryboardEvents,
  generateScript,
  type GenerationThemes,
  type StoryboardData,
  type StoryboardListItem,
  type StoryboardScene,
  type GenerationStatus,
} from "@/lib/api";
import { DAY_THEMES } from "@/lib/themes";
import VideoQualityPanel, { type VideoQualitySettings } from "./VideoQualityPanel";

// ── 定数 ───────────────────────────────────────────────────────

const COURSE_LABELS: Record<string, string> = {
  welcome: "ウェルカム",
  appetizer: "前菜",
  soup: "スープ",
  main: "メイン",
  dessert: "デザート",
  custom: "カスタム",
};

const COURSE_KEYS = [
  { value: "welcome", label: "ウェルカム" },
  { value: "appetizer", label: "前菜" },
  { value: "soup", label: "スープ" },
  { value: "main", label: "メイン" },
  { value: "dessert", label: "デザート" },
  { value: "custom", label: "カスタム" },
];

const TRANSITION_OPTIONS = [
  { value: "crossfade", label: "クロスフェード" },
  { value: "cut", label: "カット" },
  { value: "fade_black", label: "フェードブラック" },
  { value: "fade_white", label: "フェードホワイト" },
];

const COLOR_TONE_OPTIONS = [
  { value: "neutral", label: "ニュートラル" },
  { value: "warm", label: "ウォーム" },
  { value: "cool", label: "クール" },
  { value: "vivid", label: "ビビッド" },
];

const BRIGHTNESS_OPTIONS = [
  { value: "normal", label: "標準" },
  { value: "dark", label: "暗め" },
  { value: "bright", label: "明るめ" },
];

const ANIMATION_SPEED_OPTIONS = [
  { value: "normal", label: "標準" },
  { value: "slow", label: "スロー" },
  { value: "fast", label: "ファスト" },
];

const MOOD_OPTIONS = [
  { value: "", label: "未設定" },
  { value: "calm", label: "穏やか" },
  { value: "dramatic", label: "ドラマチック" },
  { value: "mysterious", label: "ミステリアス" },
  { value: "joyful", label: "楽しい" },
  { value: "romantic", label: "ロマンチック" },
  { value: "energetic", label: "エネルギッシュ" },
  { value: "serene", label: "静寂" },
  { value: "festive", label: "華やか" },
];

const CAMERA_ANGLE_OPTIONS = [
  { value: "", label: "未設定" },
  { value: "bird_eye", label: "鳥瞰（真上から）" },
  { value: "wide", label: "ワイドショット" },
  { value: "close_up", label: "クローズアップ" },
  { value: "medium", label: "ミディアムショット" },
  { value: "pan", label: "パノラマ" },
  { value: "dynamic", label: "ダイナミック" },
];

const THEME_OPTIONS = [
  { value: "", label: "未設定" },
  { value: "zen", label: "禅" },
  { value: "fire", label: "炎" },
  { value: "ocean", label: "海" },
  { value: "forest", label: "森" },
  { value: "gold", label: "黄金" },
  { value: "space", label: "宇宙" },
  { value: "fairytale", label: "童話" },
];

const SORT_ORDER_LABELS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"];

const STATUS_CONFIGS: Record<
  string,
  { label: string; className: string }
> = {
  draft: { label: "下書き", className: "bg-slate-500/20 text-slate-400" },
  script_ready: { label: "台本完成", className: "bg-blue-500/20 text-blue-300" },
  images_generating: { label: "画像生成中", className: "bg-amber-500/20 text-amber-300" },
  images_ready: { label: "画像完成", className: "bg-amber-500/20 text-amber-300" },
  video_generating: { label: "動画生成中", className: "bg-purple-500/20 text-purple-300" },
  video_ready: { label: "動画完成", className: "bg-emerald-500/20 text-emerald-300" },
  pending: { label: "待機中", className: "bg-slate-500/20 text-slate-400" },
  generating: { label: "生成中", className: "bg-amber-500/20 text-amber-300" },
  ready: { label: "完了", className: "bg-emerald-500/20 text-emerald-300" },
  complete: { label: "完了", className: "bg-emerald-500/20 text-emerald-300" },
  failed: { label: "失敗", className: "bg-red-500/20 text-red-300" },
};

type Step = 1 | 2 | 3;

interface StoryboardWorkflowTabProps {
  themes: GenerationThemes | null;
}

// ── ステータスバッジ ──────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIGS[status] ?? {
    label: status,
    className: "bg-slate-500/20 text-slate-400",
  };
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}

// ── ステップインジケーター ────────────────────────────────────

function StepIndicator({ currentStep }: { currentStep: Step }) {
  const steps = [
    { id: 1 as Step, label: "① 台本作成", icon: <FileText size={14} />, desc: "シーン・演出設定" },
    { id: 2 as Step, label: "② 画像確認", icon: <Image size={14} />, desc: "AI画像を生成・承認" },
    { id: 3 as Step, label: "③ 動画生成", icon: <Video size={14} />, desc: "映像ファイルを生成" },
  ];

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, index) => {
        const isCompleted = currentStep > step.id;
        const isCurrent = currentStep === step.id;
        const isFuture = currentStep < step.id;

        return (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-medium transition-all ${
                isCurrent
                  ? "bg-blue-500/[0.15] border-blue-400/30 text-blue-300"
                  : isCompleted
                  ? "bg-emerald-500/[0.10] border-emerald-400/20 text-emerald-400"
                  : "bg-transparent border-transparent text-slate-600"
              }`}
            >
              <span
                className={`flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold flex-shrink-0 ${
                  isCurrent
                    ? "bg-blue-400 text-[#080f1a]"
                    : isCompleted
                    ? "bg-emerald-400 text-[#080f1a]"
                    : "bg-slate-700 text-slate-500"
                }`}
              >
                {isCompleted ? <Check size={10} /> : step.id}
              </span>
              <div className="hidden sm:block">
                <div>{step.label}</div>
                <div className={`text-[10px] ${isCurrent ? "text-blue-400/60" : isCompleted ? "text-emerald-400/60" : "text-slate-700"}`}>
                  {step.desc}
                </div>
              </div>
              <span className="sm:hidden">{step.icon}</span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`w-8 h-px mx-1 flex-shrink-0 ${
                  currentStep > step.id ? "bg-emerald-400/30" : "bg-slate-700"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── 左サイドバー ─────────────────────────────────────────────

function StoryboardSidebar({
  storyboards,
  selectedId,
  onSelect,
  onDelete,
  onNewCreate,
  loading,
}: {
  storyboards: StoryboardListItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onNewCreate: () => void;
  loading: boolean;
}) {
  return (
    <div
      className="flex flex-col border-r border-blue-400/[0.10]"
      style={{ width: 240, flexShrink: 0 }}
    >
      <div className="px-4 py-3 border-b border-blue-400/[0.10]">
        <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
          <BookOpen size={12} className="text-blue-400/70" />
          保存済み台本
        </p>
      </div>

      <div className="flex-1 overflow-y-auto py-2 space-y-1 px-2">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={16} className="animate-spin text-slate-500" />
          </div>
        ) : storyboards.length === 0 ? (
          <div className="py-8 text-center px-3">
            <BookOpen size={24} className="mx-auto text-slate-700 mb-2" />
            <p className="text-xs text-slate-500 mb-1">台本がありません</p>
            <p className="text-[10px] text-slate-600">「新規作成」で今夜の台本を作成しましょう</p>
          </div>
        ) : (
          storyboards.map((sb) => {
            const isSelected = selectedId === sb.id;
            const dayTheme = sb.day_of_week ? DAY_THEMES[sb.day_of_week] : undefined;
            return (
              <div
                key={sb.id}
                className={`relative group rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? "bg-blue-500/[0.15] border-blue-400/30"
                    : "bg-transparent border-transparent hover:bg-blue-400/[0.05] hover:border-blue-400/[0.08]"
                }`}
                onClick={() => onSelect(sb.id)}
              >
                <div className="px-3 py-2.5">
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-xs font-medium text-slate-200 leading-tight truncate flex-1 pr-1">
                      {sb.title || `台本 #${sb.id}`}
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(sb.id);
                      }}
                      className="opacity-30 group-hover:opacity-100 p-1 text-slate-500 hover:text-red-400 transition-all flex-shrink-0 rounded"
                      title="台本を削除"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1.5">
                    {dayTheme && (
                      <span className="text-[10px]">{dayTheme.icon}</span>
                    )}
                    <StatusBadge status={sb.status} />
                  </div>
                  <p className="text-[10px] text-slate-600 mt-1">
                    {new Date(sb.created_at).toLocaleDateString("ja-JP", {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="p-3 border-t border-blue-400/[0.10]">
        <button
          onClick={onNewCreate}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-xs transition-colors"
        >
          <Plus size={13} />
          新規作成
        </button>
      </div>
    </div>
  );
}

// ── Step 1: 絵コンテエディター ───────────────────────────────

// Inline dropdown helper
function SelectField({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <span className="text-[10px] text-slate-500 whitespace-nowrap flex-shrink-0">{label}</span>
      <div className="relative min-w-0">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="pl-2 pr-6 py-1 bg-[#132040] border border-blue-400/[0.10] rounded-lg text-[11px] text-slate-200 focus:border-blue-500/40 focus:outline-none appearance-none cursor-pointer disabled:opacity-50 max-w-[140px]"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown size={9} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
      </div>
    </div>
  );
}

// Scene card thumbnail: shows image preview if ready, otherwise a placeholder
function SceneThumbnail({
  scene,
  apiBase,
}: {
  scene: StoryboardScene;
  apiBase: string;
}) {
  const hasImage = (scene.image_status === "ready" || scene.image_status === "complete") && scene.image_path;
  return (
    <div
      className="flex-shrink-0 rounded-lg overflow-hidden bg-[#080f1a] border border-blue-400/[0.10] flex items-center justify-center"
      style={{ width: 120, height: 26, aspectRatio: "46/10" }}
      title={hasImage ? "生成済み画像" : "未生成"}
    >
      {hasImage ? (
        <img
          src={`${apiBase}${scene.image_path}`}
          alt="scene preview"
          className="w-full h-full object-cover"
        />
      ) : scene.image_status === "generating" ? (
        <Loader2 size={10} className="animate-spin text-blue-400" />
      ) : (
        <div className="flex flex-col items-center gap-0.5">
          <Image size={10} className="text-slate-700" />
        </div>
      )}
    </div>
  );
}

function ScriptCreationStep({
  storyboard,
  onStoryboardUpdate,
  onNext,
  imageProvider,
  onImageProviderChange,
}: {
  storyboard: StoryboardData | null;
  onStoryboardUpdate: (sb: StoryboardData) => void;
  onNext: () => void;
  imageProvider: string;
  onImageProviderChange: (provider: string) => void;
}) {
  const [provider, setProvider] = useState("runway");
  const [savingProvider, setSavingProvider] = useState(false);

  // 絵コンテ state
  const [localScenes, setLocalScenes] = useState<StoryboardScene[]>([]);
  const [savingFields, setSavingFields] = useState<Record<number, string>>({});
  const [draftDurations, setDraftDurations] = useState<Record<number, string>>({});
  const [addingScene, setAddingScene] = useState(false);
  const [deletingSceneIds, setDeletingSceneIds] = useState<Set<number>>(new Set());
  const [reorderingId, setReorderingId] = useState<number | null>(null);
  const [expandedOptionalIds, setExpandedOptionalIds] = useState<Set<number>>(new Set());
  const [expandedPromptIds, setExpandedPromptIds] = useState<Set<number>>(new Set());
  const [editingSceneId, setEditingSceneId] = useState<number | null>(null);
  const [editPrompt, setEditPrompt] = useState("");
  const [savingSceneId, setSavingSceneId] = useState<number | null>(null);

  // AI script generation
  const [concept, setConcept] = useState("");
  const [generatingScript, setGeneratingScript] = useState(false);
  // NEW: script generation mode
  const [scriptMode, setScriptMode] = useState<"full_course" | "per_dish">("full_course");
  const [dishes, setDishes] = useState<{ name: string; concept: string }[]>([
    { name: "", concept: "" },
  ]);

  // Title editing
  const [editingTitle, setEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [savingTitle, setSavingTitle] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (storyboard) {
      setLocalScenes(storyboard.scenes);
      setDraftDurations({});
      setProvider(storyboard.provider ?? "runway");
    }
  }, [storyboard]);

  function toggleOptional(sceneId: number) {
    setExpandedOptionalIds((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) next.delete(sceneId);
      else next.add(sceneId);
      return next;
    });
  }

  function togglePromptExpand(sceneId: number) {
    setExpandedPromptIds((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) next.delete(sceneId);
      else next.add(sceneId);
      return next;
    });
  }

  async function saveSceneField(
    scene: StoryboardScene,
    field: string,
    value: string | number | null
  ) {
    if (!storyboard) return;
    setSavingFields((prev) => ({ ...prev, [scene.id]: field }));
    try {
      const payload = { [field]: value } as Parameters<typeof updateScene>[2];
      const updated = await updateScene(storyboard.id, scene.id, payload);
      setLocalScenes((prev) => prev.map((s) => (s.id === scene.id ? updated : s)));
    } catch (e) {
      console.error("Save scene field failed:", e);
    }
    setSavingFields((prev) => {
      const next = { ...prev };
      delete next[scene.id];
      return next;
    });
  }

  async function saveDuration(scene: StoryboardScene) {
    if (!storyboard) return;
    const raw = draftDurations[scene.id];
    if (raw === undefined) return;
    const parsed = parseInt(raw, 10);
    if (isNaN(parsed) || parsed <= 0) return;
    setSavingFields((prev) => ({ ...prev, [scene.id]: "duration_seconds" }));
    try {
      const updated = await updateScene(storyboard.id, scene.id, { duration_seconds: parsed });
      setLocalScenes((prev) => prev.map((s) => (s.id === scene.id ? updated : s)));
      setDraftDurations((prev) => {
        const next = { ...prev };
        delete next[scene.id];
        return next;
      });
    } catch (e) {
      console.error("Save duration failed:", e);
    }
    setSavingFields((prev) => {
      const next = { ...prev };
      delete next[scene.id];
      return next;
    });
  }

  async function handleDeleteScene(scene: StoryboardScene) {
    if (!storyboard) return;
    const sceneName = scene.scene_title || scene.scene_description_ja || `シーン ${scene.sort_order + 1}`;
    if (!confirm(`「${sceneName}」を削除しますか？\nこの操作は元に戻せません。`)) return;
    setDeletingSceneIds((prev) => new Set(prev).add(scene.id));
    try {
      const updated = await deleteScene(storyboard.id, scene.id);
      onStoryboardUpdate(updated);
      setLocalScenes(updated.scenes);
    } catch (e) {
      console.error("Delete scene failed:", e);
      alert("シーンの削除に失敗しました。もう一度お試しください。");
    }
    setDeletingSceneIds((prev) => {
      const next = new Set(prev);
      next.delete(scene.id);
      return next;
    });
  }

  async function handleMoveScene(scene: StoryboardScene, direction: "up" | "down") {
    if (!storyboard) return;
    const idx = localScenes.findIndex((s) => s.id === scene.id);
    if (direction === "up" && idx === 0) return;
    if (direction === "down" && idx === localScenes.length - 1) return;
    const newScenes = [...localScenes];
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    [newScenes[idx], newScenes[swapIdx]] = [newScenes[swapIdx], newScenes[idx]];
    setLocalScenes(newScenes);
    setReorderingId(scene.id);
    try {
      const updated = await reorderScenes(storyboard.id, newScenes.map((s) => s.id));
      onStoryboardUpdate(updated);
      setLocalScenes(updated.scenes);
    } catch (e) {
      console.error("Reorder scenes failed:", e);
    }
    setReorderingId(null);
  }

  async function handleAddScene() {
    if (!storyboard) return;
    setAddingScene(true);
    try {
      const updated = await addScene(storyboard.id, {
        course_key: "custom",
        duration_seconds: 120,
        transition: "crossfade",
        projection_mode: "unified",
        color_tone: "neutral",
        brightness: "normal",
        animation_speed: "normal",
      });
      onStoryboardUpdate(updated);
      setLocalScenes(updated.scenes);
    } catch (e) {
      console.error("Add scene failed:", e);
    }
    setAddingScene(false);
  }

  async function saveTitle() {
    if (!storyboard || !draftTitle.trim()) return;
    setSavingTitle(true);
    try {
      const updated = await updateStoryboard(storyboard.id, { title: draftTitle.trim() });
      onStoryboardUpdate(updated);
    } catch (e) {
      console.error("Save title failed:", e);
    }
    setSavingTitle(false);
    setEditingTitle(false);
  }

  function startEditPrompt(scene: StoryboardScene) {
    setEditingSceneId(scene.id);
    setEditPrompt(scene.prompt_edited ?? scene.prompt);
    setExpandedPromptIds((prev) => new Set(prev).add(scene.id));
  }

  async function saveEditPrompt(scene: StoryboardScene) {
    if (!storyboard) return;
    setSavingSceneId(scene.id);
    try {
      const updated = await updateScene(storyboard.id, scene.id, { prompt_edited: editPrompt });
      setLocalScenes((prev) => prev.map((s) => (s.id === scene.id ? updated : s)));
      setEditingSceneId(null);
      setEditPrompt("");
    } catch (e) {
      console.error("Save prompt failed:", e);
    }
    setSavingSceneId(null);
  }

  async function handleGenerateScript() {
    if (!storyboard) return;
    if (scriptMode === "full_course" && !concept.trim()) return;
    if (scriptMode === "per_dish" && dishes.every(d => !d.name.trim() && !d.concept.trim())) return;

    setGeneratingScript(true);
    try {
      const params = scriptMode === "full_course"
        ? { concept: concept.trim(), mode: "full_course" as const }
        : { mode: "per_dish" as const, dishes: dishes.filter(d => d.name.trim() || d.concept.trim()) };

      const updated = await generateScript(storyboard.id, params);
      onStoryboardUpdate(updated);
      setLocalScenes(updated.scenes);
      setConcept("");
      setDishes([{ name: "", concept: "" }]);
    } catch (e) {
      console.error("Script generation failed:", e);
      alert("台本の生成に失敗しました。Gemini APIキーが設定されているか確認してください。");
    }
    setGeneratingScript(false);
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}秒`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}分${String(s).padStart(2, "0")}秒`;
  }

  // ── 空状態 ──────────────────────────────────────────────────
  if (!storyboard) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-500/[0.10] border border-blue-400/20">
            <Sparkles size={20} className="text-blue-400" />
          </div>
          <p className="text-sm font-medium text-slate-300">台本を選択または新規作成してください</p>
          <p className="text-xs text-slate-500">左サイドバーの「新規作成」で空の台本を作成し、シーンを自由に追加できます</p>
        </div>
      </div>
    );
  }

  // ── 絵コンテ編集ビュー ────────────────────────────────────
  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-4">

      {/* ── 台本タイトル + ヘッダーバー ─────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* タイトル */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {editingTitle ? (
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <input
                type="text"
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveTitle();
                  if (e.key === "Escape") { setEditingTitle(false); }
                }}
                autoFocus
                className="flex-1 min-w-0 px-3 py-1.5 bg-[#132040] border border-blue-500/40 rounded-xl text-sm text-slate-100 font-semibold focus:outline-none"
              />
              <button
                onClick={saveTitle}
                disabled={savingTitle || !draftTitle.trim()}
                className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-40"
              >
                {savingTitle ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                保存
              </button>
              <button
                onClick={() => setEditingTitle(false)}
                className="px-3 py-1.5 bg-slate-700/40 hover:bg-slate-700/60 text-slate-300 rounded-lg text-xs transition-colors"
              >
                キャンセル
              </button>
            </div>
          ) : (
            <button
              onClick={() => { setDraftTitle(storyboard.title); setEditingTitle(true); }}
              className="group flex items-center gap-2 min-w-0"
              title="タイトルを編集"
            >
              <span className="text-base font-semibold text-slate-100 truncate">
                {storyboard.title}
              </span>
              <Edit3 size={12} className="text-slate-600 group-hover:text-blue-400 flex-shrink-0 transition-colors" />
            </button>
          )}
          <StatusBadge status={storyboard.status} />
        </div>

        <div className="flex-1" />

        {/* プロバイダー */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500">動画:</span>
          <div className="relative">
            <select
              value={provider}
              onChange={async (e) => {
                const newProvider = e.target.value;
                setProvider(newProvider);
                setSavingProvider(true);
                try {
                  const updated = await updateStoryboard(storyboard.id, { provider: newProvider });
                  onStoryboardUpdate(updated);
                } catch (err) {
                  console.error("Update provider failed:", err);
                }
                setSavingProvider(false);
              }}
              className="pl-2.5 pr-6 py-1.5 bg-[#132040] border border-blue-400/[0.10] rounded-xl text-[11px] text-slate-100 focus:border-blue-500/40 focus:outline-none appearance-none cursor-pointer"
            >
              <option value="runway">Runway Gen-4.5</option>
              <option value="kling">Kling 2.6</option>
              <option value="pika">Pika 2.5</option>
            </select>
            <ChevronDown size={9} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          </div>
          {savingProvider && <Loader2 size={11} className="animate-spin text-blue-400" />}
        </div>
      </div>

      {/* ── シーン追加ボタン ─────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleAddScene}
          disabled={addingScene}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-xs transition-all disabled:opacity-40"
        >
          {addingScene ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          新しいシーンを追加
        </button>
        <span className="text-[11px] text-slate-600">
          {localScenes.length > 0
            ? `${localScenes.length}シーン — 各カードで映像の内容・雰囲気を設定してください`
            : "シーンを追加して絵コンテを作成してください"}
        </span>
      </div>

      {/* ── AIで台本を自動生成 ───────────────────────────────── */}
      {storyboard && (
        <div className="bg-[#132040] border border-blue-400/[0.10] rounded-xl p-4 space-y-3">
          <div className="text-xs text-slate-400 font-medium">AIで台本を自動生成</div>

          {/* Mode tabs */}
          <div className="flex gap-1 bg-[#0e1d32] rounded-lg p-1">
            <button
              onClick={() => setScriptMode("full_course")}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                scriptMode === "full_course"
                  ? "bg-blue-600/30 text-blue-300 border border-blue-500/20"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              コース全体
            </button>
            <button
              onClick={() => setScriptMode("per_dish")}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                scriptMode === "per_dish"
                  ? "bg-blue-600/30 text-blue-300 border border-blue-500/20"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              料理ごと
            </button>
          </div>

          {/* Full course mode */}
          {scriptMode === "full_course" && (
            <div className="flex gap-2">
              <input
                type="text"
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
                placeholder="コンセプトを入力... (例: 千と千尋の神隠し風、海底の冒険...)"
                disabled={generatingScript}
                className="flex-1 px-3 py-2 bg-[#0e1d32] border border-blue-400/[0.10] rounded-lg text-sm text-white placeholder-slate-600 focus:border-blue-500/40 focus:outline-none disabled:opacity-40"
                onKeyDown={(e) => e.key === "Enter" && handleGenerateScript()}
              />
              <button
                onClick={handleGenerateScript}
                disabled={!concept.trim() || generatingScript || !storyboard}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-500 hover:to-blue-400 text-white font-medium rounded-lg text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {generatingScript ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {generatingScript ? "生成中..." : "AIで台本を生成"}
              </button>
            </div>
          )}

          {/* Per dish mode */}
          {scriptMode === "per_dish" && (
            <div className="space-y-2">
              {dishes.map((dish, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <span className="text-xs text-slate-500 w-8 text-right flex-shrink-0">{idx + 1}.</span>
                  <input
                    type="text"
                    value={dish.name}
                    onChange={(e) => {
                      const next = [...dishes];
                      next[idx] = { ...next[idx], name: e.target.value };
                      setDishes(next);
                    }}
                    placeholder="料理名 (例: 前菜)"
                    disabled={generatingScript}
                    className="w-28 px-2 py-1.5 bg-[#0e1d32] border border-blue-400/[0.10] rounded-lg text-xs text-white placeholder-slate-600 focus:border-blue-500/40 focus:outline-none disabled:opacity-40"
                  />
                  <input
                    type="text"
                    value={dish.concept}
                    onChange={(e) => {
                      const next = [...dishes];
                      next[idx] = { ...next[idx], concept: e.target.value };
                      setDishes(next);
                    }}
                    placeholder="テーマ/コンセプト (例: 千と千尋の神隠し風)"
                    disabled={generatingScript}
                    className="flex-1 px-2 py-1.5 bg-[#0e1d32] border border-blue-400/[0.10] rounded-lg text-xs text-white placeholder-slate-600 focus:border-blue-500/40 focus:outline-none disabled:opacity-40"
                  />
                  {dishes.length > 1 && (
                    <button
                      onClick={() => setDishes(dishes.filter((_, i) => i !== idx))}
                      disabled={generatingScript}
                      className="text-slate-600 hover:text-red-400 transition-colors disabled:opacity-40"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              ))}
              <div className="flex gap-2">
                <button
                  onClick={() => setDishes([...dishes, { name: "", concept: "" }])}
                  disabled={generatingScript}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/15 rounded-lg transition-all disabled:opacity-40"
                >
                  <Plus size={12} /> 料理を追加
                </button>
                <div className="flex-1" />
                <button
                  onClick={handleGenerateScript}
                  disabled={dishes.every(d => !d.name.trim() && !d.concept.trim()) || generatingScript || !storyboard}
                  className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-500 hover:to-blue-400 text-white font-medium rounded-lg text-xs transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {generatingScript ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                  {generatingScript ? "生成中..." : "AIで台本を生成"}
                </button>
              </div>
            </div>
          )}

          {generatingScript && (
            <div className="text-xs text-amber-300 flex items-center gap-1.5">
              <Loader2 size={11} className="animate-spin" />
              AIがシーンを考えています...
            </div>
          )}
        </div>
      )}

      {/* ── 絵コンテカード一覧 ────────────────────────────────── */}
      <div className="space-y-4">
        {localScenes.map((scene, idx) => {
          const isDeleting = deletingSceneIds.has(scene.id);
          const isReordering = reorderingId === scene.id;
          const savingField = savingFields[scene.id];
          const isOptionalExpanded = expandedOptionalIds.has(scene.id);
          const isPromptExpanded = expandedPromptIds.has(scene.id);
          const isEditingPrompt = editingSceneId === scene.id;
          const isSavingPrompt = savingSceneId === scene.id;

          const draftDuration = draftDurations[scene.id];
          const displaySeconds =
            draftDuration !== undefined
              ? parseInt(draftDuration, 10) || scene.duration_seconds
              : scene.duration_seconds;
          const isDurationDirty =
            draftDuration !== undefined &&
            parseInt(draftDuration, 10) !== scene.duration_seconds;

          const ordLabel = SORT_ORDER_LABELS[idx] ?? `${idx + 1}`;

          return (
            <div
              key={scene.id}
              className={`bg-[#0a1628] rounded-2xl border border-blue-400/[0.12] overflow-hidden transition-opacity ${
                isDeleting ? "opacity-30 pointer-events-none" : ""
              }`}
            >
              {/* ── カードヘッダー: シーン番号 + タイトル + コントロール ── */}
              <div className="flex items-center gap-2 px-4 py-2.5 bg-[#0e1d32]/80 border-b border-blue-400/[0.08]">
                <span className="text-blue-400 font-bold text-xs flex-shrink-0 w-4">{ordLabel}</span>

                {/* シーン名 (インライン編集) */}
                <input
                  type="text"
                  defaultValue={scene.scene_title ?? ""}
                  placeholder="シーン名 (例: 海底の楽園)"
                  onBlur={(e) => {
                    const val = e.target.value.trim();
                    const current = scene.scene_title ?? "";
                    if (val !== current) saveSceneField(scene, "scene_title", val || null);
                  }}
                  onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                  className="flex-1 min-w-0 bg-transparent text-sm font-semibold text-slate-100 placeholder-slate-700 focus:outline-none focus:text-white"
                />

                {/* 保存中インジケーター */}
                {(savingField || isReordering) && (
                  <Loader2 size={11} className="animate-spin text-blue-400 flex-shrink-0" />
                )}

                {/* 上下移動 */}
                <div className="flex items-center gap-0 flex-shrink-0">
                  <button
                    onClick={() => handleMoveScene(scene, "up")}
                    disabled={idx === 0 || !!isReordering}
                    className="p-1 text-slate-700 hover:text-slate-300 disabled:opacity-20 transition-colors"
                    title="上へ"
                  >
                    <ArrowUp size={12} />
                  </button>
                  <button
                    onClick={() => handleMoveScene(scene, "down")}
                    disabled={idx === localScenes.length - 1 || !!isReordering}
                    className="p-1 text-slate-700 hover:text-slate-300 disabled:opacity-20 transition-colors"
                    title="下へ"
                  >
                    <ArrowDown size={12} />
                  </button>
                </div>

                {/* 削除 */}
                <button
                  onClick={() => handleDeleteScene(scene)}
                  disabled={isDeleting}
                  className="p-1 text-slate-700 hover:text-red-400 transition-colors flex-shrink-0"
                  title="削除"
                >
                  <X size={13} />
                </button>
              </div>

              {/* ── カードボディ: サムネイル + フィールド ── */}
              <div className="flex gap-0">
                {/* 左: サムネイル + アスペクト比コンテナ */}
                <div className="flex flex-col items-center justify-start gap-2 px-3 pt-3 pb-3 border-r border-blue-400/[0.06] flex-shrink-0" style={{ width: 144 }}>
                  <SceneThumbnail scene={scene} apiBase={API_BASE} />
                  <div className="w-full">
                    <div className="flex items-center gap-1 text-[10px] text-slate-500 mb-1">
                      <Clock size={9} />
                      <span>時間</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        min={1}
                        value={draftDuration !== undefined ? draftDuration : scene.duration_seconds}
                        onChange={(e) =>
                          setDraftDurations((prev) => ({ ...prev, [scene.id]: e.target.value }))
                        }
                        onBlur={() => { if (isDurationDirty) saveDuration(scene); }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && isDurationDirty) saveDuration(scene);
                          if (e.key === "Escape") {
                            setDraftDurations((prev) => { const n = { ...prev }; delete n[scene.id]; return n; });
                          }
                        }}
                        className="w-14 px-2 py-1 bg-[#132040] border border-blue-400/[0.10] rounded-lg text-xs text-white text-center focus:border-blue-500/40 focus:outline-none"
                      />
                      <span className="text-[10px] text-slate-500">秒</span>
                      {isDurationDirty && (
                        savingField === "duration_seconds"
                          ? <Loader2 size={9} className="animate-spin text-blue-400" />
                          : <button onClick={() => saveDuration(scene)} className="text-[9px] px-1.5 py-0.5 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors">
                              保存
                            </button>
                      )}
                    </div>
                    <span className="text-[9px] text-slate-600">({formatDuration(displaySeconds)})</span>
                  </div>
                </div>

                {/* 右: メインフィールド */}
                <div className="flex-1 min-w-0 p-3 space-y-2.5">

                  {/* ビジュアル説明 */}
                  <div>
                    <label className="text-[10px] text-slate-500 mb-1 block">ビジュアル説明</label>
                    <textarea
                      defaultValue={scene.scene_description_ja ?? ""}
                      placeholder="どんな映像を投影したいか、詳しく描写してください... (例: 透明な海底に色とりどりのサンゴが広がり、熱帯魚が優雅に泳ぐ。中央に大きな真珠貝が光を放ち...)"
                      rows={3}
                      onBlur={(e) => {
                        const val = e.target.value.trim();
                        const current = scene.scene_description_ja ?? "";
                        if (val !== current) saveSceneField(scene, "scene_description_ja", val || null);
                      }}
                      className="w-full px-2.5 py-2 bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl text-xs text-slate-200 placeholder-slate-700 focus:border-blue-500/40 focus:outline-none resize-none leading-relaxed"
                    />
                  </div>

                  {/* ムード + カメラアングル + 色調 + トランジション — 1行 */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <SelectField
                      label="ムード"
                      value={scene.mood ?? ""}
                      options={MOOD_OPTIONS}
                      onChange={(v) => saveSceneField(scene, "mood", v || null)}
                      disabled={!!savingField}
                    />
                    <SelectField
                      label="アングル"
                      value={scene.camera_angle ?? ""}
                      options={CAMERA_ANGLE_OPTIONS}
                      onChange={(v) => saveSceneField(scene, "camera_angle", v || null)}
                      disabled={!!savingField}
                    />
                    <SelectField
                      label="色調"
                      value={scene.color_tone ?? "neutral"}
                      options={COLOR_TONE_OPTIONS}
                      onChange={(v) => saveSceneField(scene, "color_tone", v)}
                      disabled={!!savingField}
                    />
                    <SelectField
                      label="転換"
                      value={scene.transition ?? "crossfade"}
                      options={TRANSITION_OPTIONS}
                      onChange={(v) => saveSceneField(scene, "transition", v)}
                      disabled={!!savingField}
                    />
                  </div>

                  {/* AIプロンプトヒント */}
                  <div>
                    <label className="text-[10px] text-slate-500 mb-1 block">
                      AIプロンプトヒント
                      <span className="ml-1 text-slate-700">(英語キーワード — 任意)</span>
                    </label>
                    <input
                      type="text"
                      defaultValue={scene.prompt_modifier ?? ""}
                      placeholder="例: sakura petals, golden sparkles, flowing water..."
                      onBlur={(e) => {
                        const val = e.target.value.trim();
                        const current = scene.prompt_modifier ?? "";
                        if (val !== current) saveSceneField(scene, "prompt_modifier", val || null);
                      }}
                      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                      className="w-full px-2.5 py-1.5 bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl text-xs text-slate-200 placeholder-slate-700 focus:border-blue-500/40 focus:outline-none"
                    />
                  </div>

                  {/* ── オプションフィールド（折りたたみ） ── */}
                  <div className="border-t border-blue-400/[0.06] pt-2">
                    <button
                      onClick={() => toggleOptional(scene.id)}
                      className="flex items-center gap-1.5 text-[10px] text-slate-600 hover:text-slate-400 transition-colors"
                    >
                      {isOptionalExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      <span>オプション設定</span>
                      {!isOptionalExpanded && (scene.course_dish_id || scene.mood || scene.camera_angle) && (
                        <span className="text-blue-400/50 ml-1">設定済み</span>
                      )}
                    </button>

                    {isOptionalExpanded && (
                      <div className="mt-2.5 space-y-2.5 pl-3">
                        {/* 料理連動 */}
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-500 w-16 flex-shrink-0">料理コース</span>
                          <div className="relative">
                            <select
                              value={scene.course_key ?? "custom"}
                              onChange={(e) => saveSceneField(scene, "course_key", e.target.value)}
                              disabled={!!savingField}
                              className="pl-2 pr-6 py-1 bg-[#132040] border border-blue-400/[0.10] rounded-lg text-[11px] text-slate-200 focus:border-blue-500/40 focus:outline-none appearance-none disabled:opacity-50"
                            >
                              {COURSE_KEYS.map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                              ))}
                            </select>
                            <ChevronDown size={9} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                          </div>
                          <span className="text-[10px] text-slate-700">（任意）</span>
                        </div>

                        {/* 投影モード */}
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-500 w-16 flex-shrink-0">投影範囲</span>
                          <div className="flex items-center gap-1">
                            {[
                              { value: "unified", label: "全体" },
                              { value: "zone", label: "ゾーン" },
                              { value: "custom", label: "指定" },
                              { value: "seat", label: "個席" },
                            ].map((opt) => (
                              <button
                                key={opt.value}
                                onClick={() => saveSceneField(scene, "projection_mode", opt.value)}
                                className={`px-2 py-0.5 rounded-lg border text-[10px] font-medium transition-all ${
                                  (scene.projection_mode ?? "unified") === opt.value
                                    ? "bg-blue-500/[0.15] border-blue-400/30 text-blue-300"
                                    : "bg-[#132040] border-blue-400/[0.10] text-slate-500 hover:text-slate-300"
                                }`}
                              >
                                {opt.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* ゾーン指定 */}
                        {scene.projection_mode === "custom" && (
                          <div className="flex items-center gap-2 pl-18">
                            {["1", "2", "3", "4"].map((z) => {
                              const zones = scene.target_zones ? scene.target_zones.split(",").map((s) => s.trim()) : [];
                              return (
                                <label key={z} className="flex items-center gap-1 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={zones.includes(z)}
                                    onChange={(e) => {
                                      const next = e.target.checked
                                        ? [...zones, z].sort()
                                        : zones.filter((tz) => tz !== z);
                                      saveSceneField(scene, "target_zones", next.length > 0 ? next.join(",") : null);
                                    }}
                                    className="accent-blue-500"
                                  />
                                  <span className="text-[10px] text-slate-500">Z{z}</span>
                                </label>
                              );
                            })}
                          </div>
                        )}

                        {/* 明るさ + 速度 */}
                        <div className="flex items-center gap-4">
                          <SelectField
                            label="明るさ"
                            value={scene.brightness ?? "normal"}
                            options={BRIGHTNESS_OPTIONS}
                            onChange={(v) => saveSceneField(scene, "brightness", v)}
                            disabled={!!savingField}
                          />
                          <SelectField
                            label="速度"
                            value={scene.animation_speed ?? "normal"}
                            options={ANIMATION_SPEED_OPTIONS}
                            onChange={(v) => saveSceneField(scene, "animation_speed", v)}
                            disabled={!!savingField}
                          />
                        </div>

                        {/* 生成プロンプト（折りたたみ） */}
                        <div className="border-t border-blue-400/[0.06] pt-2">
                          <button
                            onClick={() => togglePromptExpand(scene.id)}
                            className="flex items-center gap-1 text-[10px] text-slate-700 hover:text-slate-400 transition-colors"
                          >
                            {isPromptExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                            生成プロンプト
                            {scene.prompt_edited && (
                              <span className="text-[9px] text-blue-400/60 ml-1">(編集済)</span>
                            )}
                          </button>

                          {isPromptExpanded && (
                            <div className="mt-2">
                              {!isEditingPrompt ? (
                                <>
                                  <div className="bg-[#080f1a] rounded-lg p-2.5 font-mono text-[10px] text-slate-500 leading-relaxed border border-blue-400/[0.06] whitespace-pre-wrap">
                                    {scene.prompt_edited ?? scene.prompt}
                                  </div>
                                  <button
                                    onClick={() => startEditPrompt(scene)}
                                    className="mt-1.5 flex items-center gap-1 text-[10px] text-slate-600 hover:text-blue-300 transition-colors"
                                  >
                                    <Edit3 size={9} />
                                    プロンプトを編集
                                  </button>
                                </>
                              ) : (
                                <div className="space-y-2">
                                  <textarea
                                    value={editPrompt}
                                    onChange={(e) => setEditPrompt(e.target.value)}
                                    rows={4}
                                    className="w-full px-2.5 py-2 bg-[#132040] border border-blue-400/[0.10] rounded-xl text-[10px] text-slate-200 font-mono leading-relaxed focus:border-blue-500/40 focus:outline-none resize-none"
                                  />
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => saveEditPrompt(scene)}
                                      disabled={isSavingPrompt}
                                      className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-medium transition-colors disabled:opacity-40"
                                    >
                                      {isSavingPrompt ? <Loader2 size={9} className="animate-spin" /> : <Check size={9} />}
                                      保存
                                    </button>
                                    <button
                                      onClick={() => { setEditingSceneId(null); setEditPrompt(""); }}
                                      className="px-2.5 py-1 bg-slate-700/40 hover:bg-slate-700/60 text-slate-300 rounded-lg text-[10px] transition-colors"
                                    >
                                      キャンセル
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* シーンが0件の場合のガイド */}
      {localScenes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center space-y-4 border border-dashed border-blue-400/[0.10] rounded-2xl">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-500/[0.06] border border-blue-400/[0.10]">
            <FileText size={24} className="text-slate-700" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-400">シーンがまだありません</p>
            <p className="text-xs text-slate-600 mt-1">「新しいシーンを追加」から映像シーンを作成してください</p>
            <p className="text-xs text-slate-700 mt-1">テーマや料理の設定は不要です — 自由に絵コンテを描きましょう</p>
          </div>
          <button
            onClick={handleAddScene}
            disabled={addingScene}
            className="flex items-center gap-1.5 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-all disabled:opacity-40"
          >
            {addingScene ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            最初のシーンを追加
          </button>
        </div>
      )}

      {/* 次のステップへ */}
      {localScenes.length > 0 && (
        <div className="pt-2 flex items-center justify-between border-t border-blue-400/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-500">画像プロバイダー:</span>
            <div className="relative">
              <select
                value={imageProvider}
                onChange={(e) => onImageProviderChange(e.target.value)}
                className="pl-2.5 pr-6 py-1.5 text-[11px] bg-[#0e1d32] border border-blue-400/[0.10] rounded-lg text-slate-300 focus:outline-none focus:border-blue-400/30 appearance-none"
              >
                <option value="gemini">Gemini Flash (標準)</option>
                <option value="gemini_pro">Gemini Pro (高品質)</option>
                <option value="imagen">Imagen 4 Fast (最速)</option>
              </select>
              <ChevronDown size={9} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            </div>
          </div>
          <button
            onClick={onNext}
            className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-medium rounded-xl text-sm transition-all"
            style={{ boxShadow: "0 0 20px rgba(59,130,246,0.25)" }}
          >
            画像生成へ進む
            <ArrowRight size={15} />
          </button>
        </div>
      )}
    </div>
  );
}

// ── 時間フォーマットユーティリティ ───────────────────────────

function formatRemainingTime(seconds: number): string {
  if (seconds < 60) {
    return `約${Math.round(seconds)}秒`;
  }
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (s === 0) return `約${m}分`;
  return `約${m}分${s}秒`;
}

function formatElapsedTime(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}秒`;
  }
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (s === 0) return `${m}分`;
  return `${m}分${s}秒`;
}

// ── Step 2: 画像プレビュー ────────────────────────────────────

function ImagePreviewStep({
  storyboard,
  onStoryboardUpdate,
  onNext,
  imageProvider,
  onImageProviderChange,
}: {
  storyboard: StoryboardData;
  onStoryboardUpdate: (sb: StoryboardData) => void;
  onNext: () => void;
  imageProvider: string;
  onImageProviderChange: (provider: string) => void;
}) {
  const [generatingAll, setGeneratingAll] = useState(false);
  const [regeneratingIds, setRegeneratingIds] = useState<Set<number>>(new Set());
  const [approving, setApproving] = useState(false);
  const [genStatus, setGenStatus] = useState<GenerationStatus | null>(null);
  const [selectedSceneIdx, setSelectedSceneIdx] = useState<number | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const scenes = storyboard.scenes;
  const allReady = scenes.length > 0 && scenes.every((s) => s.image_status === "ready" || s.image_status === "complete");
  // Whether there are any scenes that "Generate All" can actually process
  const hasGenerableScenes = scenes.some((s) => s.image_status === "pending" || s.image_status === "failed");

  // Auto-select the first ready scene when none is selected
  useEffect(() => {
    if (selectedSceneIdx !== null) return;
    const firstReadyIdx = scenes.findIndex(
      (s) => (s.image_status === "ready" || s.image_status === "complete") && s.image_path
    );
    if (firstReadyIdx !== -1) {
      setSelectedSceneIdx(firstReadyIdx);
    }
  }, [scenes, selectedSceneIdx]);

  // Reset on mount, cleanup on unmount
  useEffect(() => {
    abortRef.current = false;
    return () => { abortRef.current = true; };
  }, []);

  // ポーリング: storyboard直接更新（サイドバー再取得なし）で軽量・高速に
  const storyboardIdRef = useRef(storyboard.id);
  storyboardIdRef.current = storyboard.id;
  const storyboardRef = useRef(storyboard);
  storyboardRef.current = storyboard;
  const onUpdateRef = useRef(onStoryboardUpdate);
  onUpdateRef.current = onStoryboardUpdate;

  async function pollUntilDone() {
    console.log(`pollUntilDone START id=${storyboardIdRef.current}`);
    let prevJobStatus: string | null = null;
    let consecutiveFailures = 0;
    const MAX_CONSECUTIVE_FAILURES = 5;

    for (let i = 0; i < 180; i++) {
      if (abortRef.current) { console.log("Poll aborted (pre-sleep)"); break; }
      await new Promise((r) => setTimeout(r, 1000));
      if (abortRef.current) { console.log("Poll aborted (post-sleep)"); break; }
      try {
        const [scenesStatus, jobStatus] = await Promise.all([
          fetchScenesStatus(storyboardIdRef.current),
          fetchGenerationStatus(storyboardIdRef.current),
        ]);

        consecutiveFailures = 0;

        const scenesSummary = scenesStatus?.scenes?.map((s: { id: number; image_status: string }) => `${s.id}:${s.image_status}`).join(", ");
        console.log(`Poll#${i} scenes=[${scenesSummary}] job=${jobStatus?.status} prev=${prevJobStatus}`);

        if (scenesStatus?.scenes) {
          onUpdateRef.current({
            ...storyboardRef.current,
            scenes: storyboardRef.current.scenes.map((scene) => {
              const updated = scenesStatus.scenes.find((s) => s.id === scene.id);
              if (updated) {
                return {
                  ...scene,
                  image_status: updated.image_status,
                  image_path: updated.image_path,
                };
              }
              return scene;
            }),
          });
        }

        setGenStatus(jobStatus);

        const allDone = scenesStatus?.scenes?.every(
          (s) => s.image_status === "complete" || s.image_status === "ready" || s.image_status === "failed"
        );

        const currentJobStatus = jobStatus?.status ?? "idle";
        const jobJustBecameIdle = prevJobStatus === "generating" && currentJobStatus === "idle";
        prevJobStatus = currentJobStatus;

        console.log(`Poll#${i} allDone=${allDone} jobIdle=${jobJustBecameIdle}`);

        if (allDone || jobJustBecameIdle) {
          console.log("BREAK: generation complete!");
          const fullStoryboard = await fetchStoryboard(storyboardIdRef.current);
          if (fullStoryboard) {
            onUpdateRef.current(fullStoryboard);
          }
          break;
        }
      } catch (e) {
        console.log(`Poll#${i} ERROR: ${e instanceof Error ? e.message : String(e)}`);
        consecutiveFailures++;
        if (abortRef.current) break;
        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          console.log(`BREAK: ${MAX_CONSECUTIVE_FAILURES} consecutive failures`);
          break;
        }
      }
    }

    try {
      if (!abortRef.current) {
        console.log("Final fetch...");
        const fullStoryboard = await fetchStoryboard(storyboardIdRef.current);
        if (fullStoryboard) {
          console.log(`Final fetch OK status=${fullStoryboard.status}`);
          onUpdateRef.current(fullStoryboard);
        }
      }
    } catch (e) {
      console.log(`Final fetch ERROR: ${e instanceof Error ? e.message : String(e)}`);
    }

    console.log("pollUntilDone END");
    setGenStatus(null);
  }

  async function handleGenerateAll() {
    console.log(`handleGenerateAll START id=${storyboard.id} provider=${imageProvider}`);
    setGeneratingAll(true);
    setGenerateError(null);
    try {
      console.log("POST generate-images...");
      const result = await generateStoryboardImages(storyboard.id, imageProvider);
      console.log(`POST OK: ${JSON.stringify(result)}`);
      console.log("pollUntilDone start...");
      await pollUntilDone();
      console.log("pollUntilDone done");
    } catch (e) {
      console.log(`CATCH: ${e instanceof Error ? e.message : String(e)}`);
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("400") || msg.toLowerCase().includes("pending")) {
        setGenerateError("生成対象のシーンがありません。シーンを再追加するか、個別に再生成してください。");
      } else {
        setGenerateError("画像生成の開始に失敗しました。しばらく待ってから再試行してください。");
      }
    } finally {
      console.log("FINALLY: generatingAll=false");
      setGeneratingAll(false);
    }
  }

  async function handleRegenerate(scene: StoryboardScene) {
    setRegeneratingIds((prev) => new Set(prev).add(scene.id));
    try {
      await regenerateSceneImage(storyboard.id, scene.id, imageProvider);
      await pollUntilDone();
    } catch (e) {
      console.error("Regenerate failed:", e);
    }
    setRegeneratingIds((prev) => {
      const next = new Set(prev);
      next.delete(scene.id);
      return next;
    });
  }

  async function handleApprove() {
    setApproving(true);
    try {
      const updated = await approveStoryboardImages(storyboard.id);
      onStoryboardUpdate(updated);
      onNext();
    } catch (e) {
      console.error("Approve images failed:", e);
    }
    setApproving(false);
  }

  const progressPercent =
    genStatus && genStatus.total_scenes > 0
      ? Math.round((genStatus.completed_scenes / genStatus.total_scenes) * 100)
      : 0;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">

      {/* コントロールバー */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={imageProvider}
          onChange={(e) => onImageProviderChange(e.target.value)}
          disabled={scenes.length === 0}
          className="px-3 py-2 bg-[#132040] border border-blue-400/[0.10] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none disabled:opacity-40"
        >
          <option value="gemini">Gemini Flash (標準)</option>
          <option value="gemini_pro">Gemini Pro (高品質)</option>
          <option value="imagen">Imagen 4 Fast (最速)</option>
        </select>
        <button
          onClick={handleGenerateAll}
          disabled={generatingAll || scenes.length === 0 || (!hasGenerableScenes && !generatingAll)}
          title={
            scenes.length === 0
              ? "シーンがありません。Step 1 でシーンを追加してください"
              : !hasGenerableScenes && !generatingAll
              ? "全シーンが完成済みです。個別に再生成するには各シーンの「再生成」ボタンを使用してください"
              : undefined
          }
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-medium rounded-xl text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {generatingAll ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Sparkles size={14} />
          )}
          全画像を生成
        </button>
        {scenes.length === 0 && (
          <span className="text-xs text-amber-400 flex items-center gap-1.5">
            シーンがありません。Step 1 でシーンを追加してください。
          </span>
        )}
        {generatingAll && (
          <span className="text-xs text-amber-300 flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            {genStatus && genStatus.completed_scenes != null
              ? `画像生成中... (${genStatus.completed_scenes}/${genStatus.total_scenes}完了${
                  genStatus.estimated_remaining_seconds !== null
                    ? ` - 残り${formatRemainingTime(genStatus.estimated_remaining_seconds)}`
                    : ""
                })`
              : "生成中..."}
          </span>
        )}
      </div>

      {/* 生成エラーメッセージ */}
      {generateError && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-400/20 rounded-xl text-xs text-red-300">
          <RefreshCw size={12} className="flex-shrink-0" />
          {generateError}
        </div>
      )}

      {/* 生成中プログレスバー */}
      {generatingAll && genStatus && genStatus.completed_scenes != null && (
        <div className="bg-[#0e1d32] border border-blue-400/[0.10] rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium">
              画像生成中 ({genStatus.completed_scenes}/{genStatus.total_scenes}シーン)
            </span>
            <span className="text-slate-500">
              {genStatus.elapsed_seconds !== null
                ? `経過: ${formatElapsedTime(genStatus.elapsed_seconds)}`
                : ""}
            </span>
          </div>
          <div className="w-full bg-[#132040] rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-700"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-blue-300/70">{progressPercent}%</span>
            {genStatus.estimated_remaining_seconds !== null && (
              <span className="text-amber-300/80 flex items-center gap-1">
                <Clock size={10} />
                残り{formatRemainingTime(genStatus.estimated_remaining_seconds)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* シーン画像グリッド */}
      <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
        {scenes.map((scene, idx) => {
          const isGenerating =
            scene.image_status === "generating" ||
            scene.image_status === "pending" ||
            regeneratingIds.has(scene.id);
          const isReady = scene.image_status === "ready" || scene.image_status === "complete";
          const isFailed = scene.image_status === "failed";
          const isSelected = selectedSceneIdx === idx;
          const isSelectable = isReady && !!scene.image_path;
          const courseName = COURSE_LABELS[scene.course_key] ?? scene.course_key;
          const ordLabel = SORT_ORDER_LABELS[scene.sort_order] ?? `${scene.sort_order + 1}.`;

          return (
            <div
              key={scene.id}
              onClick={() => {
                if (isSelectable) setSelectedSceneIdx(idx);
              }}
              className={`bg-[#0e1d32] rounded-xl border overflow-hidden transition-all ${
                isSelected
                  ? "border-blue-400 ring-2 ring-blue-400/50"
                  : isSelectable
                  ? "border-blue-400/[0.10] hover:border-blue-400/30 cursor-pointer"
                  : "border-blue-400/[0.10]"
              }`}
            >
              <div className="flex items-center justify-between px-3 py-2 border-b border-blue-400/[0.06]">
                <span className="text-xs font-medium text-slate-200">
                  <span className="text-blue-300 mr-1">{ordLabel}</span>
                  {courseName}
                </span>
                <div className="flex items-center gap-1.5">
                  {isSelected && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-400/20 text-blue-300 font-medium">
                      プレビュー中
                    </span>
                  )}
                  <StatusBadge status={scene.image_status} />
                </div>
              </div>

              {/* 画像エリア */}
              <div className="relative aspect-video bg-[#080f1a] overflow-hidden">
                {isReady && scene.image_path ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    key={scene.image_path}
                    src={`${API_BASE}${scene.image_path}?t=${encodeURIComponent(scene.updated_at ?? scene.image_path)}`}
                    alt={courseName}
                    className="w-full h-full object-cover"
                  />
                ) : isGenerating ? (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                    <div className="w-full h-full bg-blue-500/5 animate-pulse" />
                    <div className="absolute flex flex-col items-center gap-2">
                      <Loader2 size={20} className="animate-spin text-blue-400" />
                      <span className="text-[10px] text-slate-500">生成中...</span>
                    </div>
                  </div>
                ) : isFailed ? (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
                    <span className="text-[10px] text-red-400">生成に失敗</span>
                  </div>
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
                    <Image size={20} className="text-slate-700" />
                    <span className="text-[10px] text-slate-600">未生成</span>
                  </div>
                )}
                {/* Selected overlay indicator */}
                {isSelected && (
                  <div className="absolute top-2 right-2 flex items-center justify-center w-5 h-5 rounded-full bg-blue-400 pointer-events-none">
                    <Check size={11} className="text-[#080f1a]" />
                  </div>
                )}
              </div>

              <div className="px-3 py-2.5 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 font-mono truncate flex-1 pr-2">
                  {scene.aspect_ratio}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRegenerate(scene);
                  }}
                  disabled={isGenerating}
                  className="flex items-center gap-1 px-2 py-1 bg-[#132040] hover:bg-blue-400/[0.10] text-slate-400 hover:text-white rounded-lg text-[10px] transition-colors disabled:opacity-40 flex-shrink-0"
                >
                  <RefreshCw size={10} />
                  再生成
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* テーブル投影プレビュー */}
      {selectedSceneIdx !== null && scenes[selectedSceneIdx]?.image_path && (
        <div className="bg-[#0e1d32] rounded-xl border border-blue-400/[0.10] p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-widest">
              テーブル投影プレビュー
            </p>
            <p className="text-[11px] text-blue-300/70">
              プレビュー:{" "}
              <span className="font-medium text-blue-300">
                {SORT_ORDER_LABELS[scenes[selectedSceneIdx].sort_order] ?? `${scenes[selectedSceneIdx].sort_order + 1}.`}{" "}
                {COURSE_LABELS[scenes[selectedSceneIdx].course_key] ?? scenes[selectedSceneIdx].course_key}
              </span>
            </p>
          </div>

          {/* Table surface with plate positions */}
          <div
            className="relative w-full overflow-hidden border border-blue-400/[0.15]"
            style={{
              height: 72,
              background: "linear-gradient(180deg, #0d1f38 0%, #0a1628 50%, #0d1f38 100%)",
            }}
          >
            {storyboard.mode === "unified" ? (
              <>
                {/* Show selected scene's image as full-width background */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  key={scenes[selectedSceneIdx].image_path}
                  src={`${API_BASE}${scenes[selectedSceneIdx].image_path}?t=${encodeURIComponent(scenes[selectedSceneIdx].updated_at ?? scenes[selectedSceneIdx].image_path ?? "")}`}
                  alt=""
                  className="absolute inset-0 w-full h-full object-cover opacity-60"
                />
                {/* Plate positions for unified mode: 4 zones × 2 plates = 8 plates */}
                <div className="absolute inset-0 flex pointer-events-none">
                  {[0, 1, 2, 3].map((zoneIdx) => (
                    <div key={zoneIdx} className="flex-1 relative">
                      {[0, 1].map((plateIdx) => (
                        <div
                          key={plateIdx}
                          className="absolute border border-blue-300/40 rounded-full"
                          style={{
                            width: 26,
                            height: 20,
                            left: plateIdx === 0 ? "25%" : "75%",
                            bottom: 8,
                            transform: "translateX(-50%)",
                            background: "radial-gradient(ellipse at 40% 35%, rgba(255,255,255,0.14) 0%, rgba(59,130,246,0.08) 100%)",
                            boxShadow: "0 0 6px rgba(147,197,253,0.20)",
                          }}
                        />
                      ))}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="absolute inset-0 flex">
                {scenes.map((scene, idx) => {
                  const isSelectedZone = idx === selectedSceneIdx;
                  return (
                    <div
                      key={scene.id}
                      className="flex-1 relative border-r border-blue-400/[0.10] last:border-r-0 overflow-hidden flex flex-col"
                    >
                      {scene.image_path ? (
                        /* eslint-disable-next-line @next/next/no-img-element */
                        <img
                          key={scene.image_path}
                          src={`${API_BASE}${scene.image_path}?t=${encodeURIComponent(scene.updated_at ?? scene.image_path)}`}
                          alt=""
                          className={`absolute inset-0 w-full h-full object-cover transition-opacity ${
                            isSelectedZone ? "opacity-70" : "opacity-20"
                          }`}
                        />
                      ) : null}
                      {/* Dim overlay for non-selected zones */}
                      {!isSelectedZone && (
                        <div className="absolute inset-0 bg-[#080f1a]/60 pointer-events-none" />
                      )}
                      {/* Zone label */}
                      <div className="absolute top-1 left-0 right-0 flex justify-center pointer-events-none">
                        <span className={`text-[9px] font-medium ${isSelectedZone ? "text-blue-300/80" : "text-blue-300/30"}`}>
                          Z{idx + 1}
                        </span>
                      </div>
                      {/* Plate positions: 2 per zone, bottom-aligned */}
                      {[0, 1].map((plateIdx) => (
                        <div
                          key={plateIdx}
                          className="absolute rounded-full pointer-events-none"
                          style={{
                            width: 26,
                            height: 20,
                            left: plateIdx === 0 ? "25%" : "75%",
                            bottom: 8,
                            transform: "translateX(-50%)",
                            border: isSelectedZone ? "1px solid rgba(147,197,253,0.50)" : "1px solid rgba(147,197,253,0.20)",
                            background: "radial-gradient(ellipse at 40% 35%, rgba(255,255,255,0.14) 0%, rgba(59,130,246,0.08) 100%)",
                            boxShadow: isSelectedZone ? "0 0 6px rgba(147,197,253,0.30)" : "none",
                          }}
                        />
                      ))}
                    </div>
                  );
                })}
              </div>
            )}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse at 50% 50%, rgba(59,130,246,0.04) 0%, transparent 70%)",
              }}
            />
          </div>

          {/* Seat indicators below the table: 2 per zone, aligned with plates */}
          <div className="flex w-full gap-0">
            {(storyboard.mode === "unified" ? [0, 1, 2, 3] : scenes.map((_, i) => i)).map((zoneIdx) => (
              <div
                key={zoneIdx}
                className="flex-1 relative"
                style={{
                  height: 20,
                  borderRight: storyboard.mode !== "unified" && zoneIdx < (scenes.length - 1)
                    ? "1px solid rgba(59,130,246,0.08)"
                    : "none",
                }}
              >
                {[0, 1].map((seatIdx) => (
                  <div
                    key={seatIdx}
                    style={{
                      position: "absolute",
                      left: seatIdx === 0 ? "25%" : "75%",
                      top: "50%",
                      transform: "translate(-50%, -50%)",
                      width: 18,
                      height: 10,
                      borderRadius: 3,
                      background: "linear-gradient(180deg, #132040 0%, #0e1d32 100%)",
                      border: "1px solid rgba(148,163,184,0.15)",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                    }}
                  >
                    {/* Seat back (top edge accent) */}
                    <div
                      style={{
                        position: "absolute",
                        top: -3,
                        left: 2,
                        right: 2,
                        height: 2,
                        borderRadius: 1,
                        background: "rgba(148,163,184,0.20)",
                      }}
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 pt-0.5">
            <div className="flex items-center gap-1.5">
              <div
                className="border border-blue-300/30 rounded-full"
                style={{ width: 10, height: 7 }}
              />
              <span className="text-[9px] text-slate-600">プレート位置</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                style={{
                  width: 12,
                  height: 7,
                  borderRadius: 2,
                  border: "1px solid rgba(148,163,184,0.15)",
                  background: "linear-gradient(180deg, #132040 0%, #0e1d32 100%)",
                }}
              />
              <span className="text-[9px] text-slate-600">座席 (8席)</span>
            </div>
          </div>
        </div>
      )}

      {/* 承認して次へ */}
      <div className="flex items-center justify-between pt-2 border-t border-blue-400/[0.08]">
        <div className="text-xs text-slate-500">
          {!allReady && scenes.length > 0 && (
            <span className="flex items-center gap-1.5 text-amber-400/80">
              <Loader2 size={11} className="animate-spin" />
              全シーンの画像が完成してから承認できます
              （{scenes.filter((s) => s.image_status === "ready" || s.image_status === "complete").length}/{scenes.length}枚完了）
            </span>
          )}
          {allReady && (
            <span className="text-emerald-400/80">
              全{scenes.length}枚の画像が完成しました。内容を確認して承認してください。
            </span>
          )}
        </div>
        <button
          onClick={handleApprove}
          disabled={!allReady || approving}
          className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-medium rounded-xl text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            boxShadow: allReady && !approving ? "0 0 20px rgba(59,130,246,0.25)" : "none",
          }}
          title={!allReady ? "全シーンの画像が完成してから承認できます" : "画像を承認して動画生成ステップへ進みます"}
        >
          {approving ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Check size={15} />
          )}
          画像を承認して動画生成へ
          {!approving && <ArrowRight size={15} />}
        </button>
      </div>
    </div>
  );
}

// ── Step 3: 動画生成 ──────────────────────────────────────────

function VideoGenerationStep({
  storyboard,
  onStoryboardUpdate,
}: {
  storyboard: StoryboardData;
  onStoryboardUpdate: (sb: StoryboardData) => void;
}) {
  const [generatingAll, setGeneratingAll] = useState(false);
  const [regeneratingIds, setRegeneratingIds] = useState<Set<number>>(new Set());
  const [qualitySettings, setQualitySettings] = useState<VideoQualitySettings>({
    provider: (storyboard.provider as VideoQualitySettings["provider"]) ?? "runway",
    qualityPreset: "maximum",
    resolution: "1920×1080",
    motionIntensity: "medium",
    styleConsistency: true,
  });
  const abortRef = useRef(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Stable refs so async poll loop always reads the latest values
  const storyboardIdRef = useRef(storyboard.id);
  storyboardIdRef.current = storyboard.id;
  const storyboardRef = useRef(storyboard);
  storyboardRef.current = storyboard;
  const onUpdateRef = useRef(onStoryboardUpdate);
  onUpdateRef.current = onStoryboardUpdate;

  const scenes = storyboard.scenes;
  const allVideosReady =
    scenes.length > 0 && scenes.every((s) => s.video_status === "ready" || s.video_status === "complete");

  // Sync provider to storyboard provider when it changes externally
  useEffect(() => {
    if (storyboard.provider && storyboard.provider !== qualitySettings.provider) {
      setQualitySettings((prev) => ({
        ...prev,
        provider: storyboard.provider as VideoQualitySettings["provider"],
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyboard.provider]);

  useEffect(() => {
    return () => { abortRef.current = true; };
  }, []);

  async function pollVideoUntilDone() {
    for (let i = 0; i < 360; i++) {
      if (abortRef.current) break;
      await new Promise((r) => setTimeout(r, 1000));
      if (abortRef.current) break;
      try {
        const scenesStatus = await fetchScenesStatus(storyboardIdRef.current);

        // Update video statuses in local state for immediate UI feedback
        if (scenesStatus?.scenes) {
          onUpdateRef.current({
            ...storyboardRef.current,
            scenes: storyboardRef.current.scenes.map((scene) => {
              const updated = scenesStatus.scenes.find((s) => s.id === scene.id);
              if (updated) {
                return {
                  ...scene,
                  video_status: updated.video_status,
                  video_path: updated.video_path,
                };
              }
              return scene;
            }),
          });
        }

        // Check if all video scenes are in a terminal state
        const allDone = scenesStatus?.scenes?.every(
          (s) => s.video_status === "complete" || s.video_status === "ready" || s.video_status === "failed"
        );

        if (allDone) {
          // Fetch full storyboard once at the end to get authoritative state
          const fullStoryboard = await fetchStoryboard(storyboardIdRef.current);
          if (fullStoryboard) {
            onUpdateRef.current(fullStoryboard);
          }
          break;
        }
      } catch (e) {
        console.error("[Poll] Video error:", e);
      }
    }
  }

  async function handleGenerateAll() {
    setGeneratingAll(true);
    try {
      // プロバイダーをストーリーボードに保存してから生成
      if (qualitySettings.provider !== storyboard.provider) {
        await updateStoryboard(storyboard.id, { provider: qualitySettings.provider });
      }
      await generateStoryboardVideos(storyboard.id);
      await pollVideoUntilDone();
    } catch (e) {
      console.error("Generate videos failed:", e);
    }
    setGeneratingAll(false);
  }

  async function handleRegenerate(scene: StoryboardScene) {
    setRegeneratingIds((prev) => new Set(prev).add(scene.id));
    try {
      await regenerateSceneVideo(storyboard.id, scene.id);
      await pollVideoUntilDone();
    } catch (e) {
      console.error("Regenerate video failed:", e);
    }
    setRegeneratingIds((prev) => {
      const next = new Set(prev);
      next.delete(scene.id);
      return next;
    });
  }

  const avgSceneDuration =
    scenes.length > 0
      ? Math.round(scenes.reduce((sum, s) => sum + s.duration_seconds, 0) / scenes.length)
      : 120;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">

      {/* ── 動画品質パネル（ヒーロー） ── */}
      <div
        className="rounded-2xl border p-6"
        style={{
          background: "linear-gradient(135deg, rgba(15,30,60,0.95) 0%, rgba(10,22,46,0.95) 100%)",
          borderColor: "rgba(59,130,246,0.18)",
          boxShadow: "0 0 40px rgba(59,130,246,0.06), inset 0 1px 0 rgba(59,130,246,0.08)",
        }}
      >
        <VideoQualityPanel
          settings={qualitySettings}
          onSettingsChange={setQualitySettings}
          sceneCount={scenes.length}
          sceneDurationSeconds={avgSceneDuration}
        />

        {/* 生成ボタン */}
        <div className="mt-6 pt-5 border-t border-blue-400/[0.10]">
          <div className="flex items-center gap-4">
            <button
              onClick={handleGenerateAll}
              disabled={generatingAll || scenes.length === 0}
              className="flex items-center gap-2.5 px-6 py-3 font-semibold rounded-xl text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: generatingAll
                  ? "rgba(59,130,246,0.20)"
                  : "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
                boxShadow: generatingAll ? "none" : "0 0 30px rgba(59,130,246,0.35), 0 4px 12px rgba(0,0,0,0.4)",
                color: "white",
              }}
            >
              {generatingAll ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Video size={16} />
              )}
              {generatingAll ? "動画生成中..." : "全シーンの動画を生成"}
            </button>

            {generatingAll && (
              <div className="flex items-center gap-2 text-amber-300 text-xs">
                <Loader2 size={12} className="animate-spin" />
                <span>
                  {qualitySettings.provider === "runway" ? "Runway Gen-4.5" :
                   qualitySettings.provider === "kling" ? "Kling 2.6" : "Pika 2.5"} で処理中...
                </span>
              </div>
            )}

            {allVideosReady && !generatingAll && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/[0.10] border border-emerald-400/20 rounded-xl">
                <Check size={13} className="text-emerald-400" />
                <span className="text-xs text-emerald-300 font-medium">全シーン完了</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── シーン動画ステータス ── */}
      <div>
        <p className="text-[10px] font-medium text-slate-500 uppercase tracking-widest mb-3">
          シーン別ステータス
        </p>
        <div className="space-y-3">
        {scenes.map((scene) => {
          const isGenerating =
            scene.video_status === "generating" ||
            scene.video_status === "pending" ||
            regeneratingIds.has(scene.id);
          const isReady = scene.video_status === "ready" || scene.video_status === "complete";
          const isFailed = scene.video_status === "failed";
          const courseName = COURSE_LABELS[scene.course_key] ?? scene.course_key;
          const ordLabel = SORT_ORDER_LABELS[scene.sort_order] ?? `${scene.sort_order + 1}.`;

          return (
            <div
              key={scene.id}
              className="bg-[#0e1d32] rounded-xl border border-blue-400/[0.10] overflow-hidden"
            >
              <div className="flex items-center gap-4 p-4">
                {/* サムネイル */}
                <div
                  className="flex-shrink-0 overflow-hidden border border-blue-400/[0.10]"
                  style={{ width: 80, height: 48 }}
                >
                  {scene.image_path ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      key={scene.image_path}
                      src={`${API_BASE}${scene.image_path}?t=${encodeURIComponent(scene.updated_at ?? scene.image_path)}`}
                      alt={courseName}
                      className="w-full h-full object-cover opacity-80"
                    />
                  ) : (
                    <div className="w-full h-full bg-[#080f1a] flex items-center justify-center">
                      <Image size={14} className="text-slate-700" />
                    </div>
                  )}
                </div>

                {/* 情報 */}
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-100">
                      <span className="text-blue-300 mr-1">{ordLabel}</span>
                      {courseName}
                    </span>
                    <StatusBadge status={scene.video_status} />
                  </div>
                  <p className="text-[11px] text-slate-500 font-mono truncate">
                    {scene.prompt_edited ?? scene.prompt}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1 text-[10px] text-slate-600">
                      <Clock size={9} />
                      {scene.duration_seconds}s
                    </span>
                    <span className="text-[10px] text-slate-600">{scene.aspect_ratio}</span>
                  </div>
                </div>

                {/* ビデオプレビュー or ステータス */}
                <div className="flex-shrink-0 flex items-center gap-2">
                  {isReady && scene.video_path ? (
                    <div className="flex items-center gap-1 text-[10px] text-emerald-400">
                      <Check size={11} />
                      動画完成
                    </div>
                  ) : isGenerating ? (
                    <div className="flex items-center gap-1 text-[10px] text-amber-300">
                      <Loader2 size={11} className="animate-spin" />
                      生成中
                    </div>
                  ) : isFailed ? (
                    <div className="text-[10px] text-red-400">失敗</div>
                  ) : null}

                  <button
                    onClick={() => handleRegenerate(scene)}
                    disabled={isGenerating}
                    className="flex items-center gap-1 px-2.5 py-1.5 bg-[#132040] hover:bg-blue-400/[0.10] text-slate-400 hover:text-white rounded-lg text-[10px] transition-colors disabled:opacity-40"
                  >
                    <RefreshCw size={10} />
                    再生成
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        </div>
      </div>

      {/* 完了メッセージ */}
      {allVideosReady && (
        <div className="bg-emerald-500/[0.08] border border-emerald-400/20 rounded-xl p-5 space-y-4">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-500/20 mb-1">
              <Check size={18} className="text-emerald-400" />
            </div>
            <p className="text-sm font-semibold text-emerald-300">全ての動画生成が完了しました</p>
            <p className="text-xs text-slate-400">
              {scenes.length}シーンの動画が正常に生成されました。投影制御ページでショーを開始してください。
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2 border-t border-emerald-400/[0.12]">
            <a
              href="/control"
              className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-xl text-sm transition-all"
              style={{ boxShadow: "0 0 20px rgba(16,185,129,0.25)" }}
            >
              <ArrowRight size={15} />
              投影制御ページへ進む
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ── メインコンポーネント ──────────────────────────────────────

export default function StoryboardWorkflowTab({
  themes,
}: StoryboardWorkflowTabProps) {
  const [currentStep, setCurrentStep] = useState<Step>(1);
  const [storyboards, setStoryboards] = useState<StoryboardListItem[]>([]);
  const [selectedStoryboard, setSelectedStoryboard] = useState<StoryboardData | null>(null);
  const [sidebarLoading, setSidebarLoading] = useState(true);
  const [imageProvider, setImageProvider] = useState("imagen");

  // suppress unused warning for themes - may be used in future
  void themes;

  const loadStoryboards = useCallback(async () => {
    setSidebarLoading(true);
    try {
      const list = await fetchStoryboards();
      setStoryboards(list);
    } catch (e) {
      console.error("Load storyboards failed:", e);
    }
    setSidebarLoading(false);
  }, []);

  useEffect(() => {
    loadStoryboards();
  }, [loadStoryboards]);

  // SSE購読: バックエンドからリアルタイムでシーン・ストーリーボードの更新を受け取る
  // selectedStoryboard が変わるたびに正しい id を参照するため ref を使う
  const selectedStoryboardRef = useRef(selectedStoryboard);
  selectedStoryboardRef.current = selectedStoryboard;
  const setSelectedStoryboardRef = useRef(setSelectedStoryboard);
  setSelectedStoryboardRef.current = setSelectedStoryboard;

  useEffect(() => {
    const unsubscribe = subscribeToStoryboardEvents((event) => {
      if (event.type === "scene_updated") {
        const current = selectedStoryboardRef.current;
        if (!current || current.id !== event.storyboard_id) return;
        // 特定シーンのステータスをローカルStateで即時更新
        setSelectedStoryboardRef.current((prev) => {
          if (!prev || prev.id !== event.storyboard_id) return prev;
          return {
            ...prev,
            scenes: prev.scenes.map((scene) =>
              scene.id === event.scene_id
                ? {
                    ...scene,
                    ...(event.image_status !== undefined && { image_status: event.image_status }),
                    ...(event.image_path !== undefined && { image_path: event.image_path ?? scene.image_path }),
                    ...(event.video_status !== undefined && { video_status: event.video_status }),
                    ...(event.video_path !== undefined && { video_path: event.video_path ?? scene.video_path }),
                  }
                : scene
            ),
          };
        });
      }

      if (event.type === "storyboard_updated") {
        const current = selectedStoryboardRef.current;
        if (!current || current.id !== event.storyboard_id) return;
        // ストーリーボード全体を再取得して確実に最新状態へ同期
        fetchStoryboard(event.storyboard_id)
          .then((sb) => {
            setSelectedStoryboardRef.current(sb);
            // サイドバーのステータスも更新
            loadStoryboards();
          })
          .catch((e) => console.error("[SSE] storyboard_updated fetch failed:", e));
      }
    });

    // コンポーネントのアンマウント時にSSE接続を閉じる
    return () => unsubscribe();
  }, [loadStoryboards]);

  async function handleSelectStoryboard(id: number) {
    try {
      const sb = await fetchStoryboard(id);
      setSelectedStoryboard(sb);
      // ステータスに基づいてステップを自動設定
      if (sb.status === "video_ready") {
        setCurrentStep(3);
      } else if (sb.status === "images_ready") {
        setCurrentStep(2);
      } else if (sb.status === "script_ready") {
        setCurrentStep(2);
      } else {
        setCurrentStep(1);
      }
    } catch (e) {
      console.error("Select storyboard failed:", e);
    }
  }

  async function handleDeleteStoryboard(id: number) {
    if (!confirm("この台本を削除しますか？")) return;
    try {
      await deleteStoryboard(id);
      if (selectedStoryboard?.id === id) {
        setSelectedStoryboard(null);
        setCurrentStep(1);
      }
      loadStoryboards();
    } catch (e) {
      console.error("Delete storyboard failed:", e);
    }
  }

  async function handleNewCreate() {
    setCurrentStep(1);
    try {
      // 絵コンテ方式: タイトルだけで空の台本を作成（テーマ・曜日は不要）
      const sb = await createStoryboard({
        title: "新しい台本",
        auto_generate_scenes: false,
      });
      setSelectedStoryboard(sb);
      loadStoryboards();
    } catch (e) {
      console.error("Create storyboard failed:", e);
      setSelectedStoryboard(null);
      alert("台本の作成に失敗しました。バックエンドAPIが起動しているか確認してください。");
    }
  }

  const handleStoryboardUpdate = useCallback((sb: StoryboardData) => {
    setSelectedStoryboard(sb);
  }, []);

  return (
    <div
      className="flex flex-col bg-[#0e1d32] rounded-2xl border border-blue-400/[0.10] overflow-hidden"
      style={{ minHeight: 600 }}
    >
      {/* 上部: ステップインジケーター */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-blue-400/[0.10] bg-[#080f1a]">
        <StepIndicator currentStep={currentStep} />
        {selectedStoryboard && (
          <div className="flex items-center gap-2">
            {currentStep > 1 && (
              <button
                onClick={() => setCurrentStep((prev) => (prev - 1) as Step)}
                className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded-lg hover:bg-blue-400/[0.05]"
              >
                戻る
              </button>
            )}
          </div>
        )}
      </div>

      {/* 下部: サイドバー + メインコンテンツ */}
      <div className="flex flex-1 overflow-hidden" style={{ minHeight: 540 }}>
        {/* サイドバー */}
        <StoryboardSidebar
          storyboards={storyboards}
          selectedId={selectedStoryboard?.id ?? null}
          onSelect={handleSelectStoryboard}
          onDelete={handleDeleteStoryboard}
          onNewCreate={handleNewCreate}
          loading={sidebarLoading}
        />

        {/* メインコンテンツ */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {currentStep === 1 && (
            <ScriptCreationStep
              storyboard={selectedStoryboard}
              onStoryboardUpdate={handleStoryboardUpdate}
              onNext={() => setCurrentStep(2)}
              imageProvider={imageProvider}
              onImageProviderChange={setImageProvider}
            />
          )}

          {currentStep === 2 && selectedStoryboard && (
            <ImagePreviewStep
              storyboard={selectedStoryboard}
              onStoryboardUpdate={handleStoryboardUpdate}
              onNext={() => setCurrentStep(3)}
              imageProvider={imageProvider}
              onImageProviderChange={setImageProvider}
            />
          )}

          {currentStep === 3 && selectedStoryboard && (
            <VideoGenerationStep
              storyboard={selectedStoryboard}
              onStoryboardUpdate={handleStoryboardUpdate}
            />
          )}

          {/* Step 2 or 3 but no storyboard selected */}
          {(currentStep === 2 || currentStep === 3) && !selectedStoryboard && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-2">
                <BookOpen size={32} className="mx-auto text-slate-700" />
                <p className="text-sm text-slate-400">台本を選択してください</p>
                <button
                  onClick={() => setCurrentStep(1)}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Step 1 に戻る
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
