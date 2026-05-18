"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronRight,
  Plus,
  Loader2,
  AlertTriangle,
  Trash2,
  Settings,
} from "lucide-react";
import {
  fetchStoryboards,
  deleteStoryboard,
  fetchTables,
  type StoryboardListItem,
  type ProjectionTable,
} from "@/lib/api";

const STATUS_META: Record<
  string,
  { label: string; color: string; nextLabel: string }
> = {
  draft: {
    label: "下書き",
    color: "text-neutral-400 bg-neutral-500/15 border-neutral-500/30",
    nextLabel: "台本を編集",
  },
  images_ready: {
    label: "画像完了",
    color: "text-blue-300 bg-blue-500/15 border-blue-500/30",
    nextLabel: "動画へ",
  },
  video_ready: {
    label: "動画完了",
    color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
    nextLabel: "投影",
  },
};

function relativeJa(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "たった今";
  if (min < 60) return `${min}分前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}時間前`;
  const day = Math.floor(hr / 24);
  if (day === 1) return "昨日";
  if (day < 7) return `${day}日前`;
  return new Date(iso).toLocaleDateString("ja-JP", { month: "short", day: "numeric" });
}

export default function CreateLandingPage() {
  const router = useRouter();
  const [list, setList] = useState<StoryboardListItem[] | null>(null);
  const [tables, setTables] = useState<ProjectionTable[]>([]);
  const [error, setError] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function load() {
    setError(false);
    try {
      const [data, tbls] = await Promise.all([
        fetchStoryboards(),
        fetchTables().catch(() => [] as ProjectionTable[]),
      ]);
      data.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setList(data);
      setTables(tbls);
    } catch {
      setError(true);
      setList([]);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDelete(id: number) {
    if (!confirm("この台本を削除しますか?(画像・動画も削除されます)")) return;
    setDeletingId(id);
    try {
      await deleteStoryboard(id);
      await load();
    } catch {
      alert("削除に失敗しました");
    } finally {
      setDeletingId(null);
    }
  }

  function tableNameFor(id: number | null | undefined): string {
    if (!id) return "席未指定";
    return tables.find((t) => t.id === id)?.name ?? `席 #${id}`;
  }

  const noTables = tables.length === 0;

  return (
    <div className="max-w-4xl space-y-6">
      {/* ─ Header ─ */}
      <div className="flex items-end justify-between gap-3 pb-3 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white">台本を作る</h1>
          <p className="text-xs text-neutral-500 mt-1">
            新規作成、または既存の下書きから再開できます。
          </p>
        </div>
        <button
          onClick={() => router.push("/create/new")}
          disabled={noTables}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title={noTables ? "席を先に登録してください" : ""}
        >
          <Plus size={14} />
          新規台本
        </button>
      </div>

      {/* ─ No tables warning ─ */}
      {noTables && (
        <div className="rounded-md bg-amber-500/10 border border-amber-500/30 p-3 text-sm flex items-start gap-2.5">
          <AlertTriangle size={14} className="text-amber-300 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-amber-200 font-medium">
              席 (テーブル) が登録されていません
            </p>
            <p className="text-amber-300/70 text-xs mt-0.5">
              動画は席のサイズに合わせて作るため、先に席を登録してください。
            </p>
          </div>
          <Link
            href="/tables"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 text-xs font-medium transition-colors shrink-0"
          >
            <Settings size={11} />
            席を登録
          </Link>
        </div>
      )}

      {/* ─ List ─ */}
      <section>
        <h2 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider mb-2">
          既存の台本 {list && list.length > 0 ? `(${list.length}件)` : ""}
        </h2>
        {list === null ? (
          <div className="rounded-md bg-[#11141a] border border-white/10 h-24 flex items-center justify-center">
            <Loader2 size={16} className="animate-spin text-neutral-500" />
          </div>
        ) : error ? (
          <div className="rounded-md bg-[#11141a] border border-red-500/15 p-4 text-center space-y-2">
            <AlertTriangle size={16} className="text-red-400/60 mx-auto" />
            <p className="text-sm text-neutral-400">読み込み失敗</p>
            <button
              onClick={load}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              再試行
            </button>
          </div>
        ) : list.length === 0 ? (
          <div className="rounded-md bg-[#11141a] border border-dashed border-white/10 p-8 text-center">
            <p className="text-sm text-neutral-500">
              まだ台本はありません。上の「新規台本」から作成します。
            </p>
          </div>
        ) : (
          <div className="rounded-md bg-[#11141a] border border-white/10 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.02] text-[11px] uppercase tracking-wider text-neutral-500">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">タイトル</th>
                  <th className="text-left px-4 py-2 font-semibold">席</th>
                  <th className="text-left px-4 py-2 font-semibold">テーマ</th>
                  <th className="text-left px-4 py-2 font-semibold">状態</th>
                  <th className="text-left px-4 py-2 font-semibold">作成</th>
                  <th className="text-right px-4 py-2 font-semibold w-32">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {list.map((sb) => {
                  const meta = STATUS_META[sb.status] ?? STATUS_META.draft;
                  const isDeleting = deletingId === sb.id;
                  return (
                    <tr
                      key={sb.id}
                      className="hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/create/${sb.id}`}
                          className="text-white font-medium hover:text-blue-300 transition-colors"
                        >
                          {sb.title || "(無題)"}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-neutral-400 text-xs">
                        {tableNameFor(sb.projection_config_id)}
                      </td>
                      <td className="px-4 py-2.5 text-neutral-400 capitalize text-xs">
                        {sb.theme ?? "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${meta.color}`}
                        >
                          {meta.label}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-neutral-500 text-xs tabular-nums">
                        {relativeJa(sb.created_at)}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            href={`/create/${sb.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs text-blue-400 hover:text-white hover:bg-blue-500/20 transition-colors"
                          >
                            {meta.nextLabel}
                            <ChevronRight size={11} />
                          </Link>
                          <button
                            onClick={() => handleDelete(sb.id)}
                            disabled={isDeleting}
                            className="w-7 h-7 rounded hover:bg-red-500/15 text-neutral-500 hover:text-red-300 flex items-center justify-center transition-colors disabled:opacity-50"
                            title="削除"
                          >
                            {isDeleting ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              <Trash2 size={12} />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ─ Advanced link ─ */}
      <div className="text-right pt-2">
        <Link
          href="/generation"
          className="text-[11px] text-neutral-600 hover:text-neutral-400 transition-colors"
        >
          詳細編集モード (上級者向け) →
        </Link>
      </div>
    </div>
  );
}
