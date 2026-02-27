"use client";

import { useEffect, useState } from "react";
import { Cake, Plus, Upload, RefreshCw, Wand2, Film, ChevronDown } from "lucide-react";
import {
  fetchBirthdays,
  createBirthday,
  updateBirthdayStatus,
  animateBirthday,
  fetchBirthdayTemplates,
  type Birthday,
  type AnimationTemplate,
} from "@/lib/api";

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: "待機中", color: "text-blue-400", bg: "bg-blue-500/10" },
  processing: { label: "生成中", color: "text-yellow-400", bg: "bg-yellow-500/10" },
  ready: { label: "準備完了", color: "text-green-400", bg: "bg-green-500/10" },
  played: { label: "再生済み", color: "text-neutral-400", bg: "bg-neutral-500/10" },
};

export default function BirthdayPage() {
  const [birthdays, setBirthdays] = useState<Birthday[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [templates, setTemplates] = useState<Record<string, AnimationTemplate>>({});

  // アニメーション生成パネル
  const [animatingId, setAnimatingId] = useState<number | null>(null);
  const [animTemplateId, setAnimTemplateId] = useState("birthday_cake");
  const [animZoneId, setAnimZoneId] = useState(1);
  const [animProvider, setAnimProvider] = useState("liveportrait");
  const [animLoading, setAnimLoading] = useState(false);

  // Create form
  const [guestName, setGuestName] = useState("");
  const [reservationDate, setReservationDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [photo, setPhoto] = useState<File | null>(null);

  // Feedback
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    loadBirthdays();
    fetchBirthdayTemplates().then(setTemplates).catch(() => {});
  }, []);

  async function loadBirthdays() {
    setLoading(true);
    try {
      const data = await fetchBirthdays();
      setBirthdays(data);
    } catch {}
    setLoading(false);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const formData = new FormData();
    formData.append("guest_name", guestName);
    formData.append("reservation_date", reservationDate);
    if (photo) formData.append("photo", photo);

    try {
      await createBirthday(formData);
      setShowCreate(false);
      setGuestName("");
      setPhoto(null);
      loadBirthdays();
      showFeedback("success", "予約を作成しました");
    } catch {
      showFeedback("error", "予約の作成に失敗しました");
    }
  }

  async function handleStatusChange(id: number, newStatus: string) {
    try {
      await updateBirthdayStatus(id, newStatus);
      loadBirthdays();
    } catch {
      showFeedback("error", "ステータスの更新に失敗しました");
    }
  }

  async function handleAnimate(id: number) {
    setAnimLoading(true);
    try {
      await animateBirthday(id, {
        template_id: animTemplateId,
        zone_id: animZoneId,
        provider: animProvider,
      });
      showFeedback("success", "アニメーション生成を開始しました");
      setAnimatingId(null);
      loadBirthdays();
    } catch {
      showFeedback("error", "アニメーション生成の開始に失敗しました（写真がアップロードされているか確認してください）");
    }
    setAnimLoading(false);
  }

  function showFeedback(type: "success" | "error", message: string) {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4000);
  }

  // 今日以降の予約と過去の予約を分離
  const today = new Date().toISOString().split("T")[0];
  const upcoming = birthdays.filter((b) => b.reservation_date >= today);
  const past = birthdays.filter((b) => b.reservation_date < today);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">誕生日予約</h2>
          <p className="text-neutral-400 text-sm mt-1">
            写真からキャラクターを生成し、サプライズ演出を管理
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={loadBirthdays}
            className="flex items-center gap-2 px-4 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white rounded-xl text-sm transition-colors"
          >
            <RefreshCw size={16} /> 更新
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> 新規予約
          </button>
        </div>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={`px-4 py-3 rounded-xl text-sm ${
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
              : "bg-red-500/10 text-red-400 border border-red-500/15"
          }`}
        >
          {feedback.message}
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-[#141414] rounded-2xl p-6 border border-white/[0.06] space-y-4"
        >
          <h3 className="font-medium text-blue-400">新規誕生日予約</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">
                ゲスト名
              </label>
              <input
                type="text"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
                placeholder="山田 太郎"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1.5">予約日</label>
              <input
                type="date"
                value={reservationDate}
                onChange={(e) => setReservationDate(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-blue-500/40 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-neutral-400 mb-1.5">
              <Upload size={12} className="inline mr-1" />
              ゲストの写真（キャラクター生成用）
            </label>
            <input
              type="file"
              onChange={(e) => setPhoto(e.target.files?.[0] || null)}
              accept="image/*"
              className="w-full text-sm text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-medium file:bg-white/[0.06] file:text-white hover:file:bg-white/[0.1]"
            />
            <p className="text-xs text-neutral-500 mt-1">
              顔がはっきり写った正面写真を推奨
            </p>
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-xl text-sm transition-colors"
            >
              予約作成
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

      {/* Upcoming */}
      <div>
        <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-widest mb-3">
          今後の予約 ({upcoming.length})
        </h3>
        {loading ? (
          <p className="text-neutral-400 text-sm">読み込み中...</p>
        ) : upcoming.length === 0 ? (
          <div className="text-center py-10 bg-[#141414] rounded-2xl border border-white/[0.06]">
            <Cake size={40} className="mx-auto text-neutral-500 mb-3" />
            <p className="text-neutral-400">今後の誕生日予約はありません</p>
          </div>
        ) : (
          <div className="space-y-3">
            {upcoming.map((b) => {
              const statusCfg = STATUS_CONFIG[b.status] || STATUS_CONFIG.pending;
              const isToday = b.reservation_date === today;
              const isAnimOpen = animatingId === b.id;
              return (
                <div key={b.id}>
                  <div
                    className={`p-4 rounded-2xl border ${
                      isToday
                        ? "bg-blue-500/5 border-blue-500/15"
                        : "bg-[#141414] border-white/[0.06]"
                    } ${isAnimOpen ? "rounded-b-none border-b-0" : ""}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        {/* Photo indicator */}
                        <div className="w-12 h-12 rounded-full bg-white/[0.04] flex items-center justify-center text-neutral-500">
                          {b.photo_path ? (
                            <Cake size={20} className="text-pink-400" />
                          ) : (
                            <Upload size={16} />
                          )}
                        </div>
                        <div>
                          <h4 className="font-medium text-white">
                            {b.guest_name}{" "}
                            <span className="text-neutral-400 text-sm">様</span>
                          </h4>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-xs text-neutral-500">
                              {b.reservation_date}
                            </span>
                            {isToday && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">
                                本日
                              </span>
                            )}
                            {b.character_video_path && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-400">
                                <Film size={10} className="inline mr-1" />
                                動画あり
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs px-3 py-1 rounded-full ${statusCfg.bg} ${statusCfg.color}`}
                        >
                          {statusCfg.label}
                        </span>

                        {/* アニメーション生成ボタン */}
                        {b.photo_path && b.status !== "played" && (
                          <button
                            onClick={() => setAnimatingId(isAnimOpen ? null : b.id)}
                            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-xl transition-colors ${
                              isAnimOpen
                                ? "bg-pink-500 text-white"
                                : "bg-pink-500/10 text-pink-400 hover:bg-pink-500/20"
                            }`}
                          >
                            <Wand2 size={12} />
                            アニメ生成
                            <ChevronDown
                              size={12}
                              className={`transition-transform ${isAnimOpen ? "rotate-180" : ""}`}
                            />
                          </button>
                        )}

                        {/* Status progression buttons */}
                        {b.status === "pending" && !b.photo_path && (
                          <span className="text-xs px-3 py-1 bg-slate-700/50 text-slate-500 rounded-xl">
                            写真未アップロード
                          </span>
                        )}
                        {b.status === "ready" && (
                          <button
                            onClick={() => handleStatusChange(b.id, "played")}
                            className="text-xs px-3 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-xl transition-colors"
                          >
                            再生済みにする
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Animation panel */}
                  {isAnimOpen && (
                    <div className="bg-[#111111] border border-white/[0.06] border-t-0 rounded-b-2xl p-4 space-y-4">
                      <h4 className="text-sm font-medium text-pink-400">
                        <Wand2 size={14} className="inline mr-1.5" />
                        アニメーション生成設定 — {b.guest_name} 様
                      </h4>
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1.5">テンプレート</label>
                          <select
                            value={animTemplateId}
                            onChange={(e) => setAnimTemplateId(e.target.value)}
                            className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-pink-500 focus:outline-none"
                          >
                            {Object.entries(templates).map(([k, v]) => (
                              <option key={k} value={k}>
                                {v.name} ({v.duration}秒)
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1.5">投影区画</label>
                          <select
                            value={animZoneId}
                            onChange={(e) => setAnimZoneId(Number(e.target.value))}
                            className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-pink-500 focus:outline-none"
                          >
                            {[1, 2, 3, 4].map((z) => (
                              <option key={z} value={z}>
                                Zone {z}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1.5">プロバイダー</label>
                          <select
                            value={animProvider}
                            onChange={(e) => setAnimProvider(e.target.value)}
                            className="w-full px-3 py-2 bg-[#1c1c1c] border border-white/[0.08] rounded-xl text-sm text-white placeholder:text-neutral-600 focus:border-pink-500 focus:outline-none"
                          >
                            <option value="liveportrait">LivePortrait (ローカル)</option>
                            <option value="hedra">Hedra AI (API)</option>
                          </select>
                        </div>
                      </div>

                      {/* Template description */}
                      {templates[animTemplateId] && (
                        <p className="text-xs text-neutral-500">
                          {templates[animTemplateId].description}
                        </p>
                      )}

                      <div className="flex gap-3">
                        <button
                          onClick={() => handleAnimate(b.id)}
                          disabled={animLoading}
                          className="flex items-center gap-2 px-5 py-2 bg-pink-500 hover:bg-pink-400 disabled:opacity-40 text-white rounded-xl text-sm font-medium transition-colors"
                        >
                          {animLoading ? (
                            <RefreshCw size={14} className="animate-spin" />
                          ) : (
                            <Wand2 size={14} />
                          )}
                          アニメーション生成開始
                        </button>
                        <button
                          onClick={() => setAnimatingId(null)}
                          className="px-4 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white rounded-xl text-sm transition-colors"
                        >
                          閉じる
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Past */}
      {past.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-widest mb-3">
            過去の予約 ({past.length})
          </h3>
          <div className="space-y-2">
            {past.slice(0, 10).map((b) => (
              <div
                key={b.id}
                className="p-3 rounded-2xl bg-[#111111] border border-white/[0.04] flex items-center justify-between text-sm"
              >
                <span className="text-neutral-400">{b.guest_name} 様</span>
                <div className="flex items-center gap-3">
                  {b.character_video_path && (
                    <span className="text-xs text-green-400">
                      <Film size={10} className="inline mr-1" />
                      動画あり
                    </span>
                  )}
                  <span className="text-neutral-500">{b.reservation_date}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
