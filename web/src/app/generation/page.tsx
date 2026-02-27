"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Wand2,
  Eye,
  Monitor,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  User,
  X,
  SlidersHorizontal,
  Activity,
} from "lucide-react";
import StoryboardWorkflowTab from "./components/StoryboardWorkflowTab";
import ExperiencePreviewTab from "./components/ExperiencePreviewTab";
import CharacterTab from "./components/CharacterTab";
import {
  fetchGenerationThemes,
  fetchJobs,
  fetchTableSpec,
  updateTableSpec,
  type GenerationThemes,
  type TableSpec,
} from "@/lib/api";

// ── パネルID型 ─────────────────────────────────────────────────
type PanelId = "character" | "experience" | "jobs" | "tableSpec" | null;

// ── メインページ ───────────────────────────────────────────────

export default function GenerationPage() {
  const [meta, setMeta] = useState<GenerationThemes | null>(null);
  const [tableSpec, setTableSpec] = useState<TableSpec | null>(null);
  const [openPanel, setOpenPanel] = useState<PanelId>(null);
  const [jobs, setJobs] = useState<Record<string, Record<string, unknown>>>({});
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchGenerationThemes().then(setMeta).catch(() => {});
    fetchTableSpec().then(setTableSpec).catch(() => {});
  }, []);

  const showFeedback = useCallback((type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4000);
  }, []);

  async function refreshJobs() {
    try {
      const data = await fetchJobs();
      setJobs(data);
    } catch {}
  }

  function togglePanel(id: PanelId) {
    setOpenPanel((prev) => (prev === id ? null : id));
  }

  // アクティブなジョブ数
  const activeJobCount = Object.values(jobs).filter(
    (j) => j.status === "processing"
  ).length;

  return (
    <div className="space-y-0">
      {/* ── ページヘッダー ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Wand2 size={20} className="text-blue-400" />
            台本・映像生成
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            台本作成 → 画像生成・確認 → 動画生成
          </p>
        </div>

        {/* ツールボタン群 */}
        <div className="flex items-center gap-2">
          {/* ジョブ状況 */}
          <button
            onClick={() => {
              refreshJobs();
              togglePanel("jobs");
            }}
            className={`relative flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              openPanel === "jobs"
                ? "bg-blue-500/10 border-blue-400/30 text-blue-300"
                : "bg-[#0e1d32] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/20"
            }`}
            title="ジョブ管理"
          >
            <Activity size={14} />
            <span className="hidden sm:inline">ジョブ</span>
            {activeJobCount > 0 && (
              <span className="flex items-center justify-center w-4 h-4 rounded-full bg-amber-500 text-[9px] font-bold text-[#080f1a]">
                {activeJobCount}
              </span>
            )}
          </button>

          {/* キャラクター生成 */}
          <button
            onClick={() => togglePanel("character")}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              openPanel === "character"
                ? "bg-blue-500/10 border-blue-400/30 text-blue-300"
                : "bg-[#0e1d32] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/20"
            }`}
            title="キャラクター生成"
          >
            <User size={14} />
            <span className="hidden sm:inline">キャラクター</span>
          </button>

          {/* 体験プレビュー */}
          <button
            onClick={() => togglePanel("experience")}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              openPanel === "experience"
                ? "bg-blue-500/10 border-blue-400/30 text-blue-300"
                : "bg-[#0e1d32] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/20"
            }`}
            title="体験プレビュー"
          >
            <Eye size={14} />
            <span className="hidden sm:inline">プレビュー</span>
          </button>

          {/* テーブルスペック設定 */}
          <button
            onClick={() => togglePanel("tableSpec")}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
              openPanel === "tableSpec"
                ? "bg-blue-500/10 border-blue-400/30 text-blue-300"
                : "bg-[#0e1d32] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/20"
            }`}
            title="テーブル設定"
          >
            <SlidersHorizontal size={14} />
            <span className="hidden sm:inline">テーブル設定</span>
          </button>
        </div>
      </div>

      {/* ── フィードバック ── */}
      {feedback && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm mb-4 ${
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
              : "bg-red-500/10 text-red-400 border border-red-500/15"
          }`}
        >
          {feedback.type === "success" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          {feedback.message}
        </div>
      )}

      {/* ── サブパネル（スライドオーバー型） ── */}
      {openPanel && (
        <div className="mb-4">
          <div className="bg-[#0e1d32] rounded-2xl border border-blue-400/[0.12] overflow-hidden">
            {/* パネルヘッダー */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-blue-400/[0.08] bg-[#080f1a]/60">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                {openPanel === "character" && <><User size={14} className="text-blue-400" /> キャラクター生成</>}
                {openPanel === "experience" && <><Eye size={14} className="text-blue-400" /> 体験プレビュー</>}
                {openPanel === "jobs" && <><Activity size={14} className="text-blue-400" /> ジョブ管理</>}
                {openPanel === "tableSpec" && <><SlidersHorizontal size={14} className="text-blue-400" /> テーブルスペック設定</>}
              </h3>
              <button
                onClick={() => setOpenPanel(null)}
                className="p-1.5 text-slate-500 hover:text-white transition-colors rounded-lg hover:bg-blue-400/[0.08]"
              >
                <X size={15} />
              </button>
            </div>

            {/* パネルコンテンツ */}
            <div className="p-5">
              {openPanel === "character" && <CharacterTab />}

              {openPanel === "experience" && <ExperiencePreviewTab />}

              {openPanel === "jobs" && (
                <JobsPanel jobs={jobs} onRefresh={refreshJobs} />
              )}

              {openPanel === "tableSpec" && (
                <TableSpecSection
                  tableSpec={tableSpec}
                  setTableSpec={setTableSpec}
                  meta={meta}
                  showFeedback={showFeedback}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── メインコンテンツ: StoryboardWorkflow ── */}
      <StoryboardWorkflowTab themes={meta} />
    </div>
  );
}

// ── テーブルスペックセクション ────────────────────────────────

function TableSpecSection({
  tableSpec,
  setTableSpec,
  meta,
  showFeedback,
}: {
  tableSpec: TableSpec | null;
  setTableSpec: (spec: TableSpec) => void;
  meta: GenerationThemes | null;
  showFeedback: (type: "success" | "error", message: string) => void;
}) {
  const [pjWidth, setPjWidth] = useState(tableSpec?.pj_width ?? 1920);
  const [pjHeight, setPjHeight] = useState(tableSpec?.pj_height ?? 1200);
  const [pjCount, setPjCount] = useState(tableSpec?.pj_count ?? 3);
  const [blendOverlap, setBlendOverlap] = useState(tableSpec?.blend_overlap ?? 120);
  const [zoneCount, setZoneCount] = useState(tableSpec?.zone_count ?? 4);
  const [tableWidthMm, setTableWidthMm] = useState(tableSpec?.table_width_mm ?? 8120);
  const [tableHeightMm, setTableHeightMm] = useState(tableSpec?.table_height_mm ?? 600);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (tableSpec) {
      setPjWidth(tableSpec.pj_width);
      setPjHeight(tableSpec.pj_height);
      setPjCount(tableSpec.pj_count);
      setBlendOverlap(tableSpec.blend_overlap);
      setZoneCount(tableSpec.zone_count);
      setTableWidthMm(tableSpec.table_width_mm);
      setTableHeightMm(tableSpec.table_height_mm);
    }
  }, [tableSpec]);

  const calcFullWidth = pjWidth * pjCount - blendOverlap * (pjCount - 1);
  const calcFullHeight = pjHeight;
  const calcZoneWidth = zoneCount > 0 ? Math.round(calcFullWidth / zoneCount) : 0;
  const calcZoneHeight = pjHeight;

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateTableSpec({
        pj_width: pjWidth,
        pj_height: pjHeight,
        pj_count: pjCount,
        blend_overlap: blendOverlap,
        zone_count: zoneCount,
        table_width_mm: tableWidthMm,
        table_height_mm: tableHeightMm,
      });
      setTableSpec(updated);
      showFeedback("success", "テーブルスペックを保存しました");
    } catch {
      showFeedback("error", "保存に失敗しました");
    }
    setSaving(false);
  }

  return (
    <div className="space-y-5">
      {/* 現在の設定サマリー */}
      <div className="grid grid-cols-6 gap-3">
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">物理サイズ</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {(tableSpec?.table_width_mm ?? meta?.table_spec.table_width_mm) ?? "—"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            x {(tableSpec?.table_height_mm ?? meta?.table_spec.table_height_mm) ?? "—"} mm
          </p>
        </div>
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">テーブル全幅</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {tableSpec?.full_width ?? meta?.table_spec.full_width ?? "—"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">px</p>
        </div>
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">高さ</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {tableSpec?.full_height ?? meta?.table_spec.full_height ?? "—"}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">px</p>
        </div>
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">区画数</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {tableSpec?.zone_count ?? meta?.table_spec.zone_count ?? "—"}
          </p>
        </div>
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">区画サイズ</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {tableSpec
              ? `${tableSpec.zone_width}x${tableSpec.zone_height}`
              : meta
              ? `${meta.table_spec.zone_width}x${meta.table_spec.zone_height}`
              : "—"}
          </p>
        </div>
        <div className="bg-[#080f1a] rounded-xl p-3 border border-blue-400/[0.08] text-center">
          <p className="text-xs text-slate-400">テーマ数</p>
          <p className="text-base font-bold font-mono text-white mt-1">
            {meta?.themes.length ?? "—"}
          </p>
        </div>
      </div>

      {/* 編集フォーム */}
      <div className="space-y-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
          物理パラメータ設定
        </h3>

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-xs text-slate-400 mb-1.5">テーブル実寸 (横mm x 縦mm)</label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                value={tableWidthMm}
                onChange={(e) => setTableWidthMm(Number(e.target.value))}
                min={1}
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="8120"
              />
              <span className="flex items-center text-slate-500 text-sm flex-shrink-0">x</span>
              <input
                type="number"
                value={tableHeightMm}
                onChange={(e) => setTableHeightMm(Number(e.target.value))}
                min={1}
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="600"
              />
              <span className="flex items-center text-slate-500 text-xs flex-shrink-0">mm</span>
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1.5">PJ解像度 (幅 x 高さ)</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={pjWidth}
                onChange={(e) => setPjWidth(Number(e.target.value))}
                min={1}
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="1920"
              />
              <span className="flex items-center text-slate-500 text-sm flex-shrink-0">x</span>
              <input
                type="number"
                value={pjHeight}
                onChange={(e) => setPjHeight(Number(e.target.value))}
                min={1}
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="1200"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1.5">PJ台数</label>
            <input
              type="number"
              value={pjCount}
              onChange={(e) => setPjCount(Number(e.target.value))}
              min={1}
              max={10}
              className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
              placeholder="3"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1.5">ブレンドオーバーラップ (px)</label>
            <input
              type="number"
              value={blendOverlap}
              onChange={(e) => setBlendOverlap(Number(e.target.value))}
              min={0}
              className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
              placeholder="120"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1.5">テーブル区画数</label>
            <input
              type="number"
              value={zoneCount}
              onChange={(e) => setZoneCount(Number(e.target.value))}
              min={1}
              max={20}
              className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
              placeholder="4"
            />
          </div>
        </div>

        {/* 計算プレビュー */}
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">計算結果</p>
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-[#132040] rounded-xl p-3 border border-blue-400/[0.12] text-center">
              <p className="text-xs text-slate-500">全幅</p>
              <p className="text-base font-bold font-mono text-blue-400 mt-1">{calcFullWidth}</p>
              <p className="text-xs text-slate-600 mt-0.5">px</p>
            </div>
            <div className="bg-[#132040] rounded-xl p-3 border border-blue-400/[0.12] text-center">
              <p className="text-xs text-slate-500">高さ</p>
              <p className="text-base font-bold font-mono text-blue-400 mt-1">{calcFullHeight}</p>
              <p className="text-xs text-slate-600 mt-0.5">px</p>
            </div>
            <div className="bg-[#132040] rounded-xl p-3 border border-blue-400/[0.12] text-center">
              <p className="text-xs text-slate-500">区画幅</p>
              <p className="text-base font-bold font-mono text-blue-400 mt-1">{calcZoneWidth}</p>
              <p className="text-xs text-slate-600 mt-0.5">px</p>
            </div>
            <div className="bg-[#132040] rounded-xl p-3 border border-blue-400/[0.12] text-center">
              <p className="text-xs text-slate-500">区画高さ</p>
              <p className="text-base font-bold font-mono text-blue-400 mt-1">{calcZoneHeight}</p>
              <p className="text-xs text-slate-600 mt-0.5">px</p>
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium disabled:opacity-40 rounded-xl text-sm transition-colors"
          >
            {saving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ジョブパネル ──────────────────────────────────────────────

function JobsPanel({
  jobs,
  onRefresh,
}: {
  jobs: Record<string, Record<string, unknown>>;
  onRefresh: () => void;
}) {
  const jobEntries = Object.entries(jobs);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
          ジョブ一覧 ({jobEntries.length})
        </h3>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-white rounded-xl text-xs transition-colors"
        >
          <RefreshCw size={14} /> 更新
        </button>
      </div>

      {jobEntries.length === 0 ? (
        <div className="text-center py-10 bg-[#080f1a] rounded-xl border border-blue-400/[0.08]">
          <Monitor size={32} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400 text-sm">アクティブなジョブはありません</p>
        </div>
      ) : (
        <div className="space-y-2">
          {jobEntries.map(([id, job]) => {
            const status = String(job.status || "unknown");
            const isProcessing = status === "processing";
            const isComplete = status === "complete";
            const isFailed = status === "failed";
            return (
              <div
                key={id}
                className="flex items-center justify-between p-4 bg-[#080f1a] rounded-xl border border-blue-400/[0.08]"
              >
                <div className="flex items-center gap-3">
                  {isProcessing && <Loader2 size={16} className="animate-spin text-amber-400" />}
                  {isComplete && <CheckCircle2 size={16} className="text-emerald-400" />}
                  {isFailed && <XCircle size={16} className="text-red-400" />}
                  <div>
                    <p className="text-sm font-medium font-mono text-white">{id}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {job.theme ? String(job.theme) : ""}
                      {job.course ? ` / ${String(job.course)}` : ""}
                      {job.mode ? ` (${String(job.mode)})` : ""}
                      {job.day ? String(job.day) : ""}
                      {job.progress ? ` [${String(job.progress)}]` : ""}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-xs px-2.5 py-1 rounded-full ${
                    isProcessing
                      ? "bg-amber-500/15 text-amber-400"
                      : isComplete
                      ? "bg-emerald-500/15 text-emerald-400"
                      : isFailed
                      ? "bg-red-500/15 text-red-400"
                      : "bg-blue-400/[0.08] text-slate-400"
                  }`}
                >
                  {isProcessing ? "処理中" : isComplete ? "完了" : isFailed ? "失敗" : status}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
