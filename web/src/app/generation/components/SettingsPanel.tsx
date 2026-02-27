"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Key,
  FolderOpen,
  Eye,
  EyeOff,
  Check,
  Loader2,
  AlertCircle,
  Shield,
} from "lucide-react";
import {
  fetchSettings,
  updateSetting,
  type AppSetting,
} from "@/lib/api";

export default function SettingsPanel() {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track which settings are being edited
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set());
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const [errorKeys, setErrorKeys] = useState<Set<string>>(new Set());
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSettings();
      setSettings(data);
    } catch {
      setError("設定の読み込みに失敗しました");
    }
    setLoading(false);
  }

  async function handleSave(key: string) {
    const value = editValues[key];
    if (value === undefined) return;

    setSavingKeys((prev) => new Set(prev).add(key));
    try {
      const updated = await updateSetting(key, value);
      setSettings((prev) => prev.map((s) => (s.key === key ? updated : s)));
      setEditValues((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      // Show saved indicator for 2 seconds
      setSavedKeys((prev) => new Set(prev).add(key));
      setTimeout(() => {
        setSavedKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }, 2000);
    } catch {
      setErrorKeys((prev) => new Set(prev).add(key));
      setTimeout(() => {
        setErrorKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }, 3000);
    }
    setSavingKeys((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  function toggleVisibility(key: string) {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Group settings by category
  const apiKeys = settings.filter((s) => s.category === "api_keys");
  const paths = settings.filter((s) => s.category === "paths");
  const other = settings.filter(
    (s) => s.category !== "api_keys" && s.category !== "paths"
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 size={20} className="animate-spin text-slate-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-center space-y-2">
          <AlertCircle size={20} className="mx-auto text-red-400" />
          <p className="text-sm text-red-300">{error}</p>
          <button
            onClick={loadSettings}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            再読み込み
          </button>
        </div>
      </div>
    );
  }

  function renderSetting(setting: AppSetting) {
    const isEditing = editValues[setting.key] !== undefined;
    const isSaving = savingKeys.has(setting.key);
    const isSaved = savedKeys.has(setting.key);
    const isError = errorKeys.has(setting.key);
    const isVisible = visibleKeys.has(setting.key);
    const hasValue =
      setting.value &&
      setting.value !== "" &&
      !setting.value.startsWith("***") &&
      setting.value !== "***";

    return (
      <div
        key={setting.key}
        className="flex items-start gap-4 px-5 py-4 border-b border-blue-400/[0.06] last:border-b-0"
      >
        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-medium text-slate-200">
              {setting.label ?? setting.key}
            </p>
            {hasValue && !isEditing && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium">
                設定済み
              </span>
            )}
            {!hasValue && !isEditing && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-500 font-medium">
                未設定
              </span>
            )}
            {isSaved && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium flex items-center gap-1">
                <Check size={9} /> 保存しました
              </span>
            )}
            {isError && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 font-medium flex items-center gap-1">
                <AlertCircle size={9} /> 保存に失敗しました
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-500 font-mono">{setting.key}</p>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type={setting.is_secret && !isVisible ? "password" : "text"}
                value={isEditing ? editValues[setting.key] : setting.value || ""}
                onChange={(e) => {
                  setEditValues((prev) => ({
                    ...prev,
                    [setting.key]: e.target.value,
                  }));
                }}
                onFocus={() => {
                  if (!isEditing) {
                    setEditValues((prev) => ({ ...prev, [setting.key]: "" }));
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && isEditing) handleSave(setting.key);
                  if (e.key === "Escape") {
                    setEditValues((prev) => {
                      const next = { ...prev };
                      delete next[setting.key];
                      return next;
                    });
                  }
                }}
                placeholder={setting.is_secret ? "APIキーを入力..." : "値を入力..."}
                className="w-full px-3 py-2 bg-[#132040] border border-blue-400/[0.10] rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:border-blue-500/40 focus:outline-none font-mono pr-10"
              />
              {setting.is_secret && (
                <button
                  onClick={() => toggleVisibility(setting.key)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  title={isVisible ? "非表示" : "表示"}
                >
                  {isVisible ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
              )}
            </div>

            {isEditing && (
              <button
                onClick={() => handleSave(setting.key)}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-40 flex-shrink-0"
              >
                {isSaving ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Check size={12} />
                )}
                保存
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-blue-500/[0.10] border border-blue-400/20">
          <Settings size={18} className="text-blue-400" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-100">APIキー設定</h2>
          <p className="text-xs text-slate-500">Runway・Kling・Pika などのAPIキーを管理</p>
        </div>
      </div>

      {/* Security notice */}
      <div className="flex items-start gap-3 px-4 py-3 bg-amber-500/[0.06] border border-amber-400/10 rounded-xl">
        <Shield size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-amber-300/80 leading-relaxed">
          APIキーはローカルデータベースに保存されます。本番環境では環境変数の使用を推奨します。
        </p>
      </div>

      {/* API Keys section */}
      {apiKeys.length > 0 && (
        <div className="bg-[#0e1d32] rounded-xl border border-blue-400/[0.10] overflow-hidden">
          <div className="px-5 py-3 border-b border-blue-400/[0.10] flex items-center gap-2">
            <Key size={13} className="text-blue-400" />
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              APIキー
            </p>
          </div>
          {apiKeys.map(renderSetting)}
        </div>
      )}

      {/* Paths section */}
      {paths.length > 0 && (
        <div className="bg-[#0e1d32] rounded-xl border border-blue-400/[0.10] overflow-hidden">
          <div className="px-5 py-3 border-b border-blue-400/[0.10] flex items-center gap-2">
            <FolderOpen size={13} className="text-blue-400" />
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              パス設定
            </p>
          </div>
          {paths.map(renderSetting)}
        </div>
      )}

      {/* Other section */}
      {other.length > 0 && (
        <div className="bg-[#0e1d32] rounded-xl border border-blue-400/[0.10] overflow-hidden">
          <div className="px-5 py-3 border-b border-blue-400/[0.10] flex items-center gap-2">
            <Settings size={13} className="text-blue-400" />
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              その他
            </p>
          </div>
          {other.map(renderSetting)}
        </div>
      )}

      {settings.length === 0 && (
        <div className="flex items-center justify-center py-12 bg-[#0e1d32] rounded-xl border border-blue-400/[0.10]">
          <div className="text-center space-y-2">
            <Settings size={32} className="mx-auto text-slate-600" />
            <p className="text-sm text-slate-500">設定が見つかりません</p>
          </div>
        </div>
      )}
    </div>
  );
}
