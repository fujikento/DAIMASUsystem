"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ChevronLeft,
  Video,
  Loader2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Play,
  Eye,
} from "lucide-react";
import Link from "next/link";
import {
  generateStoryboardVideos,
  fetchScenesStatus,
  regenerateSceneVideo,
  fetchTables,
  type StoryboardData,
  type ProjectionTable,
} from "@/lib/api";
import TableMockup, { type MockupMode } from "@/components/TableMockup";

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
  const [table, setTable] = useState<ProjectionTable | null>(null);
  const [mockupSceneIdx, setMockupSceneIdx] = useState(0);
  const [mockupMode, setMockupMode] = useState<MockupMode>("unified");

  // ─ Load the table this storyboard is for ─
  useEffect(() => {
    if (!storyboard.projection_config_id) return;
    fetchTables()
      .then((tbls) =>
        setTable(tbls.find((t) => t.id === storyboard.projection_config_id) ?? null)
      )
      .catch(() => {});
  }, [storyboard.projection_config_id]);

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
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-white">
          {allDone
            ? "動画生成完了"
            : !someDone
            ? "動画生成"
            : inProgress
            ? "動画生成中"
            : "動画一覧"}
        </h2>
        <p className="text-neutral-500 text-sm">
          {allDone
            ? "投影画面から再生できます。"
            : !someDone
            ? `画像を 5秒の動画に変換します。1シーン約 60-120秒。コスト合計 約 $${estCost}。`
            : `${completedCount} / ${storyboard.scenes.length} 完成`}
        </p>
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
        <div className="rounded-xl bg-[#0e1d32] border border-blue-400/15 p-8 text-center space-y-3">
          <p className="text-white text-sm font-medium">
            {storyboard.scenes.length} 件の動画を生成します
          </p>
          <p className="text-xs text-neutral-500">
            合計所要時間 約 5-15分。バックグラウンドで処理されます。
          </p>
          <div className="pt-1">
            <button
              onClick={startBatchVideo}
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
            <div className="rounded-md bg-[#11141a] border border-white/10 p-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-blue-300 font-medium">
                  <Loader2 size={12} className="animate-spin" />
                  生成中(動画は時間がかかります)
                </span>
                <span className="text-neutral-500 tabular-nums">
                  {completedCount} / {storyboard.scenes.length}
                </span>
              </div>
              <div className="h-1 bg-[#0a0d12] rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-500"
                  style={{
                    width: `${(completedCount / storyboard.scenes.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* ─ Mockup preview (only when video done + table loaded) ─ */}
          {table && someDone && (
            <section className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
              <div className="px-3 py-2 border-b border-white/10 bg-white/[0.02] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye size={12} className="text-neutral-500" />
                  <h3 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
                    テーブル投影プレビュー
                  </h3>
                  <span className="text-[10px] text-neutral-600">— {table.name}</span>
                </div>
                {/* Mode toggle */}
                <div className="inline-flex rounded border border-white/10 overflow-hidden text-[10px]">
                  {(["unified", "per_zone", "synchronized"] as MockupMode[]).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMockupMode(m)}
                      className={`px-2 py-1 transition-colors ${
                        mockupMode === m
                          ? "bg-blue-500/20 text-blue-200"
                          : "bg-transparent text-neutral-500 hover:text-white"
                      }`}
                    >
                      {m === "unified"
                        ? "連結"
                        : m === "per_zone"
                        ? "席ごと"
                        : "同期"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-4 space-y-3">
                {/* Scene selector */}
                {mockupMode !== "per_zone" && storyboard.scenes.length > 1 && (
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-[10px] text-neutral-500 mr-1">シーン:</span>
                    {storyboard.scenes.map((s, i) => {
                      const ready = s.video_status === "complete";
                      const active = i === mockupSceneIdx;
                      return (
                        <button
                          key={s.id}
                          onClick={() => setMockupSceneIdx(i)}
                          disabled={!ready}
                          className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                            active
                              ? "bg-blue-500/20 border-blue-400/40 text-blue-200"
                              : "bg-transparent border-white/10 text-neutral-500 hover:text-white disabled:opacity-30"
                          }`}
                        >
                          #{i + 1}
                        </button>
                      );
                    })}
                  </div>
                )}
                <TableMockup
                  table={table}
                  mode={mockupMode}
                  maxHeight={280}
                  showProjectorOverlay
                  sources={
                    mockupMode === "per_zone"
                      ? {
                          byZone: Object.fromEntries(
                            storyboard.scenes
                              .slice(0, table.zone_count)
                              .map((s, i) => [i, mediaUrl(s.video_path)])
                          ),
                        }
                      : mockupMode === "synchronized"
                      ? { sync: mediaUrl(storyboard.scenes[mockupSceneIdx]?.video_path ?? null) }
                      : { unified: mediaUrl(storyboard.scenes[mockupSceneIdx]?.video_path ?? null) }
                  }
                />
                <p className="text-[10px] text-neutral-500 leading-relaxed">
                  {mockupMode === "unified" &&
                    "連結モード: テーブル全幅 (1動画) で再生。複数席を連続したパノラマ的演出。"}
                  {mockupMode === "per_zone" &&
                    "席ごとモード: ゾーン毎に異なる動画を再生。シーンの順 (#1, #2, ...) が席に対応します。"}
                  {mockupMode === "synchronized" &&
                    "同期モード: 全席で同じ動画を同時再生。テーブル全体で揃った演出。"}
                </p>
              </div>
            </section>
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
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors"
          >
            <Play size={14} />
            投影画面を開く
          </Link>
        ) : (
          <Link
            href="/create"
            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-300 text-sm transition-colors"
          >
            一覧に戻る
          </Link>
        )}
      </div>
    </div>
  );
}
