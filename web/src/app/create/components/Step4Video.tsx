"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ChevronLeft,
  Video,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Play,
  PartyPopper,
} from "lucide-react";
import Link from "next/link";
import {
  generateStoryboardVideos,
  fetchScenesStatus,
  regenerateSceneVideo,
  type StoryboardData,
} from "@/lib/api";

const COURSE_EMOJI: Record<string, string> = {
  welcome: "🌸",
  appetizer: "🥗",
  soup: "🍲",
  main: "🍖",
  dessert: "🍰",
};

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
}

const API_BASE =
  typeof window !== "undefined" && process.env.NEXT_PUBLIC_API_BASE
    ? process.env.NEXT_PUBLIC_API_BASE
    : "http://localhost:8000";

function mediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}/static-content/${encodeURI(path.replace(/^\//, ""))}`;
}

export default function Step4Video({ storyboard, onReload, onBack }: Props) {
  const [batchLoading, setBatchLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [regeneratingId, setRegeneratingId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const allDone = storyboard.scenes.every((s) => s.video_status === "complete");
  const someDone = storyboard.scenes.some((s) => s.video_status === "complete");
  const inProgress = storyboard.scenes.some(
    (s) => s.video_status === "pending" || s.video_status === "processing"
  );

  const poll = useCallback(async () => {
    if (!inProgress && !polling) return;
    try {
      const data = await fetchScenesStatus(storyboard.id);
      const stillInFlight = data.scenes.some(
        (s) => s.video_status === "pending" || s.video_status === "processing"
      );
      await onReload();
      if (!stillInFlight) setPolling(false);
    } catch {
      // silent — next tick
    }
  }, [storyboard.id, inProgress, polling, onReload]);

  useEffect(() => {
    if (!inProgress && !polling) return;
    setPolling(true);
    const t = setInterval(poll, 5000);
    return () => clearInterval(t);
  }, [inProgress, polling, poll]);

  async function startBatchVideo() {
    setBatchLoading(true);
    setErr(null);
    try {
      await generateStoryboardVideos(storyboard.id);
      setPolling(true);
      await onReload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "動画生成の開始に失敗しました");
    } finally {
      setBatchLoading(false);
    }
  }

  async function regenerate(sceneId: number) {
    setRegeneratingId(sceneId);
    try {
      await regenerateSceneVideo(storyboard.id, sceneId);
      setPolling(true);
      await onReload();
    } catch (e) {
      alert(`再生成失敗: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setRegeneratingId(null);
    }
  }

  const completedCount = storyboard.scenes.filter(
    (s) => s.video_status === "complete"
  ).length;
  const estCost = (storyboard.scenes.length * 0.2).toFixed(2);

  return (
    <div className="space-y-6">
      {/* ─ Step intro ─ */}
      <div className="text-center space-y-1.5">
        {allDone ? (
          <>
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-500/15 border-2 border-emerald-500/40 mb-2">
              <PartyPopper size={26} className="text-emerald-300" />
            </div>
            <h2 className="text-2xl font-bold text-white">
              完成しました!
            </h2>
            <p className="text-neutral-400 text-sm">
              これで投影できます。投影画面で再生してみてください。
            </p>
          </>
        ) : (
          <>
            <h2 className="text-2xl font-bold text-white">
              {!someDone
                ? "動画にしましょう"
                : inProgress
                ? "動画を生成中..."
                : "動画を確認"}
            </h2>
            <p className="text-neutral-400 text-sm">
              {!someDone
                ? `画像を5秒の動画に変換します(1シーン約60-120秒、コスト合計 ~$${estCost})`
                : `${completedCount} / ${storyboard.scenes.length} 完成`}
            </p>
          </>
        )}
      </div>

      {/* ─ Error display ─ */}
      {err && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 flex items-start gap-2">
          <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{err}</p>
        </div>
      )}

      {/* ─ Initial CTA ─ */}
      {!someDone && !inProgress ? (
        <div className="rounded-3xl bg-gradient-to-br from-purple-900/30 to-pink-900/15 border-2 border-dashed border-purple-400/30 p-10 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-purple-600/20 border border-purple-400/30 mx-auto flex items-center justify-center">
            <Video size={28} className="text-purple-300" />
          </div>
          <div className="space-y-1">
            <p className="text-white font-semibold">
              画像を動画にしますか?
            </p>
            <p className="text-xs text-neutral-400">
              5-15分かかります。他の画面に移っても続行します。
            </p>
          </div>
          <button
            onClick={startBatchVideo}
            disabled={batchLoading}
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-base shadow-xl shadow-purple-900/40 transition-all hover:scale-[1.02] active:scale-[0.99] disabled:opacity-60"
          >
            {batchLoading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                開始中...
              </>
            ) : (
              <>
                <Sparkles size={18} />
                動画を生成する
              </>
            )}
          </button>
        </div>
      ) : (
        <>
          {/* ─ Progress bar ─ */}
          {inProgress && (
            <div className="rounded-xl bg-[#0e1d32] border border-purple-400/15 p-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-purple-300 font-medium">
                  <Loader2 size={12} className="animate-spin" />
                  生成中(動画は時間がかかります)
                </span>
                <span className="text-neutral-500 tabular-nums">
                  {completedCount} / {storyboard.scenes.length}
                </span>
              </div>
              <div className="h-1.5 bg-[#0a1628] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500"
                  style={{
                    width: `${(completedCount / storyboard.scenes.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* ─ Video grid ─ */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {storyboard.scenes.map((scene, idx) => {
              const vUrl = mediaUrl(scene.video_path);
              const iUrl = mediaUrl(scene.image_path);
              const vDone = scene.video_status === "complete";
              const isRegen = regeneratingId === scene.id;
              return (
                <div
                  key={scene.id}
                  className="group relative rounded-2xl bg-[#0e1d32] border border-blue-400/10 overflow-hidden"
                >
                  <div className="relative aspect-video bg-[#080f1a]">
                    {vDone && vUrl ? (
                      <video
                        src={vUrl}
                        muted
                        loop
                        playsInline
                        controls
                        poster={iUrl ?? undefined}
                        className="w-full h-full object-cover"
                      />
                    ) : iUrl ? (
                      <>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={iUrl}
                          alt={`シーン ${idx + 1}`}
                          className="w-full h-full object-cover opacity-40"
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          {scene.video_status === "pending" ||
                          scene.video_status === "processing" ||
                          isRegen ? (
                            <Loader2 size={28} className="animate-spin text-white/70" />
                          ) : scene.video_status === "failed" ? (
                            <AlertTriangle size={28} className="text-red-400/80" />
                          ) : (
                            <Video size={28} className="text-white/30" />
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Video size={24} className="text-neutral-700" />
                      </div>
                    )}
                    {vDone && (
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
                      <span className="text-base leading-none">
                        {COURSE_EMOJI[scene.course_key] ?? "🍽"}
                      </span>
                      <span className="text-xs font-medium text-white">
                        {COURSE_JP[scene.course_key] ?? scene.course_key}
                      </span>
                    </div>
                    {vDone && (
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
          画像に戻る
        </button>
        {allDone ? (
          <Link
            href="/control"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-base shadow-lg shadow-emerald-900/40 transition-all hover:scale-[1.02] active:scale-[0.99]"
          >
            <Play size={18} />
            投影画面を開く
          </Link>
        ) : (
          <Link
            href="/create"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-300 font-medium text-sm transition-colors"
          >
            一覧に戻る
          </Link>
        )}
      </div>
    </div>
  );
}
