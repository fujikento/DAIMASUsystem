"use client";

import { useState } from "react";
import {
  ChevronRight,
  Wand2,
  Loader2,
  Edit3,
  Save,
  X,
  Sparkles,
  Utensils,
} from "lucide-react";
import {
  generateScript,
  updateScene,
  type StoryboardData,
  type StoryboardScene,
} from "@/lib/api";

const COURSE_LABEL: Record<string, { jp: string; emoji: string }> = {
  welcome: { jp: "ウェルカム", emoji: "🌸" },
  appetizer: { jp: "前菜", emoji: "🥗" },
  soup: { jp: "スープ", emoji: "🍲" },
  main: { jp: "メイン", emoji: "🍖" },
  dessert: { jp: "デザート", emoji: "🍰" },
};

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
    <div className="space-y-6">
      {/* ─ Step intro ─ */}
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-bold text-white">
          どんなお話にしますか?
        </h2>
        <p className="text-neutral-400 text-sm">
          各料理のシーンを書きます。テーマのテンプレートが入っているのでこのまま次へも、AIに書かせるのも、自分で編集するのも自由です。
        </p>
      </div>

      {/* ─ AI generate card ─ */}
      <div className="rounded-2xl bg-gradient-to-br from-purple-900/30 via-blue-900/20 to-blue-900/10 border border-purple-400/20 p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-400/30 flex items-center justify-center shrink-0">
            <Wand2 size={18} className="text-purple-300" />
          </div>
          <div className="flex-1">
            <h3 className="text-white font-semibold text-sm">
              AIに台本を書かせる(おすすめ)
            </h3>
            <p className="text-neutral-400 text-xs mt-1 leading-relaxed">
              テーマに沿った映像のシーンをAIが自動で書きます。雰囲気だけ伝えても OK。
            </p>
          </div>
        </div>

        {showConceptInput ? (
          <div className="space-y-3">
            <textarea
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="例:満月の夜、桜が舞い散る幻想的な雰囲気で(空欄でもOK)"
              rows={3}
              className="w-full bg-[#0a1628] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-neutral-600 focus:border-purple-400/50 focus:outline-none resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleAIGenerate}
                disabled={genLoading}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold transition-colors disabled:opacity-60"
              >
                {genLoading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    生成中(15-30秒)...
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    AIに書かせる
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowConceptInput(false);
                  setConcept("");
                }}
                disabled={genLoading}
                className="px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-neutral-400 text-sm transition-colors disabled:opacity-60"
              >
                やめる
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowConceptInput(true)}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 border border-purple-400/30 text-purple-200 text-sm font-semibold transition-colors"
          >
            <Wand2 size={14} />
            AIに書かせる(雰囲気を指示)
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

  const meta = COURSE_LABEL[scene.course_key] ?? { jp: scene.course_key, emoji: "🍽" };

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
          <span className="text-lg leading-none">{meta.emoji}</span>
          <span className="text-sm font-semibold text-white">{meta.jp}</span>
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
