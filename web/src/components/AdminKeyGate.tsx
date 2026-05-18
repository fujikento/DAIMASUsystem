"use client";

/**
 * AdminKeyGate — `ADMIN_API_KEY` 認証が有効なサーバ環境で、ブラウザ側に
 * `localStorage.DAIMASU_ADMIN_API_KEY` を保存させる小モーダル。
 *
 * 起動時に `/api/system/info` を叩き、もし `auth_required: true` が返ったが
 * localStorage に key が無い場合 → モーダルを表示してフォーカス。
 * 入力 → 保存 → /api/system/info を再叩きして 200 を確認 → モーダル閉じる。
 *
 * 公開 endpoint なので /api/system/info はキー無しでも 200 を返す。
 * このゲートは「キー未保存だと管理 UI が空っぽに見える」UX 事故を防ぐ。
 */

import { useEffect, useState } from "react";

const KEY_STORAGE = "DAIMASU_ADMIN_API_KEY";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AdminKeyGate() {
  const [needsKey, setNeedsKey] = useState(false);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // localStorage に key があっても、サーバ側で rotation された可能性があるので
    // 必ず /api/shows を叩いて検証する (codex round 5 P2)。
    if (typeof window === "undefined") return;
    const existing = window.localStorage.getItem(KEY_STORAGE) || "";

    (async () => {
      try {
        const headers: Record<string, string> = {};
        if (existing) headers["X-API-Key"] = existing;
        const r = await fetch(`${API_BASE}/api/shows`, {
          method: "GET",
          headers,
        });
        if (r.status === 401) {
          // stale key の場合は localStorage を消してゲートを開ける
          if (existing) {
            try { window.localStorage.removeItem(KEY_STORAGE); } catch { /* noop */ }
          }
          setNeedsKey(true);
        }
        // 200 → key 不要 or 有効、ゲート不要
      } catch {
        // backend 接続不能 → ゲート出さない (別の問題として表示される)
      }
    })();
  }, []);

  async function save() {
    if (!input.trim()) return;
    setSaving(true);
    setError(null);
    try {
      // 入力 key で /api/shows を叩いて検証
      const r = await fetch(`${API_BASE}/api/shows`, {
        method: "GET",
        headers: { "X-API-Key": input.trim() },
      });
      if (r.ok) {
        window.localStorage.setItem(KEY_STORAGE, input.trim());
        setNeedsKey(false);
        // 各 page の useEffect を発火させるため reload (簡易)
        window.location.reload();
      } else if (r.status === 401) {
        setError("無効な API key です");
      } else {
        setError(`予期しないレスポンス: ${r.status}`);
      }
    } catch (e) {
      setError(`通信エラー: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  }

  if (!needsKey) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-white/20 rounded-2xl p-6 max-w-md w-full space-y-4 text-white">
        <h2 className="text-xl font-bold">管理者 API key</h2>
        <p className="text-sm text-zinc-400">
          このサーバは <code className="px-1 bg-black/40 rounded">ADMIN_API_KEY</code>
          が設定されています。ブラウザに保存して各 API 呼び出しの
          <code className="px-1 bg-black/40 rounded mx-1">X-API-Key</code>
          に自動付与します (localStorage に保存、サーバには送信時のみ)。
        </p>
        <input
          autoFocus
          type="password"
          placeholder="X-API-Key value"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
          }}
          className="w-full px-3 py-2.5 bg-black/40 border border-white/20 rounded-lg text-base"
        />
        {error && (
          <div className="bg-red-900/40 border border-red-500/50 text-red-200 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button
            onClick={save}
            disabled={!input.trim() || saving}
            className="px-4 py-2 bg-blue-600 active:bg-blue-700 disabled:opacity-40 rounded-lg font-bold"
          >
            {saving ? "確認中…" : "保存"}
          </button>
        </div>
        <p className="text-[10px] text-zinc-500">
          サーバ側で env <code>ADMIN_API_KEY=</code> を空にすると認証無効になります。
        </p>
      </div>
    </div>
  );
}
