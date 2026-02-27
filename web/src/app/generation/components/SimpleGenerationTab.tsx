"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Image as ImageIcon,
  Video,
  Check,
  RefreshCw,
  Loader2,
  ChevronRight,
  Sparkles,
  BookOpen,
  Plus,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Play,
} from "lucide-react";
import {
  fetchStoryboards,
  fetchStoryboard,
  createStoryboard,
  generateStoryboardImages,
  regenerateSceneImage,
  approveStoryboardImages,
  generateStoryboardVideos,
  fetchGenerationStatus,
  fetchScenesStatus,
  subscribeToStoryboardEvents,
  type GenerationThemes,
  type StoryboardData,
  type StoryboardListItem,
  type StoryboardScene,
  type GenerationStatus,
} from "@/lib/api";
import { DAY_THEMES } from "@/lib/themes";

// ── 定数 ───────────────────────────────────────────────────────

const DAY_BUTTONS = [
  { key: "monday", label: "月" },
  { key: "tuesday", label: "火" },
  { key: "wednesday", label: "水" },
  { key: "thursday", label: "木" },
  { key: "friday", label: "金" },
  { key: "saturday", label: "土" },
  { key: "sunday", label: "日" },
];

const COURSE_LABELS: Record<string, string> = {
  welcome: "ウェルカム",
  appetizer: "前菜",
  soup: "スープ",
  main: "メイン",
  dessert: "デザート",
  custom: "カスタム",
};

