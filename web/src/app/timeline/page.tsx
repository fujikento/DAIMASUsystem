"use client";

import { useEffect, useState } from "react";
import { Clock, Plus, Trash2 } from "lucide-react";
import {
  fetchTimelines,
  fetchTimeline,
  createTimeline,
  deleteTimeline,
  type TimelineListItem,
  type Timeline,
  type TimelineItem,
} from "@/lib/api";
import { DAY_THEMES } from "@/lib/themes";

export default function TimelinePage() {
  const [timelines, setTimelines] = useState<TimelineListItem[]>([]);
  const [selectedTimeline, setSelectedTimeline] = useState<Timeline | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDay, setCreateDay] = useState("monday");
  const [createCourse, setCreateCourse] = useState("dinner");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTimelines();
  }, []);

  async function loadTimelines() {
    setLoading(true);
    try {
      const data = await fetchTimelines();
      setTimelines(data);
    } catch {}
    setLoading(false);
  }

  async function handleSelect(id: number) {
    try {
      const tl = await fetchTimeline(id);
      setSelectedTimeline(tl);
    } catch {}
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createTimeline({
        name: createName,
        course_type: createCourse,
        day_of_week: createDay,
      });
      setShowCreate(false);
      setCreateName("");
      loadTimelines();
    } catch {}
  }

  async function handleDelete(id: number) {
    if (!confirm("このタイムラインを削除しますか？")) return;
    try {
      await deleteTimeline(id);
      if (selectedTimeline?.id === id) setSelectedTimeline(null);
      loadTimelines();
    } catch {}
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">タイムライン</h2>
          <p className="text-neutral-400 text-sm mt-1">コース進行に合わせた映像タイムライン</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
        >
          <Plus size={16} /> 新規作成
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-[#141414] rounded-2xl p-6 border border-white/[0.06] space-y-4"
        >
          <h3 className="font-medium text-blue-400">新規タイムライン</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">名前</label>
              <input
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="水曜ディナー - Ocean Deep"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">曜日テーマ</label>
              <select
                value={createDay}
                onChange={(e) => setCreateDay(e.target.value)}
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
              >
                {Object.entries(DAY_THEMES).map(([key, t]) => (
                  <option key={key} value={key}>
                    {t.icon} {t.nameJa}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">コースタイプ</label>
              <select
                value={createCourse}
                onChange={(e) => setCreateCourse(e.target.value)}
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
              >
                <option value="lunch">ランチ</option>
                <option value="dinner">ディナー</option>
                <option value="special">スペシャル</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
            >
              作成
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-6 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white rounded-xl text-sm transition-colors"
            >
              キャンセル
            </button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Timeline List */}
        <div className="space-y-3">
          <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-widest">
            タイムライン一覧
          </h3>
          {loading ? (
            <p className="text-neutral-400 text-sm">読み込み中...</p>
          ) : timelines.length === 0 ? (
            <div className="text-center py-10">
              <Clock size={32} className="mx-auto text-neutral-600 mb-3" />
              <p className="text-neutral-400 text-sm">タイムラインがありません</p>
            </div>
          ) : (
            timelines.map((tl) => {
              const theme = DAY_THEMES[tl.day_of_week];
              const isSelected = selectedTimeline?.id === tl.id;
              return (
                <div
                  key={tl.id}
                  onClick={() => handleSelect(tl.id)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? "bg-blue-500/10 border-blue-500/20"
                      : "bg-[#141414] border-white/[0.06] hover:border-white/[0.12]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-sm text-white">{tl.name}</h4>
                      <div className="flex items-center gap-2 mt-1">
                        {theme && (
                          <span
                            className="text-xs px-2 py-0.5 rounded-full"
                            style={{
                              backgroundColor: theme.color + "20",
                              color: theme.color,
                            }}
                          >
                            {theme.icon} {theme.dayJa}
                          </span>
                        )}
                        <span className="text-xs text-neutral-400">
                          {tl.course_type}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(tl.id);
                      }}
                      className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Timeline Editor */}
        <div className="lg:col-span-2">
          {selectedTimeline ? (
            <div className="bg-[#141414] rounded-2xl border border-white/[0.06] p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-bold text-white">{selectedTimeline.name}</h3>
                  <p className="text-neutral-400 text-sm">
                    {selectedTimeline.items.length} アイテム
                  </p>
                </div>
              </div>

              {/* Timeline Visual */}
              <div className="relative">
                {/* Timeline bar */}
                <div className="h-2 bg-neutral-800 rounded-full mb-6" />

                {/* Items */}
                {selectedTimeline.items.length === 0 ? (
                  <p className="text-center text-neutral-400 py-8">
                    アイテムがありません。コンテンツを追加してください。
                  </p>
                ) : (
                  <div className="space-y-2">
                    {selectedTimeline.items
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((item, index) => (
                        <div
                          key={item.id}
                          className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]"
                        >
                          <span className="text-xs text-neutral-600 w-6 text-right font-mono">
                            {index + 1}
                          </span>
                          <div className="flex-1">
                            <p className="text-sm font-medium text-white">
                              {item.content?.name || `コンテンツ #${item.content_id}`}
                            </p>
                            <div className="flex items-center gap-3 mt-1 text-xs text-neutral-400">
                              <span>
                                {formatTime(item.start_time)} ～{" "}
                                {formatTime(item.start_time + item.duration)}
                              </span>
                              <span>ゾーン: {item.zone}</span>
                              <span>{item.transition}</span>
                            </div>
                          </div>
                          <span className="text-xs text-neutral-500">
                            {item.duration}s
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-neutral-400">
              <div className="text-center">
                <Clock size={48} className="mx-auto mb-4 text-neutral-600" />
                <p className="text-neutral-400">左からタイムラインを選択してください</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
