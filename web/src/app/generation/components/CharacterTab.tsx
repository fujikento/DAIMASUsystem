"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Upload,
  User,
  Sparkles,
  Loader2,
  CheckCircle2,
  XCircle,
  Image,
  Film,
  Camera,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import {
  fetchCharacterTemplates,
  createCharacterAvatar,
  createCharacterAnimation,
  createCharacterMemorial,
  fetchCharacterJobStatus,
  type CharacterTemplate,
  type CharacterJobStatus,
} from "@/lib/api";

// ── 定数 ─────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  birthday: "バースデー",
  welcome: "ウェルカム",
  surprise: "サプライズ",
  season: "季節イベント",
};

const CATEGORY_ORDER = ["welcome", "birthday", "surprise", "season"];

const THEME_OPTIONS = [
  { value: "ocean", label: "海 Ocean Deep" },
  { value: "zen", label: "和 Japanese Zen" },
  { value: "fire", label: "火 Fire & Passion" },
  { value: "forest", label: "森 Forest Spirit" },
  { value: "gold", label: "宝 Golden Luxury" },
  { value: "space", label: "宇宙 Space Odyssey" },
  { value: "fairytale", label: "物語 Fairy Tale" },
];

const PROVIDER_OPTIONS = [
  { value: "liveportrait", label: "LivePortrait (ローカル)" },
  { value: "hedra", label: "Hedra AI (API)" },
];

type GenerationType = "avatar" | "animation" | "memorial";

// ── メインコンポーネント ──────────────────────────────────────────

