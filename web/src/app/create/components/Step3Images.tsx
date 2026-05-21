"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import {
  generateStoryboardImages,
  fetchScenesStatus,
  regenerateSceneImage,
  approveStoryboardImages,
  type StoryboardData,
} from "@/lib/api";

const COURSE_JP: Record<string, string> = {
  welcome: "ウェルカム",
  appetizer: "前菜",
  soup: "スープ",
  main: "メイン",
  dessert: "デザート",
};

interface Props {
  storyboard: StoryboardData;
  onReload: () => Promise<void>;
  onBack: () => void;
  onNext: () => void;
}

const API_BASE =
  typeof window !== "undefined" && process.env.NEXT_PUBLIC_API_BASE
    ? process.env.NEXT_PUBLIC_API_BASE
    : "http://localhost:8000";

function imageUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}/static-content/${encodeURI(path.replace(/^\//, ""))}`;
}

export default function Step3Images({
  storyboard,
  onReload,
  onBack,
  onNext,
}: Props) {
  const [batchLoading, setBatchLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [approving, setApproving] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const allDone = storyboard.scenes.every(
    (s) => s.image_status === "complete" || s.image_status === "approved"
  );
  const someDone = storyboard.scenes.some(
    (s) => s.image_status === "complete" || s.image_status === "approved"
  );
  const inProgress = storyboard.scenes.some(
    (s) =>
      s.image_status === "pending" ||
      s.image_status === "processing" ||
      s.image_status === "generating"
  );

  // ─ Auto-poll when generation is in progress ─
  const poll = useCallback(async () => {
    if (!inProgress && !polling) return;
    try {
      const data = await fetchScenesStatus(storyboard.id);
      const stillInFlight = data.scenes.some(
        (s) =>
          s.image_status === "pending" ||
          s.image_status === "processing" ||
          s.image_status === "generating"
      );
      await onReload();
      if (!stillInFlight) setPolling(false);
    } catch {
      // silent — next tick will retry
    }
  }, [storyboard.id, inProgress, polling, onReload]);

  useEffect(() => {
    if (!inProgress && !polling) return;
    setPolling(true);
    const t = setInterval(poll, 3000);
    return () => clearInterval(t);
  }, [inProgress, polling, poll]);

  async function startBatchGenerate() {
    setBatchLoading(true);
    setErr(null);
    try {
      await generateStoryboardImages(storyboard.id);
      setPolling(true);
      await onReload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "画像生成の開始に失敗しました");
    } finally {
      setBatchLoading(false);
    }
  }

  async function regenerate(sceneId: number) {
    setRegeneratingId(sceneId);
    try {
      await regenerateSceneImage(storyboard.id, sceneId);
      setPolling(true);
      await onReload();
    } catch (e) {
      alert(`再生成失敗: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setRegeneratingId(null);
    }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await approveStoryboardImages(storyboard.id);
      await onReload();
      onNext();
    } catch (e) {
      alert(`承認失敗: ${e instanceof Error ? e.message : ""}`);
      setApproving(false);
    }
  }

  const completedCount = storyboard.scenes.filter(
    (s) => s.image_status === "complete" || s.image_status === "approved"
  ).length;

  return (
    <div className="space-y-6">
      {/* ─ Step intro ─ */}
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-bold text-white">
          {!someDone
            ? "画像を作りましょう"
            : inProgress
            ? "画像を生成中..."
            : "画像ができました!"}
        </h2>
        <p className="text-neutral-400 text-sm">
          {!someDone
            ? `${storyboard.scenes.length}シーン分の画像をAIに作らせます(1シーン約20-40秒、コスト合計 ~$${(storyboard.scenes.length * 0.17).toFixed(2)})`
            : inProgress
            ? `${completedCount} / ${storyboard.scenes.length} 完成`
            : "気に入らない画像は右下のボタンで作り直せます"}
        </p>
      </div>

      {/* ─ Error display ─ */}
      {err && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 flex items-start gap-2">
          <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{err}</p>
        </div>
      )}

      {/* ─ Initial CTA or grid ─ */}
      {!someDone && !inProgress ? (
        <div className="rounded-xl bg-[#0e1d32] border border-blue-400/15 p-8 text-center space-y-3">
          <p className="text-white text-sm font-medium">
            {storyboard.scenes.length} 件の画像を生成します
          </p>
          <p className="text-xs text-neutral-500">
            バックグラウンドで処理されます。生成中は他の画面に移動可能です。
          </p>
          <div className="pt-1">
            <button
              onClick={startBatchGenerate}
              disabled={batchLoading}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors disabled:opacity-60"
            >
              {batchLoading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  開始中
                </>
              ) : (
                "生成を開始"
              )}
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* ─ Progress bar ─ */}
          {inProgress && (
            <div className="rounded-xl bg-[#0e1d32] border border-blue-400/15 p-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-blue-300 font-medium">
                  <Loader2 size={12} className="animate-spin" />
                  生成中
                </span>
                <span className="text-neutral-500 tabular-nums">
                  {completedCount} / {storyboard.scenes.length}
                </span>
              </div>
              <div className="h-1.5 bg-[#0a1628] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-400 transition-all duration-500"
                  style={{
                    width: `${(completedCount / storyboard.scenes.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* ─ Image grid ─ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {storyboard.scenes.map((scene, idx) => {
              const url = imageUrl(scene.image_path);
              const status = scene.image_status;
              const done = status === "complete" || status === "approved";
              const isRegen = regeneratingId === scene.id;
              return (
                <div
                  key={scene.id}
                  className="group relative rounded-2xl bg-[#0e1d32] border border-blue-400/10 overflow-hidden"
                >
                  <div className="relative aspect-video bg-[#080f1a]">
                    {done && url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={url}
                        alt={`シーン ${idx + 1}`}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center">
                        {status === "pending" || status === "processing" || status === "generating" || isRegen ? (
                          <Loader2 size={24} className="animate-spin text-neutral-600" />
                        ) : status === "failed" ? (
                          <AlertTriangle size={24} className="text-red-400/60" />
                        ) : (
                          <ImageIcon size={24} className="text-neutral-700" />
                        )}
                      </div>
                    )}
                    {done && (
                      <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-emerald-500/90 border-2 border-white/20 flex items-center justify-center">
                        <CheckCircle2 size={12} className="text-white" />
                      </div>
                    )}
                  </div>
                  <div className="p-3 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded bg-blue-500/15 text-[9px] font-bold text-blue-300 flex items-center justify-center">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-medium text-white">
                        {COURSE_JP[scene.course_key] ?? scene.course_key}
                      </span>
                    </div>
                    {scene.scene_title && (
                      <p className="text-[11px] text-neutral-500 truncate">
                        {scene.scene_title}
                      </p>
                    )}
                    {done && (
                      <button
                        onClick={() => regenerate(scene.id)}
                        disabled={isRegen}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-400 hover:text-white text-[11px] font-medium transition-colors disabled:opacity-60"
                      >
                        {isRegen ? (
                          <Loader2 size={11} className="animate-spin" />
                        ) : (
                          <RefreshCw size={11} />
                        )}
                        作り直す
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ─ Footer nav ─ */}
      <div className="flex items-center justify-between pt-2 gap-3">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-white transition-colors"
        >
          <ChevronLeft size={16} />
          台本に戻る
        </button>
        <button
          onClick={handleApprove}
          disabled={!allDone || approving || inProgress}
          className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-base shadow-lg shadow-blue-900/40 transition-all hover:scale-[1.02] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          title={
            !allDone
              ? "全ての画像が完成するまでお待ちください"
              : "画像を承認して動画化へ"
          }
        >
          {approving ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              承認中...
            </>
          ) : (
            <>
              次へ:動画にする
              <ChevronRight size={18} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
