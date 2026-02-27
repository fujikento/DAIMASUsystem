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
  CheckSquare,
  Square,
  CheckCircle2,
  XCircle,
  Play,
  Zap,
} from "lucide-react";
import {
  fetchStoryboards,
  fetchStoryboard,
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
    { id: 1 as WorkflowStep, label: "① 画像生成", desc: "全台本の画像を一括生成" },
    { id: 2 as WorkflowStep, label: "② 画像確認", desc: "台本ごとに画像を確認・承認" },
    { id: 3 as WorkflowStep, label: "③ 動画生成", desc: "承認済み台本の動画を生成" },
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

// ── 台本ごとの状態 ────────────────────────────────────────────

interface StoryboardBatchState {
  id: number;
  data: StoryboardData | null;
  loading: boolean;
  imageGenStatus: GenerationStatus | null;
  videoGenStatus: GenerationStatus | null;
  sceneStatuses: Array<{
    id: number;
    image_status: string;
    image_path: string | null;
    video_status: string;
    video_path: string | null;
  }>;
  approved: boolean;
  regeneratingIds: Set<number>;
}

// ── メインコンポーネント ──────────────────────────────────────

interface BatchGenerationTabProps {
  themes: GenerationThemes | null;
}

export default function BatchGenerationTab({ themes }: BatchGenerationTabProps) {
  const [step, setStep] = useState<WorkflowStep>(1);
  const [storyboards, setStoryboards] = useState<StoryboardListItem[]>([]);
  const [storyboardsLoading, setStoryboardsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchStates, setBatchStates] = useState<Record<number, StoryboardBatchState>>({});

  // 画像生成設定
  const [imageProvider, setImageProvider] = useState("gemini");

  // 一括処理の状態
  const [batchImageGenerating, setBatchImageGenerating] = useState(false);
  const [batchVideoGenerating, setBatchVideoGenerating] = useState(false);
  const [batchApproving, setBatchApproving] = useState(false);

  // 展開表示する台本 (Step 2での画像グリッド表示)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  // フィードバック
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showFeedback = useCallback((type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 5000);
  }, []);

  // 台本一覧を読み込む
  useEffect(() => {
    setStoryboardsLoading(true);
    fetchStoryboards()
      .then(setStoryboards)
      .catch(() => showFeedback("error", "台本一覧の取得に失敗しました"))
      .finally(() => setStoryboardsLoading(false));
  }, [showFeedback]);

  // SSE購読: バックエンドからリアルタイムで選択中台本のシーン更新を受け取る
  const selectedIdsRef = useRef(selectedIds);
  selectedIdsRef.current = selectedIds;
  const setBatchStatesRef = useRef(setBatchStates);
  setBatchStatesRef.current = setBatchStates;

  useEffect(() => {
    const unsubscribe = subscribeToStoryboardEvents((event) => {
      if (event.type === "scene_updated") {
        // 選択中の台本のシーンのみ更新
        if (!selectedIdsRef.current.has(event.storyboard_id)) return;
        setBatchStatesRef.current((prev) => {
          const state = prev[event.storyboard_id];
          if (!state) return prev;
          return {
            ...prev,
            [event.storyboard_id]: {
              ...state,
              sceneStatuses: state.sceneStatuses.map((s) =>
                s.id === event.scene_id
                  ? {
                      ...s,
                      ...(event.image_status !== undefined && { image_status: event.image_status! }),
                      ...(event.image_path !== undefined && { image_path: event.image_path ?? s.image_path }),
                    }
                  : s
              ),
              data: state.data
                ? {
                    ...state.data,
                    scenes: state.data.scenes.map((scene) =>
                      scene.id === event.scene_id
                        ? {
                            ...scene,
                            ...(event.image_status !== undefined && { image_status: event.image_status! }),
                            ...(event.image_path !== undefined && { image_path: event.image_path ?? scene.image_path }),
                          }
                        : scene
                    ),
                  }
                : null,
            },
          };
        });
      }

      if (event.type === "storyboard_updated") {
        if (!selectedIdsRef.current.has(event.storyboard_id)) return;
        // 選択中台本の全データを再取得して同期
        fetchStoryboard(event.storyboard_id)
          .then((data) => {
            setBatchStatesRef.current((prev) => ({
              ...prev,
              [event.storyboard_id]: {
                ...prev[event.storyboard_id],
                data,
                sceneStatuses: data.scenes.map((s) => ({
                  id: s.id,
                  image_status: s.image_status,
                  image_path: s.image_path,
                  video_status: s.video_status,
                  video_path: s.video_path,
                })),
              },
            }));
          })
          .catch((e) => console.error("[SSE] batch storyboard_updated fetch failed:", e));
      }
    });

    // コンポーネントのアンマウント時にSSE接続を閉じる
    return () => unsubscribe();
  }, []);

  // 選択台本の詳細を読み込む
  useEffect(() => {
    for (const id of selectedIds) {
      if (!batchStates[id]) {
        setBatchStates((prev) => ({
          ...prev,
          [id]: {
            id,
            data: null,
            loading: true,
            imageGenStatus: null,
            videoGenStatus: null,
            sceneStatuses: [],
            approved: false,
            regeneratingIds: new Set(),
          },
        }));
        fetchStoryboard(id)
          .then((data) => {
            setBatchStates((prev) => ({
              ...prev,
              [id]: { ...prev[id], data, loading: false },
            }));
          })
          .catch(() => {
            setBatchStates((prev) => ({
              ...prev,
              [id]: { ...prev[id], loading: false },
            }));
          });
      }
    }
  }, [selectedIds, batchStates]);

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleExpand(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  // Step 1: 選択した全台本の画像を一括生成
  async function handleBatchGenerateImages() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setBatchImageGenerating(true);

    try {
      // 並列で全台本の画像生成を開始
      await Promise.allSettled(
        ids.map((id) => generateStoryboardImages(id, imageProvider))
      );
      showFeedback("success", `${ids.length}件の台本で画像生成を開始しました`);

      // 各台本のポーリングを開始
      for (const id of ids) {
        startPollingImages(id);
      }
    } catch {
      showFeedback("error", "画像生成の開始に失敗しました");
      setBatchImageGenerating(false);
    }
  }

  // SSEがシーン個別の完了通知をリアルタイムで届けるため、ここでは全体進捗確認に留める。
  // 間隔を1000ms→3000msに緩め、scenes/statusの並列取得を廃止してサーバー負荷を削減。
  function startPollingImages(sbId: number) {
    let completed = false;
    const interval = setInterval(async () => {
      try {
        // SSE handles per-scene updates; only poll overall status here
        const status = await fetchGenerationStatus(sbId);
        setBatchStates((prev) => ({
          ...prev,
          [sbId]: {
            ...prev[sbId],
            imageGenStatus: status,
          },
        }));
        if (status.status === "idle") {
          // Fetch scene statuses once on completion to get final state
          const scenesData = await fetchScenesStatus(sbId);
          setBatchStates((prev) => ({
            ...prev,
            [sbId]: {
              ...prev[sbId],
              sceneStatuses: scenesData?.scenes ?? prev[sbId]?.sceneStatuses ?? [],
            },
          }));
          clearInterval(interval);
          completed = true;
        }
      } catch {
        clearInterval(interval);
        completed = true;
      }
      // 全台本のポーリングが終わったか確認
      if (completed) {
        setBatchStates((prev) => {
          const allDone = Array.from(selectedIds).every((id) => {
            const s = prev[id]?.imageGenStatus;
            return !s || s.status === "idle";
          });
          if (allDone) {
            setBatchImageGenerating(false);
            showFeedback("success", "全台本の画像生成が完了しました。画像を確認してください");
            setStep(2);
          }
          return prev;
        });
      }
    }, 3000);
  }

  // Step 2: 個別シーンの再生成
  async function handleRegenerateScene(sbId: number, sceneId: number) {
    setBatchStates((prev) => {
      const state = prev[sbId];
      if (!state) return prev;
      const newRegeneratingIds = new Set(state.regeneratingIds);
      newRegeneratingIds.add(sceneId);
      return { ...prev, [sbId]: { ...state, regeneratingIds: newRegeneratingIds } };
    });
    try {
      await regenerateSceneImage(sbId, sceneId, imageProvider);
      setTimeout(async () => {
        try {
          const scenes = await fetchScenesStatus(sbId);
          setBatchStates((prev) => {
            const state = prev[sbId];
            if (!state) return prev;
            const newRegeneratingIds = new Set(state.regeneratingIds);
            newRegeneratingIds.delete(sceneId);
            return { ...prev, [sbId]: { ...state, sceneStatuses: scenes.scenes, regeneratingIds: newRegeneratingIds } };
          });
        } catch {
          setBatchStates((prev) => {
            const state = prev[sbId];
            if (!state) return prev;
            const newRegeneratingIds = new Set(state.regeneratingIds);
            newRegeneratingIds.delete(sceneId);
            return { ...prev, [sbId]: { ...state, regeneratingIds: newRegeneratingIds } };
          });
        }
      }, 6000);
    } catch {
      showFeedback("error", "再生成に失敗しました");
      setBatchStates((prev) => {
        const state = prev[sbId];
        if (!state) return prev;
        const newRegeneratingIds = new Set(state.regeneratingIds);
        newRegeneratingIds.delete(sceneId);
        return { ...prev, [sbId]: { ...state, regeneratingIds: newRegeneratingIds } };
      });
    }
  }

  // Step 2: 台本単位で画像を承認
  async function handleApproveStoryboard(sbId: number) {
    try {
      await approveStoryboardImages(sbId);
      const refreshed = await fetchStoryboard(sbId);
      setBatchStates((prev) => ({
        ...prev,
        [sbId]: { ...prev[sbId], data: refreshed, approved: true },
      }));
      showFeedback("success", "台本の画像を承認しました");
    } catch {
      showFeedback("error", "承認に失敗しました");
    }
  }

  // Step 2: 全台本を一括承認して次へ
  async function handleApproveAll() {
    setBatchApproving(true);
    const ids = Array.from(selectedIds);
    let successCount = 0;
    for (const id of ids) {
      try {
        await approveStoryboardImages(id);
        const refreshed = await fetchStoryboard(id);
        setBatchStates((prev) => ({
          ...prev,
          [id]: { ...prev[id], data: refreshed, approved: true },
        }));
        successCount++;
      } catch {}
    }
    setBatchApproving(false);
    if (successCount > 0) {
      showFeedback("success", `${successCount}件の台本を承認しました`);
      setStep(3);
    } else {
      showFeedback("error", "承認に失敗しました");
    }
  }

  // Step 3: 全台本の動画を一括生成
  async function handleBatchGenerateVideos() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setBatchVideoGenerating(true);

    try {
      await Promise.allSettled(
        ids.map((id) => generateStoryboardVideos(id))
      );
      showFeedback("success", `${ids.length}件の台本で動画生成を開始しました`);

      for (const id of ids) {
        startPollingVideos(id);
      }
    } catch {
      showFeedback("error", "動画生成の開始に失敗しました");
      setBatchVideoGenerating(false);
    }
  }

  function startPollingVideos(sbId: number) {
    let completed = false;
    const interval = setInterval(async () => {
      try {
        const status = await fetchGenerationStatus(sbId);
        setBatchStates((prev) => ({
          ...prev,
          [sbId]: { ...prev[sbId], videoGenStatus: status },
        }));
        if (status.status === "idle") {
          clearInterval(interval);
          completed = true;
          const refreshed = await fetchStoryboard(sbId);
          setBatchStates((prev) => ({
            ...prev,
            [sbId]: { ...prev[sbId], data: refreshed },
          }));
        }
      } catch {
        clearInterval(interval);
        completed = true;
      }
      if (completed) {
        setBatchStates((prev) => {
          const allDone = Array.from(selectedIds).every((id) => {
            const s = prev[id]?.videoGenStatus;
            return !s || s.status === "idle";
          });
          if (allDone) {
            setBatchVideoGenerating(false);
            showFeedback("success", "全台本の動画生成が完了しました！");
          }
          return prev;
        });
      }
    }, 4000);
  }

  const selectedCount = selectedIds.size;
  const selectedArray = Array.from(selectedIds);

  const allApproved =
    selectedArray.length > 0 &&
    selectedArray.every((id) => batchStates[id]?.approved);

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

      {/* ステップインジケーター & 選択数 */}
      <div className="bg-[#0e1d32] rounded-2xl px-5 py-4 border border-blue-400/[0.10]">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">一括生成ワークフロー</h3>
            <p className="text-xs text-slate-500 mt-1">
              {selectedCount > 0
                ? `${selectedCount}件の台本を選択中`
                : "台本を選択してください"}
            </p>
          </div>
          <StepIndicator currentStep={step} />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-5">
        {/* 左: 台本選択サイドバー */}
        <div className="col-span-1 bg-[#0b1628] rounded-2xl border border-blue-400/[0.10] flex flex-col overflow-hidden" style={{ minHeight: 500 }}>
          <div className="px-4 py-3 border-b border-blue-400/[0.10] flex items-center justify-between">
            <p className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <BookOpen size={12} className="text-blue-400/70" />
              台本を選択
            </p>
            {selectedCount > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 font-medium">
                {selectedCount}件
              </span>
            )}
          </div>

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
                const isSelected = selectedIds.has(sb.id);
                const dayTheme = sb.day_of_week ? DAY_THEMES[sb.day_of_week] : undefined;
                return (
                  <button
                    key={sb.id}
                    onClick={() => toggleSelect(sb.id)}
                    className={`w-full text-left rounded-xl border transition-all px-3 py-2.5 flex items-start gap-2 ${
                      isSelected
                        ? "bg-blue-500/[0.15] border-blue-400/30"
                        : "bg-transparent border-transparent hover:bg-blue-400/[0.05] hover:border-blue-400/[0.08]"
                    }`}
                  >
                    <div className="flex-shrink-0 mt-0.5 text-blue-400">
                      {isSelected ? <CheckSquare size={13} /> : <Square size={13} className="text-slate-600" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">
                        {sb.title || `台本 #${sb.id}`}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        {dayTheme && <span className="text-[10px]">{dayTheme.icon}</span>}
                        <StatusBadge status={sb.status} />
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* 全選択/解除 */}
          {storyboards.length > 0 && (
            <div className="p-3 border-t border-blue-400/[0.10] flex gap-2">
              <button
                onClick={() => setSelectedIds(new Set(storyboards.map((sb) => sb.id)))}
                className="flex-1 px-2 py-1.5 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-[10px] transition-colors"
              >
                全選択
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="flex-1 px-2 py-1.5 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-[10px] transition-colors"
              >
                解除
              </button>
            </div>
          )}
        </div>

        {/* 右: ワークフロー */}
        <div className="col-span-3 space-y-4">
          {selectedCount === 0 ? (
            <div className="bg-[#0b1628] rounded-2xl border border-blue-400/[0.10] flex flex-col items-center justify-center py-20 text-center">
              <Zap size={40} className="text-slate-700 mb-4" />
              <p className="text-slate-400 text-sm">台本を選択してください</p>
              <p className="text-slate-600 text-xs mt-2">
                複数の台本を選択すると一括で画像→確認→動画の生成が行えます
              </p>
            </div>
          ) : (
            <>
              {/* Step 1: 画像一括生成 */}
              {step === 1 && (
                <BatchStep1
                  selectedIds={selectedArray}
                  batchStates={batchStates}
                  imageProvider={imageProvider}
                  onImageProviderChange={setImageProvider}
                  batchImageGenerating={batchImageGenerating}
                  onGenerateImages={handleBatchGenerateImages}
                />
              )}

              {/* Step 2: 画像確認 */}
              {step === 2 && (
                <BatchStep2
                  selectedIds={selectedArray}
                  batchStates={batchStates}
                  expandedIds={expandedIds}
                  batchApproving={batchApproving}
                  allApproved={allApproved}
                  onToggleExpand={toggleExpand}
                  onRegenerateScene={handleRegenerateScene}
                  onApproveStoryboard={handleApproveStoryboard}
                  onApproveAll={handleApproveAll}
                  onBack={() => setStep(1)}
                  onRefreshStatuses={async (sbId) => {
                    const scenes = await fetchScenesStatus(sbId);
                    setBatchStates((prev) => ({
                      ...prev,
                      [sbId]: { ...prev[sbId], sceneStatuses: scenes.scenes },
                    }));
                  }}
                />
              )}

              {/* Step 3: 動画一括生成 */}
              {step === 3 && (
                <BatchStep3
                  selectedIds={selectedArray}
                  batchStates={batchStates}
                  batchVideoGenerating={batchVideoGenerating}
                  onGenerateVideos={handleBatchGenerateVideos}
                  onBack={() => setStep(2)}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Step 1: 画像一括生成 ────────────────────────────────────

function BatchStep1({
  selectedIds,
  batchStates,
  imageProvider,
  onImageProviderChange,
  batchImageGenerating,
  onGenerateImages,
}: {
  selectedIds: number[];
  batchStates: Record<number, StoryboardBatchState>;
  imageProvider: string;
  onImageProviderChange: (v: string) => void;
  batchImageGenerating: boolean;
  onGenerateImages: () => void;
}) {
  const totalScenes = selectedIds.reduce((sum, id) => {
    const data = batchStates[id]?.data;
    return sum + (data?.scenes.length ?? 0);
  }, 0);

  return (
    <div className="space-y-4">
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
          <ImageIcon size={12} className="text-blue-400/70" />
          ステップ 1 — 画像一括生成
        </h3>
        <p className="text-sm text-slate-400">
          選択した {selectedIds.length} 件の台本（合計 {totalScenes} シーン）の画像を一括生成します。
        </p>

        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1.5">画像生成プロバイダー</label>
            <select
              value={imageProvider}
              onChange={(e) => onImageProviderChange(e.target.value)}
              disabled={batchImageGenerating}
              className="w-full px-3 py-2.5 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none disabled:opacity-50"
            >
              <option value="gemini">Gemini Flash (標準)</option>
              <option value="gemini_pro">Gemini Pro (高品質)</option>
              <option value="imagen">Imagen 4 Fast (最速)</option>
            </select>
          </div>
          <button
            onClick={onGenerateImages}
            disabled={batchImageGenerating || selectedIds.some((id) => !batchStates[id]?.data)}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: batchImageGenerating ? "none" : "0 0 20px rgba(59,130,246,0.25)" }}
          >
            {batchImageGenerating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Sparkles size={16} />
            )}
            {batchImageGenerating ? "生成中..." : "全台本の画像を一括生成"}
          </button>
        </div>
      </div>

      {/* 台本ごとの状況 */}
      <div className="space-y-2">
        {selectedIds.map((id) => {
          const state = batchStates[id];
          const sb = storyboards_from_state(state);
          const genStatus = state?.imageGenStatus;

          return (
            <div key={id} className="bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.10]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {state?.loading ? (
                    <Loader2 size={14} className="animate-spin text-slate-500" />
                  ) : (
                    <BookOpen size={14} className="text-blue-400/60" />
                  )}
                  <span className="text-sm text-slate-200">
                    {sb?.title || `台本 #${id}`}
                  </span>
                  {sb && <StatusBadge status={sb.status} />}
                </div>
                <span className="text-xs text-slate-500">
                  {sb ? `${sb.scenes.length} シーン` : "読み込み中..."}
                </span>
              </div>

              {genStatus && (
                <div className="mt-3 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {genStatus.completed_scenes} / {genStatus.total_scenes} 完了
                    </span>
                    <StatusBadge status={genStatus.status} />
                  </div>
                  <div className="w-full bg-[#132040] rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all"
                      style={{
                        width: genStatus.total_scenes > 0
                          ? `${(genStatus.completed_scenes / genStatus.total_scenes) * 100}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 2: 画像確認 ─────────────────────────────────────────

function BatchStep2({
  selectedIds,
  batchStates,
  expandedIds,
  batchApproving,
  allApproved,
  onToggleExpand,
  onRegenerateScene,
  onApproveStoryboard,
  onApproveAll,
  onBack,
  onRefreshStatuses,
}: {
  selectedIds: number[];
  batchStates: Record<number, StoryboardBatchState>;
  expandedIds: Set<number>;
  batchApproving: boolean;
  allApproved: boolean;
  onToggleExpand: (id: number) => void;
  onRegenerateScene: (sbId: number, sceneId: number) => void;
  onApproveStoryboard: (id: number) => void;
  onApproveAll: () => void;
  onBack: () => void;
  onRefreshStatuses: (sbId: number) => Promise<void>;
}) {
  const API_BASE_LOCAL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const approvedCount = selectedIds.filter((id) => batchStates[id]?.approved).length;

  return (
    <div className="space-y-4">
      {/* ヘッダー */}
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
          <ImageIcon size={12} className="text-blue-400/70" />
          ステップ 2 — 画像確認
        </h3>
        <p className="text-sm text-slate-400">
          各台本の生成画像を確認し、台本ごとに承認してください。
          {approvedCount} / {selectedIds.length} 件承認済み
        </p>

        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-300 rounded-xl text-sm transition-colors"
          >
            戻る
          </button>
          <button
            onClick={onApproveAll}
            disabled={batchApproving}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: batchApproving ? "none" : "0 0 20px rgba(59,130,246,0.20)" }}
          >
            {batchApproving ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                <Check size={16} />
                <ChevronRight size={14} />
              </>
            )}
            {batchApproving ? "承認中..." : "全台本を承認して動画生成へ"}
          </button>
        </div>
      </div>

      {/* 台本ごとの画像確認 */}
      <div className="space-y-3">
        {selectedIds.map((sbId) => {
          const state = batchStates[sbId];
          const sb = storyboards_from_state(state);
          const isExpanded = expandedIds.has(sbId);
          const isApproved = state?.approved ?? false;

          return (
            <div key={sbId} className="bg-[#0e1d32] rounded-2xl border border-blue-400/[0.10] overflow-hidden">
              {/* 台本ヘッダー */}
              <div
                className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-blue-400/[0.03] transition-colors"
                onClick={() => onToggleExpand(sbId)}
              >
                <ChevronRight
                  size={14}
                  className={`text-slate-500 transition-transform flex-shrink-0 ${isExpanded ? "rotate-90" : ""}`}
                />
                <BookOpen size={14} className="text-blue-400/60 flex-shrink-0" />
                <span className="text-sm font-medium text-slate-200 flex-1 truncate">
                  {sb?.title || `台本 #${sbId}`}
                </span>
                {sb && <StatusBadge status={sb.status} />}
                {isApproved && (
                  <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                    <CheckCircle2 size={12} />
                    承認済み
                  </span>
                )}
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => onRefreshStatuses(sbId)}
                    className="p-1.5 text-slate-500 hover:text-blue-400 transition-colors"
                    title="ステータス更新"
                  >
                    <RefreshCw size={12} />
                  </button>
                  {!isApproved && (
                    <button
                      onClick={() => onApproveStoryboard(sbId)}
                      className="flex items-center gap-1 px-2.5 py-1 bg-emerald-500/[0.10] hover:bg-emerald-500/[0.20] text-emerald-400 rounded-lg text-[10px] transition-colors border border-emerald-500/[0.15]"
                    >
                      <Check size={10} />
                      この台本を承認
                    </button>
                  )}
                </div>
              </div>

              {/* 展開: 画像グリッド */}
              {isExpanded && sb && (
                <div className="border-t border-blue-400/[0.08] p-4">
                  <div className="grid grid-cols-3 gap-3">
                    {sb.scenes.map((scene, idx) => {
                      const sceneStatus = state?.sceneStatuses.find((s) => s.id === scene.id);
                      const imageStatus = sceneStatus?.image_status ?? scene.image_status;
                      const isRegenerating = state?.regeneratingIds.has(scene.id) ?? false;
                      const imageReady = imageStatus === "ready" || imageStatus === "complete";
                      const imagePath = sceneStatus?.image_path ?? scene.image_path;
                      const imageUpdatedAt = scene.updated_at;

                      return (
                        <div
                          key={scene.id}
                          className="bg-[#0b1628] rounded-xl border border-blue-400/[0.08] overflow-hidden"
                        >
                          {/* 画像エリア */}
                          <div
                            className="relative flex items-center justify-center bg-[#080f1a]"
                            style={{ height: 100 }}
                          >
                            {imageReady && imagePath ? (
                              /* eslint-disable-next-line @next/next/no-img-element */
                              <img
                                key={imagePath}
                                src={`${API_BASE_LOCAL}${imagePath}?t=${encodeURIComponent(imageUpdatedAt ?? imagePath)}`}
                                alt={`シーン ${idx + 1}`}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = "none";
                                }}
                              />
                            ) : isRegenerating ? (
                              <Loader2 size={18} className="animate-spin text-blue-400" />
                            ) : imageStatus === "generating" || imageStatus === "pending" ? (
                              <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5">
                                <div className="absolute inset-0 bg-blue-500/5 animate-pulse" />
                                <Loader2 size={16} className="animate-spin text-blue-400 relative" />
                                <span className="text-[10px] text-slate-500 relative">生成中...</span>
                              </div>
                            ) : (
                              <ImageIcon size={18} className="text-slate-700" />
                            )}
                            <div className="absolute top-1 left-1">
                              <StatusBadge status={imageStatus} />
                            </div>
                          </div>
                          {/* シーン情報 */}
                          <div className="p-2 flex items-center justify-between gap-2">
                            <p className="text-[10px] text-slate-400 truncate flex-1">
                              {idx + 1}. {COURSE_LABELS[scene.course_key] ?? scene.course_key}
                            </p>
                            <button
                              onClick={() => onRegenerateScene(sbId, scene.id)}
                              disabled={isRegenerating}
                              className="flex-shrink-0 p-1 text-slate-600 hover:text-blue-400 transition-colors disabled:opacity-40"
                              title="再生成"
                            >
                              <RefreshCw size={10} className={isRegenerating ? "animate-spin" : ""} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 3: 動画一括生成 ─────────────────────────────────────

function BatchStep3({
  selectedIds,
  batchStates,
  batchVideoGenerating,
  onGenerateVideos,
  onBack,
}: {
  selectedIds: number[];
  batchStates: Record<number, StoryboardBatchState>;
  batchVideoGenerating: boolean;
  onGenerateVideos: () => void;
  onBack: () => void;
}) {
  const totalScenes = selectedIds.reduce((sum, id) => {
    const data = batchStates[id]?.data;
    return sum + (data?.scenes.length ?? 0);
  }, 0);

  const completedVideos = selectedIds.reduce((sum, id) => {
    const data = batchStates[id]?.data;
    if (!data) return sum;
    return sum + data.scenes.filter((s) => s.video_status === "ready").length;
  }, 0);

  return (
    <div className="space-y-4">
      <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
          <Video size={12} className="text-blue-400/70" />
          ステップ 3 — 動画一括生成
        </h3>
        <p className="text-sm text-slate-400">
          承認済みの {selectedIds.length} 件の台本（合計 {totalScenes} シーン）から動画を一括生成します。
        </p>

        {completedVideos > 0 && (
          <div className="flex items-center gap-2 px-3 py-2 bg-emerald-500/[0.08] border border-emerald-500/[0.15] rounded-xl text-xs text-emerald-400">
            <CheckCircle2 size={14} />
            {completedVideos} / {totalScenes} シーンの動画生成が完了しています
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
            disabled={batchVideoGenerating}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
            style={{ boxShadow: batchVideoGenerating ? "none" : "0 0 20px rgba(59,130,246,0.25)" }}
          >
            {batchVideoGenerating ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            {batchVideoGenerating ? "生成中..." : "全台本の動画を一括生成"}
          </button>
        </div>
      </div>

      {/* 台本ごとの動画生成状況 */}
      <div className="space-y-3">
        {selectedIds.map((sbId) => {
          const state = batchStates[sbId];
          const sb = storyboards_from_state(state);
          const genStatus = state?.videoGenStatus;
          const videoReadyCount = sb?.scenes.filter((s) => s.video_status === "ready").length ?? 0;

          return (
            <div key={sbId} className="bg-[#0e1d32] rounded-xl p-4 border border-blue-400/[0.10] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Video size={14} className="text-purple-400/60" />
                  <span className="text-sm text-slate-200">
                    {sb?.title || `台本 #${sbId}`}
                  </span>
                  {sb && <StatusBadge status={sb.status} />}
                </div>
                <span className="text-xs text-slate-500">
                  {videoReadyCount} / {sb?.scenes.length ?? "?"} シーン完了
                </span>
              </div>

              {genStatus && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {genStatus.completed_scenes} / {genStatus.total_scenes} 完了
                    </span>
                    <StatusBadge status={genStatus.status} />
                  </div>
                  <div className="w-full bg-[#132040] rounded-full h-1.5">
                    <div
                      className="bg-purple-500 h-1.5 rounded-full transition-all"
                      style={{
                        width: genStatus.total_scenes > 0
                          ? `${(genStatus.completed_scenes / genStatus.total_scenes) * 100}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>
              )}

              {/* シーン動画ステータス */}
              {sb && (
                <div className="grid grid-cols-5 gap-2">
                  {sb.scenes.map((scene, idx) => (
                    <div
                      key={scene.id}
                      className={`flex flex-col items-center gap-1 p-2 rounded-lg border text-center ${
                        scene.video_status === "ready"
                          ? "bg-emerald-500/[0.08] border-emerald-500/[0.15]"
                          : scene.video_status === "generating"
                          ? "bg-purple-500/[0.08] border-purple-500/[0.15]"
                          : "bg-[#132040] border-blue-400/[0.08]"
                      }`}
                    >
                      {scene.video_status === "ready" ? (
                        <Play size={10} className="text-emerald-400" />
                      ) : scene.video_status === "generating" ? (
                        <Loader2 size={10} className="animate-spin text-purple-400" />
                      ) : (
                        <Video size={10} className="text-slate-600" />
                      )}
                      <span className="text-[9px] text-slate-500 truncate w-full">
                        {COURSE_LABELS[scene.course_key]?.slice(0, 4) ?? `S${idx + 1}`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── ユーティリティ ────────────────────────────────────────────

function storyboards_from_state(state: StoryboardBatchState | undefined): StoryboardData | null {
  return state?.data ?? null;
}
