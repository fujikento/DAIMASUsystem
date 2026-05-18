"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  ChevronRight,
  Clock,
  Plus,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon,
  Video,
  Trash2,
} from "lucide-react";
import {
  fetchStoryboards,
  deleteStoryboard,
  type StoryboardListItem,
} from "@/lib/api";

const STATUS_META: Record<
  string,
  { label: string; color: string; nextLabel: string; icon: React.ReactNode }
> = {
  draft: {
    label: "下書き",
    color: "text-neutral-400 bg-neutral-500/15 border-neutral-500/30",
    nextLabel: "台本を編集",
    icon: <Sparkles size={12} />,
  },
  images_ready: {
    label: "画像できた",
    color: "text-blue-300 bg-blue-500/15 border-blue-500/30",
    nextLabel: "動画にする",
    icon: <ImageIcon size={12} />,
  },
  video_ready: {
    label: "動画完成",
    color: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
    nextLabel: "投影する",
    icon: <Video size={12} />,
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
  const [error, setError] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function load() {
    setError(false);
    try {
      const data = await fetchStoryboards();
      data.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setList(data);
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

  return (
    <div className="max-w-3xl mx-auto space-y-10 py-4">
      {/* ─ Header ─ */}
      <div className="text-center space-y-3">
        <p className="text-xs font-semibold tracking-[0.25em] uppercase text-blue-400/80">
          Step 1 of 4
        </p>
        <h1 className="text-4xl font-bold text-white tracking-tight">
          何を作りますか?
        </h1>
        <p className="text-neutral-400 text-base">
          新しく作るか、前回の続きから始められます
        </p>
      </div>

      {/* ─ New storyboard CTA (primary) ─ */}
      <button
        onClick={() => router.push("/create/new")}
        className="group w-full text-left rounded-3xl p-8 bg-gradient-to-br from-blue-600 via-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 transition-all shadow-2xl shadow-blue-900/40 hover:shadow-blue-800/60 hover:scale-[1.01] active:scale-[0.99]"
      >
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-white/15 border border-white/20 flex items-center justify-center shrink-0 group-hover:bg-white/25 transition-colors">
            <Plus size={28} className="text-white" strokeWidth={2.5} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-2xl font-bold text-white mb-1">
              新しい台本をつくる
            </h2>
            <p className="text-white/80 text-sm leading-relaxed">
              テーマを選んで、AIに台本を書かせて、画像と動画を作ります。最短5分。
            </p>
          </div>
          <ChevronRight
            size={28}
            className="text-white/80 shrink-0 group-hover:translate-x-1 transition-transform"
          />
        </div>
      </button>

      {/* ─ Resume section ─ */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-300 tracking-wide">
            続きから
          </h3>
          {list && list.length > 0 && (
            <span className="text-xs text-neutral-600">
              {list.length}件の作品
            </span>
          )}
        </div>

        {list === null ? (
          <div className="rounded-2xl bg-[#0e1d32] border border-blue-400/10 h-32 flex items-center justify-center">
            <Loader2 size={20} className="animate-spin text-neutral-600" />
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-[#0e1d32] border border-red-500/15 p-6 text-center space-y-2">
            <AlertCircle size={20} className="text-red-400/60 mx-auto" />
            <p className="text-sm text-neutral-400">
              読み込みに失敗しました
            </p>
            <button
              onClick={load}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              再試行
            </button>
          </div>
        ) : list.length === 0 ? (
          <div className="rounded-2xl bg-[#0e1d32] border border-dashed border-neutral-700 p-8 text-center">
            <Sparkles size={24} className="text-neutral-700 mx-auto mb-2" />
            <p className="text-sm text-neutral-500">
              まだ作品はありません。上のボタンから始めましょう。
            </p>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {list.map((sb) => {
              const meta = STATUS_META[sb.status] ?? STATUS_META.draft;
              const isDeleting = deletingId === sb.id;
              return (
                <li
                  key={sb.id}
                  className="group rounded-2xl bg-[#0e1d32] border border-blue-400/10 hover:border-blue-400/30 transition-colors overflow-hidden"
                >
                  <div className="flex items-stretch">
                    <Link
                      href={`/create/${sb.id}`}
                      className="flex-1 flex items-center gap-4 p-4 hover:bg-blue-400/[0.04] transition-colors min-w-0"
                    >
                      <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-[#0a1628] to-[#0d1f38] border border-white/[0.06] flex items-center justify-center shrink-0">
                        {sb.status === "video_ready" ? (
                          <Video size={20} className="text-emerald-400/70" />
                        ) : sb.status === "images_ready" ? (
                          <ImageIcon size={20} className="text-blue-400/70" />
                        ) : (
                          <Sparkles size={20} className="text-neutral-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="text-white text-base font-semibold truncate">
                            {sb.title || "(無題)"}
                          </h4>
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap border ${meta.color}`}
                          >
                            {meta.icon}
                            {meta.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-neutral-500 mt-1">
                          <Clock size={11} />
                          <span>{relativeJa(sb.created_at)}</span>
                          {sb.theme && (
                            <>
                              <span className="text-neutral-700">·</span>
                              <span className="capitalize">{sb.theme}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="hidden sm:flex items-center gap-1.5 text-xs font-medium text-blue-400 shrink-0">
                        <span>{meta.nextLabel}</span>
                        <ChevronRight
                          size={14}
                          className="group-hover:translate-x-0.5 transition-transform"
                        />
                      </div>
                    </Link>
                    <button
                      onClick={() => handleDelete(sb.id)}
                      disabled={isDeleting}
                      className="px-4 border-l border-white/[0.04] text-neutral-700 hover:text-red-400 hover:bg-red-500/5 transition-colors disabled:opacity-50"
                      title="削除"
                    >
                      {isDeleting ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <Trash2 size={16} />
                      )}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ─ Power-user escape hatch ─ */}
      <div className="text-center pt-4">
        <Link
          href="/generation"
          className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
        >
          <CheckCircle2 size={12} />
          詳細編集モードを開く(上級者向け)
        </Link>
      </div>
    </div>
  );
}
