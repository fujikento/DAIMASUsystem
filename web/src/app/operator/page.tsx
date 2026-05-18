"use client";

/**
 * オペレーター用 mobile UI — ステージ上でスマホ片手で叩く最小操作画面。
 *
 * Phase 2.2 production hardening:
 *   - 大ボタン (44px+ touch target) で 4 操作: GO (次 cue) / PAUSE / EMERGENCY / BLACKOUT
 *   - 現在の cue 番号 / show.status / degraded フラグ / OSC last_error を 1 画面に
 *   - 5 秒ごとに status を再取得 (SSE でも良いが mobile network 切断耐性で polling 採用)
 *   - 接続切れ表示
 *   - rehearsal mode のときは黄色バナー
 */

import { useCallback, useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Storage key for client-side admin key (Phase 1.2 auth middleware)
const KEY_STORAGE = "DAIMASU_ADMIN_API_KEY";

function getApiKey(): string {
  // codex P1: NEXT_PUBLIC_* は public bundle に embed されるため使わない。
  // localStorage 経由でブラウザ毎に保存する (Settings 画面で入力させる想定)。
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  const k = getApiKey();
  if (k) headers["X-API-Key"] = k;
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

interface ShowStatus {
  show_id: number;
  status: string;
  current_cue_id: number | null;
  current_cue_number: number | null;
  current_cue_type: string | null;
  elapsed_in_cue: number;
  total_cues: number;
  completed_cues: number;
  degraded: boolean;
  last_osc_error: string | null;
}

export default function OperatorPage() {
  const [showId, setShowId] = useState<number>(1);
  const [status, setStatus] = useState<ShowStatus | null>(null);
  const [shows, setShows] = useState<Array<{ id: number; name: string; status: string }>>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rehearsalOn, setRehearsalOn] = useState(false);
  const [connectionOk, setConnectionOk] = useState(true);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [hasKey, setHasKey] = useState(false);

  // Initial: check if key already set
  useEffect(() => {
    setHasKey(!!getApiKey());
  }, []);

  function saveApiKey() {
    if (typeof window === "undefined") return;
    try {
      if (apiKeyInput.trim()) {
        window.localStorage.setItem(KEY_STORAGE, apiKeyInput.trim());
        setHasKey(true);
        setApiKeyInput("");
        // 入力直後に status 再取得して検証
        location.reload();
      }
    } catch {
      setError("localStorage 書込失敗");
    }
  }

  function clearApiKey() {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.removeItem(KEY_STORAGE);
      setHasKey(false);
      location.reload();
    } catch { /* noop */ }
  }

  // Show list を 1 回だけ取得
  useEffect(() => {
    (async () => {
      try {
        const r = await authedFetch("/api/shows");
        if (r.ok) {
          const list = await r.json();
          setShows(list);
          if (list.length > 0) setShowId(list[0].id);
        }
      } catch {
        setConnectionOk(false);
      }
    })();
  }, []);

  // status を 3 秒 polling
  const fetchStatus = useCallback(async () => {
    try {
      const r = await authedFetch(`/api/shows/${showId}/status`);
      if (r.ok) {
        setStatus(await r.json());
        setConnectionOk(true);
      } else if (r.status === 404) {
        setStatus(null);
      } else {
        setConnectionOk(false);
      }
    } catch {
      setConnectionOk(false);
    }
  }, [showId]);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 3000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  // rehearsal flag を polling
  useEffect(() => {
    const fetchRehearsal = async () => {
      try {
        const r = await authedFetch(`/api/system/rehearsal/log?limit=1`);
        if (r.ok) {
          const d = await r.json();
          setRehearsalOn(!!d.dry_run);
        }
      } catch {
        /* noop */
      }
    };
    fetchRehearsal();
    const t = setInterval(fetchRehearsal, 10000);
    return () => clearInterval(t);
  }, []);

  async function action(label: string, path: string, method: "POST" | "GET" = "POST") {
    setBusy(label);
    setError(null);
    try {
      const r = await authedFetch(path, { method });
      if (!r.ok) {
        const text = await r.text();
        setError(`${label} failed: ${r.status} ${text.slice(0, 100)}`);
      }
      await fetchStatus();
    } catch (e) {
      setError(`${label} failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen bg-black text-white p-4 select-none">
      <div className="max-w-md mx-auto space-y-4">
        {/* ヘッダー */}
        <header className="flex items-center justify-between border-b border-white/10 pb-2">
          <h1 className="text-xl font-bold">Operator</h1>
          <div className="flex items-center gap-2 text-xs">
            <span className={`w-2 h-2 rounded-full ${connectionOk ? "bg-emerald-400" : "bg-red-500"}`} />
            <span>{connectionOk ? "online" : "offline"}</span>
          </div>
        </header>

        {/* Rehearsal banner */}
        {rehearsalOn && (
          <div className="bg-amber-500/20 border border-amber-400/40 text-amber-100 px-3 py-2 rounded-lg text-sm">
            🎬 REHEARSAL MODE — OSC dry-run (TouchDesigner には届きません)
          </div>
        )}

        {/* API key 入力 (key 未設定時のみ表示) */}
        {!hasKey && (
          <div className="bg-blue-500/10 border border-blue-400/30 text-blue-100 px-3 py-3 rounded-lg space-y-2">
            <div className="text-xs">
              ADMIN_API_KEY をブラウザに保存します (localStorage)。サーバ側で
              <code className="mx-1 px-1 bg-black/30 rounded">ADMIN_API_KEY</code>
              が設定されている場合のみ必要。
            </div>
            <div className="flex gap-2">
              <input
                type="password"
                placeholder="X-API-Key value"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                className="flex-1 px-2 py-1.5 bg-black/40 border border-white/20 rounded text-sm"
              />
              <button
                onClick={saveApiKey}
                disabled={!apiKeyInput.trim()}
                className="px-3 py-1.5 bg-blue-600 active:bg-blue-700 disabled:opacity-40 rounded text-sm font-bold"
              >
                保存
              </button>
            </div>
          </div>
        )}
        {hasKey && (
          <div className="flex items-center justify-end">
            <button onClick={clearApiKey} className="text-[10px] text-zinc-500 underline">
              API key を消す (logout)
            </button>
          </div>
        )}

        {/* Show selector */}
        {shows.length > 1 && (
          <select
            value={showId}
            onChange={(e) => setShowId(Number(e.target.value))}
            className="w-full p-3 bg-zinc-900 border border-white/20 rounded-lg text-base"
          >
            {shows.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.name} ({s.status})
              </option>
            ))}
          </select>
        )}

        {/* Status panel */}
        <section className="bg-zinc-900 border border-white/10 rounded-xl p-4 space-y-2">
          <div className="text-xs uppercase tracking-wider text-zinc-400">show #{showId}</div>
          {status ? (
            <>
              <div className="text-3xl font-mono">
                cue {status.current_cue_number ?? "—"} / {status.total_cues}
              </div>
              <div className="text-sm text-zinc-300">
                status: <span className="font-mono">{status.status}</span>
                {" · "}
                type: <span className="font-mono">{status.current_cue_type ?? "—"}</span>
              </div>
              <div className="text-sm text-zinc-300">
                elapsed: {status.elapsed_in_cue.toFixed(1)}s · completed: {status.completed_cues}/{status.total_cues}
              </div>
              {status.degraded && (
                <div className="mt-2 bg-red-900/40 border border-red-500/50 text-red-200 px-3 py-2 rounded text-sm">
                  ⚠ DEGRADED: {status.last_osc_error ?? "unknown"}
                </div>
              )}
            </>
          ) : (
            <div className="text-zinc-500">no status (show not started)</div>
          )}
        </section>

        {/* Error */}
        {error && (
          <div className="bg-red-900/40 border border-red-500/50 text-red-200 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}

        {/* Buttons */}
        <div className="grid grid-cols-2 gap-3">
          <button
            disabled={!!busy}
            onClick={() => action("START", `/api/shows/${showId}/start`)}
            className="bg-emerald-600 active:bg-emerald-700 disabled:opacity-40 text-white text-lg font-bold py-6 rounded-2xl"
          >
            ▶ START
          </button>
          <button
            disabled={!!busy}
            onClick={() => action("GO", `/api/shows/${showId}/go`)}
            className="bg-blue-600 active:bg-blue-700 disabled:opacity-40 text-white text-lg font-bold py-6 rounded-2xl"
          >
            → GO
          </button>
          <button
            disabled={!!busy}
            onClick={() => action("PAUSE", `/api/shows/${showId}/pause`)}
            className="bg-amber-600 active:bg-amber-700 disabled:opacity-40 text-white text-lg font-bold py-6 rounded-2xl"
          >
            ‖ PAUSE
          </button>
          <button
            disabled={!!busy}
            onClick={() => action("STOP", `/api/shows/${showId}/stop`)}
            className="bg-zinc-700 active:bg-zinc-800 disabled:opacity-40 text-white text-lg font-bold py-6 rounded-2xl"
          >
            ■ STOP
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-3 border-t border-white/10">
          <button
            disabled={!!busy}
            onClick={() => action("BLACKOUT", `/api/shows/${showId}/blackout`)}
            className="bg-zinc-900 border-2 border-white/30 active:bg-zinc-800 disabled:opacity-40 text-white text-base font-bold py-5 rounded-2xl"
          >
            ◑ BLACKOUT
          </button>
          <button
            disabled={!!busy}
            onClick={() => action("UNBLACK", `/api/shows/${showId}/unblackout`)}
            className="bg-zinc-900 border-2 border-white/30 active:bg-zinc-800 disabled:opacity-40 text-white text-base font-bold py-5 rounded-2xl"
          >
            ◐ UNBLACK
          </button>
        </div>

        {/* Emergency stop — 大きく赤く隔離 */}
        <button
          disabled={!!busy}
          onClick={() => {
            if (confirm("EMERGENCY STOP を実行しますか?\n全 OSC タスクを停止し blackout します。")) {
              action("EMERGENCY", `/api/shows/${showId}/emergency-stop`);
            }
          }}
          className="w-full bg-red-700 active:bg-red-800 disabled:opacity-40 text-white text-xl font-bold py-7 rounded-2xl mt-2"
        >
          🚨 EMERGENCY STOP
        </button>

        {busy && <div className="text-center text-sm text-zinc-400">{busy}…</div>}
      </div>
    </div>
  );
}
