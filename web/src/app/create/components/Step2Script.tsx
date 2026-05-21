"use client";

import { useState } from "react";
import {
  ChevronRight,
  Loader2,
  Edit3,
  Save,
  X,
  Utensils,
} from "lucide-react";
import {
  generateScript,
  updateScene,
  updateStoryboard,
  type StoryboardData,
  type StoryboardScene,
} from "@/lib/api";

const COURSE_LABEL: Record<string, string> = {
  welcome: "ウェルカム",
  appetizer: "前菜",
  soup: "スープ",
  main: "メイン",
  dessert: "デザート",
};

type PlaybackMode = "unified" | "per_zone" | "synchronized";

const MODE_OPTIONS: Array<{ key: PlaybackMode; label: string; desc: string }> = [
  { key: "unified", label: "連結", desc: "テーブル全幅に1動画。複数席を連続したパノラマ演出。" },
  { key: "per_zone", label: "席ごと", desc: "ゾーン毎に別動画。各人前に異なる映像。" },
  { key: "synchronized", label: "同期", desc: "全席で同じ動画を同時再生。揃った演出。" },
];

interface Props {
  storyboard: StoryboardData;
  onReload: () => Promise<void>;
  onNext: () => void;
}

export default function Step2Script({ storyboard, onReload, onNext }: Props) {
  const [genLoading, setGenLoading] = useState(false);
  const [concept, setConcept] = useState("");
  const [showConceptInput, setShowConceptInput] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [modeSaving, setModeSaving] = useState(false);

  const currentMode: PlaybackMode =
    (storyboard.mode as PlaybackMode) || "unified";

  async function handleModeChange(mode: PlaybackMode) {
    if (mode === currentMode) return;
    setModeSaving(true);
    try {
      await updateStoryboard(storyboard.id, { mode });
      await onReload();
    } catch (e) {
      alert(`モード変更失敗: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setModeSaving(false);
    }
  }

  async function handleAIGenerate() {
    setGenLoading(true);
    try {
      await generateScript(storyboard.id, {
        concept: concept.trim() || undefined,
        mode: "full_course",
      });
      setShowConceptInput(false);
      await onReload();
    } catch (e) {
      alert(`AI生成に失敗しました: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setGenLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* ─ Step intro ─ */}
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-white">台本</h2>
        <p className="text-xs text-neutral-500">
          各シーンを編集します。テーマのテンプレートが入っているのでそのまま次へも、AI で書き直しも可能。
        </p>
      </div>

      {/* ─ Playback mode selector ─ */}
      <div className="rounded-md bg-[#11141a] border border-white/10 p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider">
            投影モード
          </h3>
          {modeSaving && (
            <Loader2 size={12} className="animate-spin text-neutral-500" />
          )}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {MODE_OPTIONS.map((opt) => {
            const active = opt.key === currentMode;
            return (
              <button
                key={opt.key}
                onClick={() => handleModeChange(opt.key)}
                disabled={modeSaving}
                className={`text-left p-2.5 rounded border transition-colors disabled:opacity-60 ${
                  active
                    ? "border-blue-400/50 bg-blue-500/10"
                    : "border-white/10 bg-transparent hover:bg-white/[0.03]"
                }`}
              >
                <div
                  className={`text-sm font-semibold ${
                    active ? "text-blue-200" : "text-neutral-200"
                  }`}
                >
                  {opt.label}
                </div>
                <p className="text-[10px] text-neutral-500 leading-snug mt-0.5">
                  {opt.desc}
                </p>
              </button>
            );
          })}
        </div>
        <p className="text-[10px] text-neutral-600">
          ※ 完成後の Step 4「テーブル投影プレビュー」でも切り替えて確認できます。投影時はこのモードが既定で使われます。
        </p>
      </div>

      {/* ─ Script auto-generation card (flat, neutral) ─ */}
      <div className="rounded-xl bg-[#0e1d32] border border-blue-400/10 p-4 space-y-3">
        <div className="space-y-0.5">
          <h3 className="text-white font-semibold text-sm">
            自動で台本を書かせる
          </h3>
          <p className="text-neutral-500 text-xs leading-relaxed">
            テーマに沿ったシーン内容を自動生成します。任意で雰囲気を指定できます。
          </p>
        </div>

        {showConceptInput ? (
          <div className="space-y-2.5">
            <textarea
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="任意:雰囲気の指示(例:満月の夜、和の静謐な雰囲気)"
              rows={3}
              className="w-full bg-[#080f1a] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-neutral-600 focus:border-blue-400/40 focus:outline-none resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleAIGenerate}
                disabled={genLoading}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-60"
              >
                {genLoading ? (
                  <>
                    <Loader2 size={13} className="animate-spin" />
                    生成中(15-30秒)
                  </>
                ) : (
                  "実行"
                )}
              </button>
              <button
                onClick={() => {
                  setShowConceptInput(false);
                  setConcept("");
                }}
                disabled={genLoading}
                className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-400 text-sm transition-colors disabled:opacity-60"
              >
                キャンセル
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowConceptInput(true)}
            className="w-full py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-neutral-200 text-sm font-medium transition-colors"
          >
            自動生成を開始
          </button>
        )}
      </div>

      {/* ─ Scenes list ─ */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-300">
            シーン一覧({storyboard.scenes.length}件)
          </h3>
          <span className="text-xs text-neutral-600">クリックで編集</span>
        </div>

        {storyboard.scenes.length === 0 ? (
          <div className="rounded-2xl bg-[#0e1d32] border border-dashed border-neutral-700 p-10 text-center">
            <Utensils size={24} className="text-neutral-700 mx-auto mb-2" />
            <p className="text-sm text-neutral-500">シーンがありません</p>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {storyboard.scenes.map((scene, idx) => (
              <SceneCard
                key={scene.id}
                scene={scene}
                index={idx}
                storyboardId={storyboard.id}
                editing={editingId === scene.id}
                onEdit={() => setEditingId(scene.id)}
                onCancel={() => setEditingId(null)}
                onSaved={async () => {
                  setEditingId(null);
                  await onReload();
                }}
              />
            ))}
          </ul>
        )}
      </div>

      {/* ─ Next button ─ */}
      <div className="flex items-center justify-end pt-2">
        <button
          onClick={onNext}
          disabled={storyboard.scenes.length === 0}
          className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-base shadow-lg shadow-blue-900/40 transition-all hover:scale-[1.02] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          次へ:画像を作る
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

// ─ Inner scene card ─────────────────────────────────────────────
function SceneCard({
  scene,
  index,
  storyboardId,
  editing,
  onEdit,
  onCancel,
  onSaved,
}: {
  scene: StoryboardScene;
  index: number;
  storyboardId: number;
  editing: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [title, setTitle] = useState(scene.scene_title ?? "");
  const [description, setDescription] = useState(scene.scene_description_ja ?? "");
  const [saving, setSaving] = useState(false);

  const courseJp = COURSE_LABEL[scene.course_key] ?? scene.course_key;

  async function handleSave() {
    setSaving(true);
    try {
      await updateScene(storyboardId, scene.id, {
        scene_title: title.trim() || null,
        scene_description_ja: description.trim(),
      });
      await onSaved();
    } catch (e) {
      alert(`保存失敗: ${e instanceof Error ? e.message : ""}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <li
      className={`rounded-2xl border transition-colors ${
        editing
          ? "bg-[#0a1628] border-blue-400/40"
          : "bg-[#0e1d32] border-blue-400/10 hover:border-blue-400/20"
      }`}
    >
      <div className="p-4 space-y-2.5">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-md bg-blue-500/15 border border-blue-400/20 text-[10px] font-bold text-blue-300 flex items-center justify-center">
            {index + 1}
          </span>
          <span className="text-sm font-semibold text-white">{courseJp}</span>
          {!editing && (
            <button
              onClick={onEdit}
              className="ml-auto text-neutral-500 hover:text-blue-400 transition-colors"
              title="編集"
            >
              <Edit3 size={14} />
            </button>
          )}
        </div>

        {editing ? (
          <div className="space-y-2.5">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="シーンタイトル(任意)"
              className="w-full bg-[#080f1a] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="このシーンで映したい内容を日本語で(例:満開の桜が舞い散る、月明かりに照らされる料亭の庭)"
              rows={3}
              className="w-full bg-[#080f1a] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors disabled:opacity-60"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                保存
              </button>
              <button
                onClick={onCancel}
                disabled={saving}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-neutral-400 text-xs transition-colors"
              >
                <X size={12} />
                キャンセル
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-1.5 pl-8">
            {scene.scene_title && (
              <p className="text-white text-sm font-medium">{scene.scene_title}</p>
            )}
            <p className="text-neutral-400 text-xs leading-relaxed">
              {scene.scene_description_ja || (
                <span className="text-neutral-600 italic">未設定 — クリックして書く</span>
              )}
            </p>
          </div>
        )}
      </div>
    </li>
  );
}
