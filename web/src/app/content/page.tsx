"use client";

import { useEffect, useState } from "react";
import { Film, Upload, Trash2, Search } from "lucide-react";
import {
  fetchContents,
  createContent,
  deleteContent,
  type Content,
} from "@/lib/api";
import { DAY_THEMES } from "@/lib/themes";

const CONTENT_TYPES = ["video", "image", "shader"];

export default function ContentPage() {
  const [contents, setContents] = useState<Content[]>([]);
  const [filterTheme, setFilterTheme] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);

  // Upload form state
  const [uploadName, setUploadName] = useState("");
  const [uploadType, setUploadType] = useState("video");
  const [uploadTheme, setUploadTheme] = useState("monday");
  const [uploadDuration, setUploadDuration] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  useEffect(() => {
    loadContents();
  }, []);

  async function loadContents() {
    setLoading(true);
    try {
      const data = await fetchContents();
      setContents(data);
    } catch {
      // API未起動
    }
    setLoading(false);
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;

    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("name", uploadName);
    formData.append("type", uploadType);
    formData.append("theme", uploadTheme);
    if (uploadDuration) formData.append("duration", uploadDuration);

    try {
      await createContent(formData);
      setShowUpload(false);
      setUploadName("");
      setUploadFile(null);
      loadContents();
    } catch (err) {
      alert("アップロードに失敗しました");
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("このコンテンツを削除しますか？")) return;
    try {
      await deleteContent(id);
      setContents(contents.filter((c) => c.id !== id));
    } catch {}
  }

  const filtered = contents.filter((c) => {
    if (filterTheme !== "all" && c.theme !== filterTheme) return false;
    if (searchQuery && !c.name.toLowerCase().includes(searchQuery.toLowerCase()))
      return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">コンテンツ管理</h2>
          <p className="text-neutral-400 mt-1">映像・画像コンテンツの管理</p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
        >
          <Upload size={16} /> アップロード
        </button>
      </div>

      {/* Upload Form */}
      {showUpload && (
        <form
          onSubmit={handleUpload}
          className="bg-[#141414] rounded-2xl p-6 border border-white/[0.06] space-y-4"
        >
          <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-widest">
            新規コンテンツ
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">
                名前
              </label>
              <input
                type="text"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="ウェルカム映像 - 海"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">
                タイプ
              </label>
              <select
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none"
              >
                {CONTENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">
                テーマ
              </label>
              <select
                value={uploadTheme}
                onChange={(e) => setUploadTheme(e.target.value)}
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none"
              >
                {Object.entries(DAY_THEMES).map(([key, t]) => (
                  <option key={key} value={key}>
                    {t.icon} {t.nameJa}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">
                長さ (秒)
              </label>
              <input
                type="number"
                value={uploadDuration}
                onChange={(e) => setUploadDuration(e.target.value)}
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="120"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-neutral-400 mb-1.5">
              ファイル
            </label>
            <input
              type="file"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              accept="video/*,image/*"
              required
              className="w-full text-sm text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-medium file:bg-white/[0.06] file:text-white hover:file:bg-white/[0.1]"
            />
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
            >
              保存
            </button>
            <button
              type="button"
              onClick={() => setShowUpload(false)}
              className="px-6 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white rounded-xl text-sm transition-colors"
            >
              キャンセル
            </button>
          </div>
        </form>
      )}

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-xs">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="検索..."
            className="w-full pl-10 pr-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
          />
        </div>
        <select
          value={filterTheme}
          onChange={(e) => setFilterTheme(e.target.value)}
          className="px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none"
        >
          <option value="all">全テーマ</option>
          {Object.entries(DAY_THEMES).map(([key, t]) => (
            <option key={key} value={key}>
              {t.icon} {t.nameJa}
            </option>
          ))}
        </select>
      </div>

      {/* Content Grid */}
      {loading ? (
        <div className="text-center py-20 text-neutral-400">読み込み中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <Film size={48} className="mx-auto text-neutral-600 mb-4" />
          <p className="text-neutral-400">コンテンツがありません</p>
          <p className="text-neutral-500 text-sm mt-1">
            上の「アップロード」ボタンから追加してください
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map((c) => {
            const themeInfo = DAY_THEMES[c.theme];
            return (
              <div
                key={c.id}
                className="bg-[#141414] rounded-2xl border border-white/[0.06] overflow-hidden"
              >
                {/* Thumbnail placeholder */}
                <div
                  className="aspect-video flex items-center justify-center"
                  style={{
                    backgroundColor: themeInfo
                      ? themeInfo.color + "26"
                      : "rgba(255,255,255,0.04)",
                  }}
                >
                  <Film
                    size={32}
                    style={{ color: themeInfo?.color || "#525252" }}
                  />
                </div>
                <div className="p-3">
                  <h4 className="font-medium text-sm text-white truncate">
                    {c.name}
                  </h4>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-neutral-500">
                      {c.type} {c.duration ? `• ${c.duration}s` : ""}
                    </span>
                    <button
                      onClick={() => handleDelete(c.id)}
                      title="削除"
                      className="p-1 text-slate-600 hover:text-red-400 transition-all"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  {themeInfo && (
                    <span
                      className="inline-block mt-2 text-xs px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: themeInfo.color + "26",
                        color: themeInfo.color,
                      }}
                    >
                      {themeInfo.icon} {themeInfo.dayJa}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