const STATUS_CONFIGS: Record<string, { label: string; className: string }> = {
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

type WorkflowStep = 1 | 2 | 3;

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

// ── ステップインジケーター ─────────────────────────────────────

function StepIndicator({ currentStep }: { currentStep: WorkflowStep }) {
  const steps = [
    { id: 1 as WorkflowStep, label: "① 画像生成", icon: <ImageIcon size={14} />, desc: "全シーンの画像を生成" },
    { id: 2 as WorkflowStep, label: "② 画像確認", icon: <Check size={14} />, desc: "画像を確認・承認" },
    { id: 3 as WorkflowStep, label: "③ 動画生成", icon: <Video size={14} />, desc: "承認済み画像から動画を生成" },
  ];

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, index) => {
        const isCompleted = currentStep > step.id;
        const isCurrent = currentStep === step.id;

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
                <div
                  className={`text-[10px] ${
                    isCurrent ? "text-blue-400/60" : isCompleted ? "text-emerald-400/60" : "text-slate-700"
                  }`}
                >
                  {step.desc}
                </div>
              </div>
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

// ── API_BASE ───────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── メインコンポーネント ──────────────────────────────────────

interface SimpleGenerationTabProps {
  themes: GenerationThemes | null;
}

export default function SimpleGenerationTab({ themes }: SimpleGenerationTabProps) {
  const [step, setStep] = useState<WorkflowStep>(1);
  const [storyboards, setStoryboards] = useState<StoryboardListItem[]>([]);
  const [storyboardsLoading, setStoryboardsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [storyboard, setStoryboard] = useState<StoryboardData | null>(null);
  const [storyboardLoading, setStoryboardLoading] = useState(false);

  // 台本を作成するときの設定
  const [newDay, setNewDay] = useState("monday");
  const [newProvider, setNewProvider] = useState("gemini");
  const [creating, setCreating] = useState(false);

  // Step 1: 画像生成
  const [imageProvider, setImageProvider] = useState("gemini");
  const [generatingImages, setGeneratingImages] = useState(false);
  const [genStatus, setGenStatus] = useState<GenerationStatus | null>(null);
  const [pollingImages, setPollingImages] = useState(false);

  // Step 2: 画像確認 — シーンの最新ステータス
  const [sceneStatuses, setSceneStatuses] = useState<
    Array<{
      id: number;
      image_status: string;
      image_path: string | null;
      video_status: string;
      video_path: string | null;
    }>
  >([]);
  const [regeneratingIds, setRegeneratingIds] = useState<Set<number>>(new Set());
  const [approving, setApproving] = useState(false);

  // Step 3: 動画生成
  const [generatingVideos, setGeneratingVideos] = useState(false);
  const [videoStatus, setVideoStatus] = useState<GenerationStatus | null>(null);
  const [pollingVideos, setPollingVideos] = useState(false);

  // フィードバック
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showFeedback = useCallback((type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 5000);
  }, []);

  // 台本一覧を読み込む
  const loadStoryboards = useCallback(async () => {
    setStoryboardsLoading(true);
    try {
      const data = await fetchStoryboards();
      setStoryboards(data);
    } catch {
      showFeedback("error", "台本一覧の取得に失敗しました");
    }
    setStoryboardsLoading(false);
  }, [showFeedback]);

  useEffect(() => {
    loadStoryboards();
  }, [loadStoryboards]);

  // SSE購読: バックエンドからリアルタイムでシーン・ストーリーボードの更新を受け取る
  const storyboardRef = useRef(storyboard);
  storyboardRef.current = storyboard;
  const setStoryboardRef = useRef(setStoryboard);
  setStoryboardRef.current = setStoryboard;
  const setSceneStatusesRef = useRef(setSceneStatuses);
  setSceneStatusesRef.current = setSceneStatuses;

  useEffect(() => {
    const unsubscribe = subscribeToStoryboardEvents((event) => {
      if (event.type === "scene_updated") {
        const current = storyboardRef.current;
        if (!current || current.id !== event.storyboard_id) return;
        // シーンのimage_statusをsceneStatusesとstoryboardの両方に即時反映
        setSceneStatusesRef.current((prev) =>
          prev.map((s) =>
            s.id === event.scene_id
              ? {
                  ...s,
                  ...(event.image_status !== undefined && { image_status: event.image_status! }),
                  ...(event.image_path !== undefined && { image_path: event.image_path ?? s.image_path }),
                }
              : s
          )
        );
        setStoryboardRef.current((prev) => {
          if (!prev || prev.id !== event.storyboard_id) return prev;
          return {
            ...prev,
            scenes: prev.scenes.map((scene) =>
              scene.id === event.scene_id
                ? {
                    ...scene,
                    ...(event.image_status !== undefined && { image_status: event.image_status! }),
                    ...(event.image_path !== undefined && { image_path: event.image_path ?? scene.image_path }),
                  }
                : scene
            ),
          };
        });
      }

      if (event.type === "storyboard_updated") {
        const current = storyboardRef.current;
        if (!current || current.id !== event.storyboard_id) return;
        // ストーリーボード全体を再取得して最新状態へ同期
        fetchStoryboard(event.storyboard_id)
          .then((sb) => {
            setStoryboardRef.current(sb);
            loadStoryboards();
          })
          .catch((e) => console.error("[SSE] storyboard_updated fetch failed:", e));
      }
    });

    // コンポーネントのアンマウント時にSSE接続を閉じる
    return () => unsubscribe();
  }, [loadStoryboards]);

  // 台本の詳細を読み込む
  async function loadStoryboard(id: number) {
    setStoryboardLoading(true);
    try {
      const data = await fetchStoryboard(id);
      setStoryboard(data);
      setStep(1);
    } catch {
      showFeedback("error", "台本の読み込みに失敗しました");
    }
    setStoryboardLoading(false);
  }

  function handleSelectStoryboard(id: number) {
    setSelectedId(id);
    loadStoryboard(id);
  }

  // 新規台本作成
  async function handleCreateStoryboard() {
    setCreating(true);
    try {
      const sb = await createStoryboard({
        day_of_week: newDay,
        provider: newProvider,
        auto_generate_scenes: true,
      });
      await loadStoryboards();
      setSelectedId(sb.id);
      setStoryboard(sb);
      setStep(1);
      showFeedback("success", `台本「${sb.title}」を作成しました`);
    } catch {
      showFeedback("error", "台本の作成に失敗しました");
    }
    setCreating(false);
  }

  // Step 1: 画像生成を開始
  async function handleGenerateImages() {
    if (!storyboard) return;
    setGeneratingImages(true);
    setGenStatus(null);
    try {
      await generateStoryboardImages(storyboard.id, imageProvider);
      showFeedback("success", "画像生成を開始しました。完了まで少々お待ちください");
      startPollingImages(storyboard.id);
    } catch {
      showFeedback("error", "画像生成の開始に失敗しました");
      setGeneratingImages(false);
    }
  }

  // 画像生成のポーリング
  // SSEがシーン個別の完了通知をリアルタイムで届けるため、ここでは全体の進捗確認に留める。
  // 旧実装は1000msごとに generation-status + scenes/status の2つを並列取得していたが、
  // SSEと二重になりサーバー負荷が高かった。新実装は3000msに緩め、状態確認のみ行う。
  function startPollingImages(sbId: number) {
    setPollingImages(true);
    // SSE is handling per-scene updates in real time; poll less aggressively
    // (every 3 s instead of 1 s) to only track overall batch completion.
    const interval = setInterval(async () => {
      try {
        const status = await fetchGenerationStatus(sbId);
        setGenStatus(status);
        if (status.status === "idle") {
          // Backend returns "idle" once the batch job finishes.
          // Fetch scene statuses once to determine final outcome.
          const scenesData = await fetchScenesStatus(sbId);
          const allDone = scenesData?.scenes?.every(
            (s) => s.image_status === "complete" || s.image_status === "ready" || s.image_status === "failed"
          );
          if (allDone) {
            clearInterval(interval);
            setPollingImages(false);
            setGeneratingImages(false);
            if (scenesData?.scenes) {
              setSceneStatuses(scenesData.scenes);
            }
            const anyComplete = scenesData?.scenes?.some(
              (s) => s.image_status === "complete" || s.image_status === "ready"
            );
            if (anyComplete) {
              showFeedback("success", "全シーンの画像生成が完了しました。画像を確認してください");
            } else {
              showFeedback("error", "一部のシーンで画像生成に失敗しました");
            }
            setStep(2);
          }
          // If not allDone, continue polling — generation may still be starting up
        }
      } catch {
        clearInterval(interval);
        setPollingImages(false);
        setGeneratingImages(false);
      }
    }, 3000);
  }

  // Step 2: 個別シーンの画像を再生成
  async function handleRegenerateScene(sceneId: number) {
    if (!storyboard) return;
    setRegeneratingIds((prev) => new Set(prev).add(sceneId));
    try {
      await regenerateSceneImage(storyboard.id, sceneId, imageProvider);
      showFeedback("success", "シーンの画像を再生成しています...");
      // 少し待ってからシーンステータスを更新
      setTimeout(async () => {
        try {
          const scenes = await fetchScenesStatus(storyboard.id);
          setSceneStatuses(scenes.scenes);
        } catch {}
        setRegeneratingIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }, 6000);
    } catch {
      showFeedback("error", "再生成に失敗しました");
      setRegeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(sceneId);
        return next;
      });
    }
  }

  // Step 2: 全画像を承認して動画生成ステップへ
  async function handleApproveImages() {
    if (!storyboard) return;
    setApproving(true);
    try {
      await approveStoryboardImages(storyboard.id);
      const refreshed = await fetchStoryboard(storyboard.id);
      setStoryboard(refreshed);
      showFeedback("success", "画像を承認しました。動画生成に進みます");
      setStep(3);
    } catch {
      showFeedback("error", "画像の承認に失敗しました");
    }
    setApproving(false);
  }

  // Step 3: 動画生成を開始
  async function handleGenerateVideos() {
    if (!storyboard) return;
    setGeneratingVideos(true);
    setVideoStatus(null);
    try {
      await generateStoryboardVideos(storyboard.id);
      showFeedback("success", "動画生成を開始しました。完了まで少々お待ちください");
      startPollingVideos(storyboard.id);
    } catch {
      showFeedback("error", "動画生成の開始に失敗しました");
      setGeneratingVideos(false);
    }
  }

  // 動画生成のポーリング
  // 動画生成はSSEで個別通知されるため、全体完了確認だけ5秒間隔で行う。
  function startPollingVideos(sbId: number) {
    setPollingVideos(true);
    const interval = setInterval(async () => {
      try {
        const status = await fetchGenerationStatus(sbId);
        setVideoStatus(status);
        if (status.status === "idle") {
          clearInterval(interval);
          setPollingVideos(false);
          setGeneratingVideos(false);
          const refreshed = await fetchStoryboard(sbId);
          setStoryboard(refreshed);
          await loadStoryboards();
          showFeedback("success", "全シーンの動画生成が完了しました！");
        }
      } catch {
        clearInterval(interval);
        setPollingVideos(false);
        setGeneratingVideos(false);
      }
    }, 5000);
  }

  // シーンステータス取得（Step2に入ったとき）
  useEffect(() => {
    if (step === 2 && storyboard && sceneStatuses.length === 0) {
      fetchScenesStatus(storyboard.id)
        .then((data) => setSceneStatuses(data.scenes))
        .catch(() => {});
    }
  }, [step, storyboard, sceneStatuses.length]);

  // ── シーンをstoryboardから取得しstatusをマージ ──────────────
  function getMergedScenes(): Array<StoryboardScene & {
    latest_image_status: string;
    latest_image_path: string | null;
  }> {
    if (!storyboard) return [];
    return storyboard.scenes.map((scene) => {
      const status = sceneStatuses.find((s) => s.id === scene.id);
      return {
        ...scene,
        latest_image_status: status?.image_status ?? scene.image_status,
        latest_image_path: status?.image_path ?? scene.image_path,
      };
    });
  }

  const mergedScenes = getMergedScenes();
  const allImagesReady =
    mergedScenes.length > 0 &&
    mergedScenes.every(
      (s) => s.latest_image_status === "ready" || s.latest_image_status === "complete"
    );
  const someImagesReady = mergedScenes.some(
    (s) => s.latest_image_status === "ready" || s.latest_image_status === "complete"
  );

  return (
    <div className="space-y-5">
      {/* フィードバック */}
      {feedback && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm ${
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
              : "bg-red-500/10 text-red-400 border border-red-500/15"
          }`}
        >
          {feedback.type === "success" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-4 gap-5" style={{ minHeight: 600 }}>
        {/* 左: 台本選択サイドバー */}
        <div className="col-span-1 bg-[#0b1628] rounded-2xl border border-blue-400/[0.10] flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-blue-400/[0.10]">
            <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <BookOpen size={12} className="text-blue-400/70" />
              台本を選択
            </p>
          </div>

          {/* 台本一覧 */}
          <div className="flex-1 overflow-y-auto py-2 space-y-1 px-2">
            {storyboardsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={16} className="animate-spin text-slate-500" />
              </div>
            ) : storyboards.length === 0 ? (
              <div className="py-6 text-center px-3">
                <BookOpen size={20} className="mx-auto text-slate-700 mb-2" />
                <p className="text-xs text-slate-600">台本がありません</p>
              </div>
            ) : (
              storyboards.map((sb) => {
                const isSelected = selectedId === sb.id;
                const dayTheme = sb.day_of_week ? DAY_THEMES[sb.day_of_week] : undefined;
                return (
                  <button
                    key={sb.id}
                    onClick={() => handleSelectStoryboard(sb.id)}
                    className={`w-full text-left rounded-xl border transition-all px-3 py-2.5 ${
                      isSelected
                        ? "bg-blue-500/[0.15] border-blue-400/30"
                        : "bg-transparent border-transparent hover:bg-blue-400/[0.05] hover:border-blue-400/[0.08]"
                    }`}
                  >
                    <p className="text-xs font-medium text-slate-200 truncate">
                      {sb.title || `台本 #${sb.id}`}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1">
                      {dayTheme && <span className="text-[10px]">{dayTheme.icon}</span>}
                      <StatusBadge status={sb.status} />
                    </div>
                    <p className="text-[10px] text-slate-600 mt-1">
                      {new Date(sb.created_at).toLocaleDateString("ja-JP", { month: "short", day: "numeric" })}
                    </p>
                  </button>
                );
              })
            )}
          </div>

          {/* 新規台本作成 */}
          <div className="p-3 border-t border-blue-400/[0.10] space-y-2">
            <p className="text-[10px] text-slate-500 uppercase tracking-widest">新規作成</p>
            <div className="flex gap-1.5">
              {DAY_BUTTONS.map((d) => {
                const t = DAY_THEMES[d.key];
                return (
                  <button
                    key={d.key}
                    onClick={() => setNewDay(d.key)}
                    className={`flex-1 py-1.5 rounded-lg text-[10px] font-medium border transition-all ${
                      newDay === d.key ? "text-white" : "border-blue-400/[0.10] text-slate-500 hover:text-white"
                    }`}
                    style={
                      newDay === d.key
                        ? { backgroundColor: t?.color + "26", borderColor: t?.color + "60" }
                        : {}
                    }
                  >
                    {d.label}
                  </button>
                );
              })}
            </div>
            <select
              value={newProvider}
              onChange={(e) => setNewProvider(e.target.value)}
              className="w-full px-2 py-1.5 bg-[#132040] border border-blue-400/[0.12] rounded-lg text-xs text-white focus:border-blue-500/40 focus:outline-none"
            >
              <option value="gemini">Gemini Flash (標準)</option>
              <option value="gemini_pro">Gemini Pro (高品質)</option>
              <option value="imagen">Imagen 4 Fast (最速)</option>
            </select>
            <button
              onClick={handleCreateStoryboard}
              disabled={creating}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-xs transition-colors disabled:opacity-40"
            >
              {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
              台本を新規作成
            </button>
          </div>
        </div>

        {/* 右: ワークフロー */}
        <div className="col-span-3 space-y-4">
          {!storyboard && !storyboardLoading ? (
            <div className="bg-[#0b1628] rounded-2xl border border-blue-400/[0.10] flex flex-col items-center justify-center py-20 text-center">
              <BookOpen size={40} className="text-slate-700 mb-4" />
              <p className="text-slate-400 text-sm">左から台本を選択するか、新規作成してください</p>
              <p className="text-slate-600 text-xs mt-2">
                台本を選択すると画像→確認→動画のワークフローが利用できます
              </p>
            </div>
          ) : storyboardLoading ? (
            <div className="bg-[#0b1628] rounded-2xl border border-blue-400/[0.10] flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-slate-500" />
            </div>
          ) : storyboard ? (
            <>
              {/* 台本情報ヘッダー */}
              <div className="bg-[#0e1d32] rounded-2xl px-5 py-4 border border-blue-400/[0.10]">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-white">
                      {storyboard.title || `台本 #${storyboard.id}`}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      {storyboard.day_of_week && DAY_THEMES[storyboard.day_of_week] && (
                        <span className="text-sm">{DAY_THEMES[storyboard.day_of_week].icon}</span>
                      )}
                      <span className="text-xs text-slate-400">
                        {storyboard.day_of_week ? (DAY_THEMES[storyboard.day_of_week]?.dayJa ?? storyboard.day_of_week) : "テーマ未設定"}
                      </span>
                      <StatusBadge status={storyboard.status} />
                      <span className="text-xs text-slate-500">
                        {storyboard.scenes.length} シーン
                      </span>
                    </div>
                  </div>
                  <StepIndicator currentStep={step} />
                </div>
              </div>

              {/* Step 1: 画像生成 */}
              {step === 1 && (
                <Step1ImageGeneration
                  storyboard={storyboard}
                  imageProvider={imageProvider}
                  onImageProviderChange={setImageProvider}
                  generatingImages={generatingImages}
                  pollingImages={pollingImages}
                  genStatus={genStatus}
                  onGenerateImages={handleGenerateImages}
                  mergedScenes={mergedScenes}
                />
              )}

              {/* Step 2: 画像確認 */}
              {step === 2 && (
                <Step2ImageReview
                  storyboard={storyboard}
                  mergedScenes={mergedScenes}
                  regeneratingIds={regeneratingIds}
                  approving={approving}
                  allImagesReady={allImagesReady}
                  someImagesReady={someImagesReady}
                  onRegenerateScene={handleRegenerateScene}
                  onApproveImages={handleApproveImages}
                  onBack={() => setStep(1)}
                  onRefreshStatuses={async () => {
                    if (!storyboard) return;
                    const data = await fetchScenesStatus(storyboard.id);
                    setSceneStatuses(data.scenes);
                  }}
                />
              )}

              {/* Step 3: 動画生成 */}
              {step === 3 && (
                <Step3VideoGeneration
                  storyboard={storyboard}
                  generatingVideos={generatingVideos}
                  pollingVideos={pollingVideos}
                  videoStatus={videoStatus}
                  onGenerateVideos={handleGenerateVideos}
                  onBack={() => setStep(2)}
                />
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ── Step 1: 画像生成 ─────────────────────────────────────────

function Step1ImageGeneration({
  storyboard,
  imageProvider,
  onImageProviderChange,
  generatingImages,
  pollingImages,
  genStatus,
  onGenerateImages,
  mergedScenes,
}: {
  storyboard: StoryboardData;
  imageProvider: string;
  onImageProviderChange: (v: string) => void;
  generatingImages: boolean;
  pollingImages: boolean;
  genStatus: GenerationStatus | null;
  onGenerateImages: () => void;
  mergedScenes: Array<StoryboardScene & { latest_image_status: string; latest_image_path: string | null }>;
}) {
  const isRunning = generatingImages || pollingImages;

  return (
    <div className="space-y-4">
      {/* 設定 */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
          <ImageIcon size={12} className="text-blue-400/70" />
          ステップ 1 — 画像生成
        </h3>
        <p className="text-sm text-slate-400">
          台本の全 {storyboard.scenes.length} シーンの画像を一括生成します。
          生成後に各シーンの画像を確認・再生成することができます。
        </p>

        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1.5">画像生成プロバイダー</label>
            <select
              value={imageProvider}
              onChange={(e) => onImageProviderChange(e.target.value)}
              disabled={isRunning}
              className="w-full px-3 py-2.5 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none disabled:opacity-50"
            >
              <option value="gemini">Gemini Flash (標準)</option>
              <option value="gemini_pro">Gemini Pro (高品質)</option>
              <option value="imagen">Imagen 4 Fast (最速)</option>
            </select>
          </div>
          <button
            onClick={onGenerateImages}
            disabled={isRunning}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: isRunning ? "none" : "0 0 20px rgba(59,130,246,0.25)" }}
          >
            {isRunning ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Sparkles size={16} />
            )}
            {isRunning ? "生成中..." : "全シーン画像生成"}
          </button>
        </div>
      </div>

      {/* 生成状況 */}
      {(generatingImages || pollingImages || genStatus) && (
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
            生成状況
          </h4>
          {genStatus ? (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">
                  {genStatus.completed_scenes} / {genStatus.total_scenes} シーン完了
                </span>
                <StatusBadge status={genStatus.status} />
              </div>
              <div className="w-full bg-[#132040] rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{
                    width: genStatus.total_scenes > 0
                      ? `${(genStatus.completed_scenes / genStatus.total_scenes) * 100}%`
                      : "0%",
                  }}
                />
              </div>
              {genStatus.estimated_remaining_seconds != null && (
                <p className="text-xs text-slate-500">
                  推定残り時間: 約{Math.round(genStatus.estimated_remaining_seconds)}秒
                </p>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 size={14} className="animate-spin text-blue-400" />
              画像生成を開始しています...
            </div>
          )}
        </div>
      )}

      {/* シーン画像グリッド — 生成中はリアルタイムでプレビュー表示 */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
          シーン一覧 ({storyboard.scenes.length} シーン)
          {isRunning && (
            <span className="ml-2 text-blue-400 normal-case font-normal">
              — 生成完了したシーンから順次表示されます
            </span>
          )}
        </h4>
        <div className="grid grid-cols-2 gap-3">
          {mergedScenes.map((scene, idx) => {
            const imageReady =
              scene.latest_image_status === "ready" || scene.latest_image_status === "complete";
            const isGeneratingScene =
              scene.latest_image_status === "generating" || scene.latest_image_status === "pending";
            const isFailed = scene.latest_image_status === "failed";

            return (
              <div
                key={scene.id}
                className="bg-[#132040] rounded-xl border border-blue-400/[0.08] overflow-hidden"
              >
                {/* 画像エリア */}
                <div className="relative bg-[#0b1628] flex items-center justify-center" style={{ height: 100 }}>
                  {imageReady && scene.latest_image_path ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      key={scene.latest_image_path}
                      src={`${API_BASE}${scene.latest_image_path}?t=${encodeURIComponent(scene.updated_at ?? scene.latest_image_path)}`}
                      alt={`シーン ${idx + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  ) : isGeneratingScene ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5">
                      <div className="absolute inset-0 bg-blue-500/5 animate-pulse" />
                      <Loader2 size={16} className="animate-spin text-blue-400 relative" />
                      <span className="text-[10px] text-slate-500 relative">生成中...</span>
                    </div>
                  ) : isFailed ? (
                    <div className="flex flex-col items-center gap-1 text-red-400">
                      <span className="text-[10px]">生成に失敗</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-1 text-slate-600">
                      <ImageIcon size={18} />
                      <span className="text-[10px]">待機中</span>
                    </div>
                  )}
                  <div className="absolute top-1.5 left-1.5">
                    <StatusBadge status={scene.latest_image_status} />
                  </div>
                </div>
                {/* シーン情報 */}
                <div className="flex items-center gap-2 px-3 py-2">
                  <span className="text-[10px] text-slate-600 font-mono flex-shrink-0">
                    #{idx + 1}
                  </span>
                  <p className="text-[11px] text-slate-300 truncate">
                    {COURSE_LABELS[scene.course_key] ?? scene.course_key}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Step 2: 画像確認 ─────────────────────────────────────────

function Step2ImageReview({
  storyboard,
  mergedScenes,
  regeneratingIds,
  approving,
  allImagesReady,
  someImagesReady,
  onRegenerateScene,
  onApproveImages,
  onBack,
  onRefreshStatuses,
}: {
  storyboard: StoryboardData;
  mergedScenes: Array<StoryboardScene & { latest_image_status: string; latest_image_path: string | null }>;
  regeneratingIds: Set<number>;
  approving: boolean;
  allImagesReady: boolean;
  someImagesReady: boolean;
  onRegenerateScene: (sceneId: number) => void;
  onApproveImages: () => void;
  onBack: () => void;
  onRefreshStatuses: () => Promise<void>;
}) {
  const API_BASE_LOCAL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await onRefreshStatuses();
    } finally {
      setRefreshing(false);
    }
  }

  const readyCount = mergedScenes.filter(
    (s) => s.latest_image_status === "ready" || s.latest_image_status === "complete"
  ).length;

  return (
    <div className="space-y-4">
      {/* ヘッダーアクション */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
            <ImageIcon size={12} className="text-blue-400/70" />
            ステップ 2 — 画像確認
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">
              {readyCount} / {mergedScenes.length} シーン完了
            </span>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-1 px-2.5 py-1.5 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-xs transition-colors"
            >
              <RefreshCw size={11} className={refreshing ? "animate-spin" : ""} />
              更新
            </button>
          </div>
        </div>
        <p className="text-sm text-slate-400">
          各シーンの生成画像を確認してください。問題があるシーンは個別に再生成できます。
          すべて確認したら「画像を承認して動画生成へ」をクリックしてください。
        </p>

        {!allImagesReady && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/[0.08] border border-amber-500/[0.15] rounded-xl text-xs text-amber-400">
            <AlertCircle size={14} />
            一部のシーンで画像がまだ生成されていません。再生成ボタンで個別に生成するか、しばらく待ってから更新してください。
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-300 rounded-xl text-sm transition-colors"
          >
            戻る
          </button>
          <button
            onClick={onApproveImages}
            disabled={approving || (!allImagesReady && !someImagesReady)}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: approving ? "none" : "0 0 20px rgba(59,130,246,0.20)" }}
          >
            {approving ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                <Check size={16} />
                <ChevronRight size={14} />
              </>
            )}
            {approving ? "承認中..." : "画像を承認して動画生成へ"}
          </button>
        </div>
      </div>

      {/* 画像グリッド */}
      <div className="grid grid-cols-2 gap-4">
        {mergedScenes.map((scene, idx) => {
          const isRegenerating = regeneratingIds.has(scene.id);
          const imageReady =
            scene.latest_image_status === "ready" || scene.latest_image_status === "complete";

          return (
            <div
              key={scene.id}
              className="bg-[#0e1d32] rounded-2xl border border-blue-400/[0.10] overflow-hidden"
            >
              {/* 画像エリア */}
              <div
                className="relative bg-[#0b1628] flex items-center justify-center"
                style={{ height: 160 }}
              >
                {imageReady && scene.latest_image_path ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    key={scene.latest_image_path}
                    src={`${API_BASE_LOCAL}${scene.latest_image_path}?t=${encodeURIComponent(scene.updated_at ?? scene.latest_image_path)}`}
                    alt={`シーン ${idx + 1}`}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : isRegenerating ? (
                  <div className="flex flex-col items-center gap-2 text-slate-500">
                    <Loader2 size={24} className="animate-spin text-blue-400" />
                    <span className="text-xs">再生成中...</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 text-slate-600">
                    <ImageIcon size={24} />
                    <span className="text-xs">
                      {scene.latest_image_status === "generating" ? "生成中..." : "未生成"}
                    </span>
                  </div>
                )}
                {/* ステータスオーバーレイ */}
                <div className="absolute top-2 left-2">
                  <StatusBadge status={scene.latest_image_status} />
                </div>
              </div>

              {/* シーン情報 */}
              <div className="p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-500 font-mono">#{idx + 1}</span>
                    <span className="text-xs text-slate-300 ml-2">
                      {COURSE_LABELS[scene.course_key] ?? scene.course_key}
                    </span>
                  </div>
                  <button
                    onClick={() => onRegenerateScene(scene.id)}
                    disabled={isRegenerating}
                    className="flex items-center gap-1 px-2 py-1 bg-blue-400/[0.08] hover:bg-blue-400/[0.15] text-slate-400 hover:text-blue-400 rounded-lg text-[10px] transition-colors disabled:opacity-40"
                  >
                    <RefreshCw size={10} className={isRegenerating ? "animate-spin" : ""} />
                    再生成
                  </button>
                </div>
                {scene.scene_description_ja && (
                  <p className="text-[10px] text-slate-500 truncate">
                    {scene.scene_description_ja}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 3: 動画生成 ─────────────────────────────────────────

function Step3VideoGeneration({
  storyboard,
  generatingVideos,
  pollingVideos,
  videoStatus,
  onGenerateVideos,
  onBack,
}: {
  storyboard: StoryboardData;
  generatingVideos: boolean;
  pollingVideos: boolean;
  videoStatus: GenerationStatus | null;
  onGenerateVideos: () => void;
  onBack: () => void;
}) {
  const isRunning = generatingVideos || pollingVideos;

  const readyCount = storyboard.scenes.filter((s) => s.video_status === "ready").length;
  const allVideosReady = readyCount === storyboard.scenes.length;

  return (
    <div className="space-y-4">
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
          <Video size={12} className="text-blue-400/70" />
          ステップ 3 — 動画生成
        </h3>
        <p className="text-sm text-slate-400">
          承認済みの画像から動画を生成します。
          全 {storyboard.scenes.length} シーンの動画生成を開始します。
        </p>

        {allVideosReady && (
          <div className="flex items-center gap-2 px-3 py-2 bg-emerald-500/[0.08] border border-emerald-500/[0.15] rounded-xl text-xs text-emerald-400">
            <CheckCircle2 size={14} />
            全シーンの動画生成が完了しています！
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-300 rounded-xl text-sm transition-colors"
          >
            戻る
          </button>
          <button
            onClick={onGenerateVideos}
            disabled={isRunning}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: isRunning ? "none" : "0 0 20px rgba(59,130,246,0.25)" }}
          >
            {isRunning ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            {isRunning ? "生成中..." : "全シーン動画生成"}
          </button>
        </div>
      </div>

      {/* 動画生成状況 */}
      {(generatingVideos || pollingVideos || videoStatus) && (
        <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
          <h4 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
            生成状況
          </h4>
          {videoStatus ? (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">
                  {videoStatus.completed_scenes} / {videoStatus.total_scenes} シーン完了
                </span>
                <StatusBadge status={videoStatus.status} />
              </div>
              <div className="w-full bg-[#132040] rounded-full h-2">
                <div
                  className="bg-purple-500 h-2 rounded-full transition-all"
                  style={{
                    width: videoStatus.total_scenes > 0
                      ? `${(videoStatus.completed_scenes / videoStatus.total_scenes) * 100}%`
                      : "0%",
                  }}
                />
              </div>
              {videoStatus.estimated_remaining_seconds != null && (
                <p className="text-xs text-slate-500">
                  推定残り時間: 約{Math.round(videoStatus.estimated_remaining_seconds)}秒
                </p>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 size={14} className="animate-spin text-purple-400" />
              動画生成を開始しています...
            </div>
          )}
        </div>
      )}

      {/* シーン動画ステータス一覧 */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
          シーン動画ステータス ({readyCount}/{storyboard.scenes.length} 完了)
        </h4>
        <div className="grid grid-cols-2 gap-3">
          {storyboard.scenes.map((scene, idx) => (
            <div
              key={scene.id}
              className="flex items-center gap-3 p-3 bg-[#132040] rounded-xl border border-blue-400/[0.08]"
            >
              <div className="w-12 h-8 bg-[#0b1628] rounded flex items-center justify-center flex-shrink-0">
                {scene.video_status === "ready" ? (
                  <Play size={12} className="text-emerald-400" />
                ) : scene.video_status === "generating" ? (
                  <Loader2 size={12} className="animate-spin text-purple-400" />
                ) : (
                  <Video size={12} className="text-slate-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-slate-300 truncate">
                  {idx + 1}. {COURSE_LABELS[scene.course_key] ?? scene.course_key}
                </p>
              </div>
              <StatusBadge status={scene.video_status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
