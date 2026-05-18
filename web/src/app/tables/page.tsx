"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus,
  Loader2,
  AlertTriangle,
  Edit3,
  Trash2,
  X,
  Save,
  Check,
} from "lucide-react";
import {
  fetchTables,
  createTable,
  updateTable,
  deleteTable,
  type ProjectionTable,
} from "@/lib/api";

interface FormState {
  name: string;
  pj_width: number;
  pj_height: number;
  pj_count: number;
  blend_overlap: number;
  zone_count: number;
  table_width_mm: number;
  table_height_mm: number;
  note: string;
  is_default: boolean;
}

const EMPTY: FormState = {
  name: "",
  pj_width: 1920,
  pj_height: 1200,
  pj_count: 3,
  blend_overlap: 120,
  zone_count: 4,
  table_width_mm: 8120,
  table_height_mm: 600,
  note: "",
  is_default: false,
};

function computed(f: FormState) {
  const fw = f.pj_width * f.pj_count - f.blend_overlap * (f.pj_count - 1);
  const fh = f.pj_height;
  const zw = Math.floor(fw / Math.max(f.zone_count, 1));
  return { fw, fh, zw, zh: fh };
}

export default function TablesPage() {
  const [tables, setTables] = useState<ProjectionTable[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const data = await fetchTables();
      setTables(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "席の取得に失敗");
      setTables([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function startCreate() {
    setForm(EMPTY);
    setEditingId(null);
    setCreating(true);
  }

  function startEdit(t: ProjectionTable) {
    setCreating(false);
    setEditingId(t.id);
    setForm({
      name: t.name,
      pj_width: t.pj_width,
      pj_height: t.pj_height,
      pj_count: t.pj_count,
      blend_overlap: t.blend_overlap,
      zone_count: t.zone_count,
      table_width_mm: t.table_width_mm,
      table_height_mm: t.table_height_mm,
      note: t.note ?? "",
      is_default: t.is_default,
    });
  }

  function cancel() {
    setCreating(false);
    setEditingId(null);
    setForm(EMPTY);
  }

  async function submit() {
    if (!form.name.trim()) {
      alert("席名は必須です");
      return;
    }
    setSubmitting(true);
    try {
      const payload = { ...form, name: form.name.trim(), note: form.note.trim() || undefined };
      if (creating) {
        await createTable(payload);
      } else if (editingId) {
        await updateTable(editingId, payload);
      }
      await load();
      cancel();
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失敗");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(t: ProjectionTable) {
    if (!confirm(`「${t.name}」を削除しますか?この席で作った台本は残ります(投影解像度はデフォルト席のものを使用)。`)) return;
    try {
      await deleteTable(t.id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "削除失敗");
    }
  }

  async function setAsDefault(t: ProjectionTable) {
    try {
      await updateTable(t.id, { is_default: true });
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "更新失敗");
    }
  }

  const c = computed(form);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* ─ Header ─ */}
      <div className="flex items-end justify-between gap-3 pb-3 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white">席 (テーブル) 管理</h1>
          <p className="text-xs text-neutral-500 mt-1">
            投影サイズ・プロジェクター構成。台本作成時にどの席用かを選びます。
          </p>
        </div>
        {!creating && editingId === null && (
          <button
            onClick={startCreate}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
          >
            <Plus size={14} />
            新規席
          </button>
        )}
      </div>

      {err && (
        <div className="rounded-md bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-300 flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          {err}
        </div>
      )}

      {/* ─ Edit / Create form ─ */}
      {(creating || editingId !== null) && (
        <div className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
            <h2 className="text-sm font-semibold text-white">
              {creating ? "新しい席を登録" : `席 #${editingId} を編集`}
            </h2>
            <button
              onClick={cancel}
              disabled={submitting}
              className="text-neutral-500 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-4 space-y-4">
            {/* Name + default toggle */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-1">
                  席名 *
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="例:メインテーブル / VIP個室 / カウンター席"
                  className="w-full bg-[#0a0d12] border border-white/10 rounded px-3 py-1.5 text-sm text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-1">
                  デフォルト席
                </label>
                <label className="flex items-center gap-2 h-[34px] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                    className="w-4 h-4 accent-blue-500"
                  />
                  <span className="text-xs text-neutral-300">この席を新規台本のデフォルトに</span>
                </label>
              </div>
            </div>

            {/* Physical dimensions */}
            <fieldset className="space-y-2">
              <legend className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                物理サイズ (mm)
              </legend>
              <div className="grid grid-cols-2 gap-3">
                <NumberField
                  label="テーブル横幅"
                  unit="mm"
                  value={form.table_width_mm}
                  onChange={(v) => setForm({ ...form, table_width_mm: v })}
                />
                <NumberField
                  label="テーブル奥行き"
                  unit="mm"
                  value={form.table_height_mm}
                  onChange={(v) => setForm({ ...form, table_height_mm: v })}
                />
              </div>
            </fieldset>

            {/* Projector config */}
            <fieldset className="space-y-2">
              <legend className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
                プロジェクター構成
              </legend>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <NumberField
                  label="台数"
                  unit="台"
                  value={form.pj_count}
                  onChange={(v) => setForm({ ...form, pj_count: v })}
                />
                <NumberField
                  label="解像度 (幅)"
                  unit="px"
                  value={form.pj_width}
                  onChange={(v) => setForm({ ...form, pj_width: v })}
                />
                <NumberField
                  label="解像度 (高さ)"
                  unit="px"
                  value={form.pj_height}
                  onChange={(v) => setForm({ ...form, pj_height: v })}
                />
                <NumberField
                  label="ブレンド幅"
                  unit="px"
                  value={form.blend_overlap}
                  onChange={(v) => setForm({ ...form, blend_overlap: v })}
                />
              </div>
              <NumberField
                label="ゾーン分割数"
                unit="個"
                value={form.zone_count}
                onChange={(v) => setForm({ ...form, zone_count: v })}
              />
            </fieldset>

            {/* Computed read-only */}
            <div className="bg-[#0a0d12] border border-white/[0.06] rounded p-3 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <Computed label="合成幅" value={`${c.fw}px`} />
              <Computed label="合成高さ" value={`${c.fh}px`} />
              <Computed label="ゾーン幅" value={`${c.zw}px`} />
              <Computed label="アスペクト" value={(c.fw / c.fh).toFixed(2)} />
            </div>

            {/* Note */}
            <div>
              <label className="block text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-1">
                メモ (任意)
              </label>
              <textarea
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                placeholder="例:店奥の個室、2-4名席。"
                rows={2}
                className="w-full bg-[#0a0d12] border border-white/10 rounded px-3 py-1.5 text-sm text-white placeholder-neutral-600 focus:border-blue-400/50 focus:outline-none resize-none"
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={cancel}
                disabled={submitting}
                className="px-3 py-1.5 rounded-md bg-white/5 hover:bg-white/10 text-neutral-300 text-sm transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={submit}
                disabled={submitting}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Save size={13} />
                )}
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─ Table list ─ */}
      {tables === null ? (
        <div className="rounded-md bg-[#11141a] border border-white/10 h-24 flex items-center justify-center">
          <Loader2 size={16} className="animate-spin text-neutral-500" />
        </div>
      ) : tables.length === 0 ? (
        <div className="rounded-md bg-[#11141a] border border-dashed border-white/10 p-8 text-center">
          <p className="text-sm text-neutral-500">席が登録されていません。</p>
        </div>
      ) : (
        <div className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.02] text-[11px] uppercase tracking-wider text-neutral-500">
              <tr>
                <th className="text-left px-4 py-2 font-semibold">席名</th>
                <th className="text-left px-4 py-2 font-semibold">物理サイズ</th>
                <th className="text-left px-4 py-2 font-semibold">投影解像度</th>
                <th className="text-left px-4 py-2 font-semibold">PJ × ゾーン</th>
                <th className="text-left px-4 py-2 font-semibold">デフォルト</th>
                <th className="text-right px-4 py-2 font-semibold w-24">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {tables.map((t) => (
                <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="text-white font-medium">{t.name}</div>
                    {t.note && (
                      <div className="text-[11px] text-neutral-500 truncate max-w-[18ch]">
                        {t.note}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-neutral-300 tabular-nums">
                    {t.table_width_mm} × {t.table_height_mm} mm
                  </td>
                  <td className="px-4 py-2.5 text-neutral-300 tabular-nums">
                    {t.full_width} × {t.full_height} px
                  </td>
                  <td className="px-4 py-2.5 text-neutral-400 tabular-nums">
                    {t.pj_count}台 × {t.zone_count}ゾーン
                  </td>
                  <td className="px-4 py-2.5">
                    {t.is_default ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-300">
                        <Check size={12} />
                        デフォルト
                      </span>
                    ) : (
                      <button
                        onClick={() => setAsDefault(t)}
                        className="text-xs text-neutral-500 hover:text-white transition-colors"
                      >
                        デフォルトに設定
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => startEdit(t)}
                        className="w-7 h-7 rounded hover:bg-white/10 text-neutral-400 hover:text-white flex items-center justify-center transition-colors"
                        title="編集"
                      >
                        <Edit3 size={13} />
                      </button>
                      <button
                        onClick={() => handleDelete(t)}
                        disabled={tables.length <= 1}
                        className="w-7 h-7 rounded hover:bg-red-500/15 text-neutral-500 hover:text-red-300 flex items-center justify-center transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        title={tables.length <= 1 ? "最後の席は削除できません" : "削除"}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Form fields ────────────────────────────────────────────────────

function NumberField({
  label,
  unit,
  value,
  onChange,
}: {
  label: string;
  unit: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="block text-[10px] font-medium text-neutral-500 mb-0.5">
        {label}
      </label>
      <div className="relative">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value) || 0)}
          className="w-full bg-[#0a0d12] border border-white/10 rounded px-2 py-1.5 text-sm text-white tabular-nums focus:border-blue-400/50 focus:outline-none pr-8"
        />
        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-neutral-600 pointer-events-none">
          {unit}
        </span>
      </div>
    </div>
  );
}

function Computed({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-neutral-600">
        {label}
      </div>
      <div className="text-white tabular-nums">{value}</div>
    </div>
  );
}