export default function CharacterTab() {
  // テンプレート
  const [templates, setTemplates] = useState<Record<string, CharacterTemplate>>({});
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);

  // 生成設定
  const [generationType, setGenerationType] = useState<GenerationType>("avatar");
  const [guestName, setGuestName] = useState("");
  const [theme, setTheme] = useState("ocean");
  const [provider, setProvider] = useState("liveportrait");
  const [zoneId, setZoneId] = useState(1);

  // 写真アップロード
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 生成状態
  const [generating, setGenerating] = useState(false);
  const [currentJob, setCurrentJob] = useState<CharacterJobStatus | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // テンプレート読み込み
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const data = await fetchCharacterTemplates(selectedCategory ?? undefined);
      setTemplates(data);
    } catch {
      // silent
    }
    setTemplatesLoading(false);
  }, [selectedCategory]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // フィードバック
  const showFeedback = useCallback((type: "success" | "error", message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 5000);
  }, []);

  // 写真選択ハンドラー
  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPhotoPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  }

  function clearPhoto() {
    setPhotoFile(null);
    setPhotoPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // ジョブポーリング
  function startPolling(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchCharacterJobStatus(jobId);
        setCurrentJob(status);
        if (status.status === "complete" || status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setGenerating(false);
          if (status.status === "complete") {
            showFeedback("success", "キャラクター生成が完了しました");
          } else {
            showFeedback("error", `生成に失敗: ${status.error || "不明なエラー"}`);
          }
        }
      } catch {
        // silent
      }
    }, 2000);
  }

  // クリーンアップ
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // 生成実行
  async function handleGenerate() {
    if (!photoFile) {
      showFeedback("error", "写真を選択してください");
      return;
    }

    setGenerating(true);
    setCurrentJob(null);

    const formData = new FormData();
    formData.append("photo", photoFile);
    formData.append("guest_name", guestName);

    try {
      let result: CharacterJobStatus;

      if (generationType === "avatar") {
        formData.append("theme", theme);
        formData.append("template_id", selectedTemplate || "welcome_elegant");
        formData.append("zone_id", String(zoneId));
        result = await createCharacterAvatar(formData);
      } else if (generationType === "animation") {
        formData.append("template_id", selectedTemplate || "birthday_cake");
        formData.append("zone_id", String(zoneId));
        formData.append("provider", provider);
        result = await createCharacterAnimation(formData);
      } else {
        formData.append("theme", theme);
        result = await createCharacterMemorial(formData);
      }

      setCurrentJob(result);
      showFeedback("success", result.message);
      startPolling(result.job_id);
    } catch (err) {
      setGenerating(false);
      const msg = err instanceof Error ? err.message : "生成開始に失敗しました";
      showFeedback("error", msg);
    }
  }

  // テンプレートをカテゴリ別にグループ化
  const groupedTemplates: Record<string, [string, CharacterTemplate][]> = {};
  for (const [id, tmpl] of Object.entries(templates)) {
    const cat = tmpl.category;
    if (!groupedTemplates[cat]) groupedTemplates[cat] = [];
    groupedTemplates[cat].push([id, tmpl]);
  }

  // 生成タイプに対応するデフォルトカテゴリ
  const typeToDefaultCategory: Record<GenerationType, string> = {
    avatar: "welcome",
    animation: "birthday",
    memorial: "welcome",
  };

  return (
    <div className="space-y-6">
      {/* フィードバック */}
      {feedback && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm ${
            feedback.type === "success"
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/15"
              : "bg-red-500/10 text-red-400 border border-red-500/15"
          }`}
        >
          {feedback.type === "success" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左カラム: 写真アップロード + 設定 */}
        <div className="lg:col-span-1 space-y-5">
          {/* 生成タイプ選択 */}
          <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
            <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
              生成タイプ
            </h3>
            <div className="space-y-2">
              {[
                { type: "avatar" as GenerationType, icon: <User size={16} />, label: "ウェルカムアバター", desc: "来店時の歓迎演出" },
                { type: "animation" as GenerationType, icon: <Film size={16} />, label: "キャラクターアニメーション", desc: "バースデー・サプライズ演出" },
                { type: "memorial" as GenerationType, icon: <Camera size={16} />, label: "メモリアルフォト", desc: "退店時のお土産画像" },
              ].map((item) => (
                <button
                  key={item.type}
                  onClick={() => {
                    setGenerationType(item.type);
                    setSelectedCategory(null);
                    setSelectedTemplate(null);
                  }}
                  className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                    generationType === item.type
                      ? "bg-blue-500/[0.10] border-blue-400/30 text-blue-300"
                      : "bg-[#132040] border-blue-400/[0.10] text-slate-400 hover:text-white hover:border-blue-400/[0.20]"
                  }`}
                >
                  <span className="mt-0.5 flex-shrink-0">{item.icon}</span>
                  <div>
                    <p className="text-sm font-medium">{item.label}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 写真アップロード */}
          <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
            <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
              ゲスト写真
            </h3>

            {photoPreview ? (
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={photoPreview}
                  alt="Guest photo"
                  className="w-full h-48 object-cover rounded-xl border border-blue-400/[0.10]"
                />
                <button
                  onClick={clearPhoto}
                  className="absolute top-2 right-2 p-1.5 bg-[#080f1a]/80 hover:bg-red-500/30 text-slate-300 hover:text-white rounded-lg transition-colors"
                >
                  <XCircle size={16} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full h-48 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-blue-400/[0.15] hover:border-blue-400/30 bg-[#080f1a] transition-colors cursor-pointer"
              >
                <Upload size={28} className="text-slate-600" />
                <div className="text-center">
                  <p className="text-sm text-slate-400">クリックして写真を選択</p>
                  <p className="text-xs text-slate-600 mt-1">JPG / PNG</p>
                </div>
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handlePhotoSelect}
              className="hidden"
            />

            {/* ゲスト名 */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">ゲスト名</label>
              <input
                type="text"
                value={guestName}
                onChange={(e) => setGuestName(e.target.value)}
                placeholder="田中 太郎"
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white placeholder:text-slate-600 focus:border-blue-500/40 focus:outline-none"
              />
            </div>
          </div>

          {/* 生成パラメータ */}
          <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
            <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
              生成設定
            </h3>

            {/* テーマ (avatar/memorial) */}
            {(generationType === "avatar" || generationType === "memorial") && (
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">テーマ</label>
                <div className="relative">
                  <select
                    value={theme}
                    onChange={(e) => setTheme(e.target.value)}
                    className="w-full pl-3 pr-8 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none appearance-none"
                  >
                    {THEME_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                </div>
              </div>
            )}

            {/* プロバイダー (animation) */}
            {generationType === "animation" && (
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">プロバイダー</label>
                <div className="relative">
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full pl-3 pr-8 py-2 bg-[#132040] border border-blue-400/[0.12] rounded-xl text-sm text-white focus:border-blue-500/40 focus:outline-none appearance-none"
                  >
                    {PROVIDER_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                </div>
              </div>
            )}

            {/* 区画選択 (avatar/animation) */}
            {generationType !== "memorial" && (
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">投影区画</label>
                <div className="flex gap-2">
                  {[1, 2, 3, 4].map((z) => (
                    <button
                      key={z}
                      onClick={() => setZoneId(z)}
                      className={`flex-1 py-2 rounded-xl text-xs font-medium border transition-all ${
                        zoneId === z
                          ? "bg-purple-500/10 border-purple-500/20 text-purple-400"
                          : "bg-[#132040] border-blue-400/[0.10] text-slate-500 hover:text-slate-300 hover:border-blue-400/[0.20]"
                      }`}
                    >
                      Zone {z}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 生成ボタン */}
            <button
              onClick={handleGenerate}
              disabled={generating || !photoFile}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-40 rounded-xl text-sm transition-colors"
              style={{
                boxShadow: generating || !photoFile ? "none" : "0 0 20px rgba(59,130,246,0.25)",
              }}
            >
              {generating ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
              {generating ? "生成中..." : "生成開始"}
            </button>
          </div>

          {/* ジョブステータス */}
          {currentJob && (
            <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
                ジョブステータス
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">ID</span>
                  <span className="text-xs font-mono text-slate-300">{currentJob.job_id}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">ステータス</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      currentJob.status === "complete"
                        ? "bg-emerald-500/15 text-emerald-400"
                        : currentJob.status === "failed"
                        ? "bg-red-500/15 text-red-400"
                        : "bg-amber-500/15 text-amber-400"
                    }`}
                  >
                    {currentJob.status === "complete" ? "完了"
                      : currentJob.status === "failed" ? "失敗"
                      : "処理中"}
                  </span>
                </div>
                {currentJob.error && (
                  <p className="text-xs text-red-400 bg-red-500/[0.05] p-2 rounded-lg">
                    {currentJob.error}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 右カラム: テンプレート選択グリッド */}
        <div className="lg:col-span-2 space-y-5">
          {/* カテゴリフィルター */}
          <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
                テンプレート選択
              </h3>
              <button
                onClick={loadTemplates}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-400/[0.08] hover:bg-blue-400/[0.12] text-slate-400 hover:text-white rounded-lg text-xs transition-colors"
              >
                <RefreshCw size={12} />
                更新
              </button>
            </div>

            {/* カテゴリタブ */}
            <div className="flex gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                  selectedCategory === null
                    ? "bg-blue-500/[0.10] border-blue-400/30 text-blue-300"
                    : "bg-[#132040] border-blue-400/[0.10] text-slate-400 hover:text-white"
                }`}
              >
                全て
              </button>
              {CATEGORY_ORDER.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    selectedCategory === cat
                      ? "bg-blue-500/[0.10] border-blue-400/30 text-blue-300"
                      : "bg-[#132040] border-blue-400/[0.10] text-slate-400 hover:text-white"
                  }`}
                >
                  {CATEGORY_LABELS[cat] || cat}
                </button>
              ))}
            </div>

            {/* テンプレートグリッド */}
            {templatesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={20} className="animate-spin text-slate-500" />
              </div>
            ) : Object.keys(templates).length === 0 ? (
              <div className="text-center py-12">
                <Image size={32} className="mx-auto text-slate-700 mb-3" />
                <p className="text-sm text-slate-400">テンプレートがありません</p>
              </div>
            ) : (
              <div className="space-y-6">
                {CATEGORY_ORDER.filter((cat) => groupedTemplates[cat]).map((cat) => (
                  <div key={cat} className="space-y-3">
                    <h4 className="text-xs font-medium text-slate-400 flex items-center gap-2">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{
                          background:
                            cat === "birthday" ? "#f59e0b"
                              : cat === "welcome" ? "#3b82f6"
                              : cat === "surprise" ? "#a855f7"
                              : "#10b981",
                        }}
                      />
                      {CATEGORY_LABELS[cat]}
                      <span className="text-slate-600">({groupedTemplates[cat].length})</span>
                    </h4>
                    <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                      {groupedTemplates[cat].map(([id, tmpl]) => {
                        const isSelected = selectedTemplate === id;
                        return (
                          <button
                            key={id}
                            onClick={() => setSelectedTemplate(isSelected ? null : id)}
                            className={`text-left rounded-xl border overflow-hidden transition-all ${
                              isSelected
                                ? "border-blue-400 ring-2 ring-blue-400/40"
                                : "border-blue-400/[0.10] hover:border-blue-400/30"
                            }`}
                          >
                            {/* サムネイルプレースホルダ */}
                            <div
                              className="relative h-24 flex items-center justify-center"
                              style={{
                                background:
                                  cat === "birthday"
                                    ? "linear-gradient(135deg, #1a1100 0%, #2d1800 100%)"
                                    : cat === "welcome"
                                    ? "linear-gradient(135deg, #001a33 0%, #002040 100%)"
                                    : cat === "surprise"
                                    ? "linear-gradient(135deg, #1a0033 0%, #200040 100%)"
                                    : "linear-gradient(135deg, #001a0f 0%, #002015 100%)",
                              }}
                            >
                              <Film
                                size={24}
                                className={
                                  cat === "birthday" ? "text-amber-600/40"
                                    : cat === "welcome" ? "text-blue-600/40"
                                    : cat === "surprise" ? "text-purple-600/40"
                                    : "text-emerald-600/40"
                                }
                              />
                              {isSelected && (
                                <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-blue-400 flex items-center justify-center">
                                  <CheckCircle2 size={12} className="text-[#080f1a]" />
                                </div>
                              )}
                              <div className="absolute bottom-1.5 right-2 text-[10px] font-mono text-slate-600">
                                {tmpl.duration}s
                              </div>
                            </div>
                            <div className="px-3 py-2.5 bg-[#080f1a]">
                              <p className="text-xs font-medium text-slate-200 truncate">{tmpl.name}</p>
                              <p className="text-[10px] text-slate-500 mt-0.5 truncate">{tmpl.description}</p>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 選択中のテンプレート詳細 */}
          {selectedTemplate && templates[selectedTemplate] && (
            <div className="bg-[#0e1d32] rounded-2xl p-5 border border-blue-400/[0.10] space-y-3">
              <h3 className="text-xs font-medium text-slate-500 uppercase tracking-widest">
                選択中のテンプレート
              </h3>
              <div className="flex items-center gap-4">
                <div
                  className="w-20 h-14 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "linear-gradient(135deg, #0d1f38 0%, #132040 100%)" }}
                >
                  <Film size={20} className="text-blue-400/40" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white">{templates[selectedTemplate].name}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{templates[selectedTemplate].description}</p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-400/[0.08] text-slate-400">
                      {CATEGORY_LABELS[templates[selectedTemplate].category] || templates[selectedTemplate].category}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {templates[selectedTemplate].duration}秒
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      ID: {selectedTemplate}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 生成プレビュー (ジョブ完了時) */}
          {currentJob?.status === "complete" && currentJob.output_path && (
            <div className="bg-[#0e1d32] rounded-2xl p-5 border border-emerald-400/[0.15] space-y-3">
              <h3 className="text-xs font-medium text-emerald-400 uppercase tracking-widest flex items-center gap-2">
                <CheckCircle2 size={13} />
                生成完了
              </h3>
              <div className="bg-[#080f1a] rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">出力ファイル</span>
                  <span className="text-xs font-mono text-slate-300 truncate ml-4">
                    {currentJob.output_path.split("/").pop()}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">ジョブタイプ</span>
                  <span className="text-xs text-slate-300">
                    {currentJob.job_type === "avatar" ? "アバター"
                      : currentJob.job_type === "animation" ? "アニメーション"
                      : "メモリアル"}
                  </span>
                </div>
                {currentJob.guest_name && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">ゲスト名</span>
                    <span className="text-xs text-slate-300">{currentJob.guest_name}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
