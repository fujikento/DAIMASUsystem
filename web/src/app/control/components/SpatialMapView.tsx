"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Sun, Video, X } from "lucide-react";

// ─── 型定義 ────────────────────────────────────────────────────────────────

interface ZoneState {
  zone_id: number;
  content_path: string | null;
  brightness: number;
  is_playing: boolean;
  canvas_x: number;
  canvas_y: number;
  canvas_w: number;
  canvas_h: number;
}

interface ProjectorInfo {
  pj_id: number;
  canvas_x: number;
  canvas_w: number;
}

interface CanvasInfo {
  width: number;
  height: number;
  zone_width: number;
  zone_height: number;
  table_width_mm: number;
  table_height_mm: number;
  projectors: ProjectorInfo[];
}

interface PreviewData {
  playback: {
    state: string;
    timeline_id: number | null;
    elapsed: number;
    current_content: string | null;
  };
  canvas: CanvasInfo;
  zones: ZoneState[];
  presets_count: number;
}

interface ZoneControlPanelProps {
  zone: ZoneState;
  onContentChange: (zoneId: number, path: string) => Promise<void>;
  onBrightnessChange: (zoneId: number, value: number) => Promise<void>;
  onClose: () => void;
}

// ─── ゾーン制御パネル ───────────────────────────────────────────────────────

function ZoneControlPanel({ zone, onContentChange, onBrightnessChange, onClose }: ZoneControlPanelProps) {
  const [contentPath, setContentPath] = useState(zone.content_path ?? "");
  const [brightness, setBrightness] = useState(zone.brightness);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState("");

  function showFeedback(msg: string) {
    setFeedback(msg);
    setTimeout(() => setFeedback(""), 2000);
  }

  async function handleContentApply() {
    if (!contentPath.trim()) return;
    setLoading(true);
    try {
      await onContentChange(zone.zone_id, contentPath.trim());
      showFeedback("コンテンツを更新しました");
    } catch {
      showFeedback("更新に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  async function handleBrightnessApply(value: number) {
    setBrightness(value);
    try {
      await onBrightnessChange(zone.zone_id, value);
    } catch {
      showFeedback("輝度更新に失敗しました");
    }
  }

  return (
    <div className="bg-[#0e1d32] border border-blue-400/[0.15] rounded-xl p-4 space-y-4">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${zone.is_playing ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`}
          />
          <span className="text-sm font-semibold text-white">Zone {zone.zone_id} 制御</span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-white transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* 現在の状態 */}
      <div className="bg-[#080f1a] rounded-lg p-3 text-xs space-y-1">
        <div className="flex justify-between text-slate-400">
          <span>状態</span>
          <span className={zone.is_playing ? "text-emerald-400" : "text-slate-500"}>
            {zone.is_playing ? "再生中" : "停止"}
          </span>
        </div>
        <div className="flex justify-between text-slate-400">
          <span>輝度</span>
          <span className="text-blue-300">{Math.round(zone.brightness * 100)}%</span>
        </div>
        {zone.content_path && (
          <div className="text-slate-500 truncate">
            {zone.content_path.split("/").pop()}
          </div>
        )}
      </div>

      {/* コンテンツ差し替え */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
          <Video size={12} />
          コンテンツパス
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={contentPath}
            onChange={(e) => setContentPath(e.target.value)}
            placeholder="/path/to/content.mp4"
            className="flex-1 bg-[#080f1a] border border-blue-400/[0.12] text-white text-xs rounded-lg px-3 py-2 placeholder:text-slate-600 focus:outline-none focus:border-blue-400/40"
          />
          <button
            onClick={handleContentApply}
            disabled={loading || !contentPath.trim()}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs rounded-lg transition-colors flex items-center gap-1.5"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : null}
            適用
          </button>
        </div>
      </div>

      {/* 輝度スライダー */}
      <div className="space-y-2">
        <label className="text-xs font-medium text-slate-400 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Sun size={12} />
            輝度
          </span>
          <span className="text-blue-300 font-mono">{Math.round(brightness * 100)}%</span>
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={brightness}
          onChange={(e) => handleBrightnessApply(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none bg-[#080f1a] cursor-pointer accent-blue-400"
        />
        <div className="flex justify-between text-[10px] text-slate-600">
          <span>消灯</span>
          <span>最大</span>
        </div>
      </div>

      {/* フィードバック */}
      {feedback && (
        <div className="text-xs text-blue-400 text-center animate-pulse">{feedback}</div>
      )}
    </div>
  );
}

// ─── メインコンポーネント ──────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SpatialMapView() {
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedZone, setSelectedZone] = useState<number | null>(null);
  const [error, setError] = useState("");

  // ゾーンラベル定義
  const ZONE_LABELS: Record<number, string> = {
    1: "Zone 1",
    2: "Zone 2",
    3: "Zone 3",
    4: "Zone 4",
  };

  // 席位置 (zone_id → [奥, 手前] の cx/cy 比率)
  const SEAT_POSITIONS: Record<number, [number, number][]> = {
    1: [[0.5, 0.25], [0.5, 0.75]],
    2: [[0.5, 0.25], [0.5, 0.75]],
    3: [[0.5, 0.25], [0.5, 0.75]],
    4: [[0.5, 0.25], [0.5, 0.75]],
  };

  const fetchPreview = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projection/preview`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PreviewData = await res.json();
      setPreview(data);
      setError("");
    } catch {
      setError("APIに接続できません");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreview();
    const interval = setInterval(fetchPreview, 5000);
    return () => clearInterval(interval);
  }, [fetchPreview]);

  const handleContentChange = async (zoneId: number, path: string) => {
    const res = await fetch(`${API_BASE}/api/projection/zone/${zoneId}/content`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_path: path }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await fetchPreview();
  };

  const handleBrightnessChange = async (zoneId: number, value: number) => {
    const res = await fetch(`${API_BASE}/api/projection/zone/${zoneId}/brightness`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brightness: value }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500">
        <Loader2 size={20} className="animate-spin mr-2" />
        <span className="text-sm">読み込み中...</span>
      </div>
    );
  }

  if (error || !preview) {
    return (
      <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-6 text-center">
        <p className="text-sm text-red-400">{error || "データを取得できません"}</p>
        <button
          onClick={fetchPreview}
          className="mt-3 text-xs text-slate-400 hover:text-white transition-colors"
        >
          再試行
        </button>
      </div>
    );
  }

  const { canvas, zones, playback } = preview;

  // SVGキャンバスのビューポート比率
  const svgAspect = canvas.width / canvas.height;
  const svgViewH = 300;
  const svgViewW = svgViewH * svgAspect;

  // ピクセル→SVG座標変換
  const toSvgX = (px: number) => (px / canvas.width) * svgViewW;
  const toSvgY = (py: number) => (py / canvas.height) * svgViewH;
  const zoneW = toSvgX(canvas.zone_width);
  const zoneH = toSvgY(canvas.zone_height);

  return (
    <div className="space-y-4">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">空間マップ</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {canvas.table_width_mm.toLocaleString()}mm × {canvas.table_height_mm}mm
            &nbsp;|&nbsp; {canvas.width} × {canvas.height}px
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div
            className={`w-2 h-2 rounded-full ${
              playback.state === "playing" ? "bg-emerald-400 animate-pulse" : "bg-slate-600"
            }`}
          />
          {playback.state === "playing" ? "再生中" : playback.state === "paused" ? "一時停止" : "待機中"}
        </div>
      </div>

      {/* SVGテーブル俯瞰図 */}
      <div className="bg-[#080f1a] rounded-xl border border-blue-400/[0.10] p-4 overflow-x-auto">
        <svg
          viewBox={`0 0 ${svgViewW} ${svgViewH}`}
          className="w-full"
          style={{ maxHeight: 260 }}
        >
          {/* テーブル外枠 */}
          <rect
            x={0}
            y={0}
            width={svgViewW}
            height={svgViewH}
            fill="#0a1222"
            rx={4}
          />

          {/* プロジェクター範囲 */}
          {canvas.projectors.map((pj) => {
            const pxX = toSvgX(pj.canvas_x);
            const pxW = toSvgX(pj.canvas_w);
            return (
              <g key={pj.pj_id}>
                <rect
                  x={pxX}
                  y={0}
                  width={pxW}
                  height={svgViewH}
                  fill="none"
                  stroke="#1e40af"
                  strokeWidth={0.5}
                  strokeDasharray="4 3"
                  opacity={0.4}
                />
                {/* PJラベル */}
                <text
                  x={pxX + pxW / 2}
                  y={10}
                  textAnchor="middle"
                  fill="#3b82f6"
                  fontSize={7}
                  opacity={0.6}
                >
                  PJ{pj.pj_id}
                </text>
              </g>
            );
          })}

          {/* ゾーン */}
          {zones.map((zone) => {
            const zx = toSvgX(zone.canvas_x);
            const zy = toSvgY(zone.canvas_y);
            const isSelected = selectedZone === zone.zone_id;
            const isPlaying = zone.is_playing;
            const brightness = zone.brightness;

            return (
              <g
                key={zone.zone_id}
                onClick={() => setSelectedZone(isSelected ? null : zone.zone_id)}
                style={{ cursor: "pointer" }}
              >
                {/* ゾーン背景 */}
                <rect
                  x={zx + 1}
                  y={zy + 14}
                  width={zoneW - 2}
                  height={zoneH - 14}
                  fill={isPlaying ? `rgba(30,64,175,${0.15 + brightness * 0.25})` : "#0d1526"}
                  rx={2}
                />

                {/* 選択ハイライト / ホバー枠 */}
                <rect
                  x={zx + 1}
                  y={zy + 14}
                  width={zoneW - 2}
                  height={zoneH - 14}
                  fill="none"
                  stroke={isSelected ? "#60a5fa" : isPlaying ? "#1d4ed8" : "#1e3a5f"}
                  strokeWidth={isSelected ? 1.5 : 0.8}
                  rx={2}
                />

                {/* ゾーン番号ラベル */}
                <text
                  x={zx + zoneW / 2}
                  y={zy + 25}
                  textAnchor="middle"
                  fill={isSelected ? "#93c5fd" : "#64748b"}
                  fontSize={8}
                  fontWeight="600"
                >
                  {ZONE_LABELS[zone.zone_id]}
                </text>

                {/* 席位置（お皿） */}
                {(SEAT_POSITIONS[zone.zone_id] ?? []).map(([cx, cy], seatIdx) => {
                  const seatX = zx + cx * zoneW;
                  const seatY = zy + 14 + cy * (zoneH - 14);
                  const seatR = zoneW * 0.13;
                  return (
                    <g key={seatIdx}>
                      <circle
                        cx={seatX}
                        cy={seatY}
                        r={seatR}
                        fill="none"
                        stroke={isPlaying ? "#3b82f6" : "#1e3a5f"}
                        strokeWidth={0.8}
                        opacity={0.7}
                      />
                      <circle
                        cx={seatX}
                        cy={seatY}
                        r={seatR * 0.35}
                        fill={isPlaying ? "#3b82f6" : "#1e3a5f"}
                        opacity={0.5}
                      />
                      {/* 席番号 */}
                      <text
                        x={seatX}
                        y={seatY + 2.5}
                        textAnchor="middle"
                        fill="#64748b"
                        fontSize={5}
                      >
                        席{(zone.zone_id - 1) * 2 + seatIdx + 1}
                      </text>
                    </g>
                  );
                })}

                {/* コンテンツ名 */}
                {zone.content_path && (
                  <text
                    x={zx + zoneW / 2}
                    y={zy + zoneH - 6}
                    textAnchor="middle"
                    fill="#475569"
                    fontSize={5.5}
                  >
                    {zone.content_path.split("/").pop()?.slice(0, 18) ?? ""}
                  </text>
                )}

                {/* 輝度インジケーター */}
                <rect
                  x={zx + 3}
                  y={zy + zoneH - 10}
                  width={(zoneW - 6) * brightness}
                  height={2}
                  fill="#3b82f6"
                  opacity={0.6}
                  rx={1}
                />
              </g>
            );
          })}

          {/* ゾーン区切り線 */}
          {[1, 2, 3].map((i) => (
            <line
              key={i}
              x1={toSvgX(i * canvas.zone_width)}
              y1={14}
              x2={toSvgX(i * canvas.zone_width)}
              y2={svgViewH}
              stroke="#1e3a5f"
              strokeWidth={0.5}
            />
          ))}

          {/* テーブル寸法ラベル */}
          <text
            x={svgViewW / 2}
            y={svgViewH - 3}
            textAnchor="middle"
            fill="#334155"
            fontSize={5.5}
          >
            {canvas.table_width_mm.toLocaleString()}mm ({canvas.width}px)
          </text>
        </svg>
      </div>

      {/* ゾーンサマリー一覧 */}
      <div className="grid grid-cols-4 gap-2">
        {zones.map((zone) => (
          <button
            key={zone.zone_id}
            onClick={() => setSelectedZone(selectedZone === zone.zone_id ? null : zone.zone_id)}
            className={`p-3 rounded-lg border text-left transition-all active:scale-95 ${
              selectedZone === zone.zone_id
                ? "bg-blue-500/10 border-blue-400/40"
                : zone.is_playing
                ? "bg-[#0e1d32] border-blue-400/[0.15] hover:border-blue-400/30"
                : "bg-[#080f1a] border-blue-400/[0.06] hover:border-blue-400/20"
            }`}
          >
            <div className="flex items-center gap-1.5 mb-2">
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  zone.is_playing ? "bg-emerald-400 animate-pulse" : "bg-slate-700"
                }`}
              />
              <span className="text-[11px] font-semibold text-white">Zone {zone.zone_id}</span>
            </div>
            <div className="text-[10px] text-slate-500 mb-1.5">
              席{(zone.zone_id - 1) * 2 + 1}・{(zone.zone_id - 1) * 2 + 2}
            </div>
            {/* 輝度バー */}
            <div className="w-full h-1 bg-[#0a1222] rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${zone.brightness * 100}%` }}
              />
            </div>
            <div className="text-[9px] text-slate-600 mt-1 text-right">
              {Math.round(zone.brightness * 100)}%
            </div>
          </button>
        ))}
      </div>

      {/* 選択ゾーン制御パネル */}
      {selectedZone !== null && (() => {
        const zone = zones.find((z) => z.zone_id === selectedZone);
        if (!zone) return null;
        return (
          <ZoneControlPanel
            zone={zone}
            onContentChange={handleContentChange}
            onBrightnessChange={handleBrightnessChange}
            onClose={() => setSelectedZone(null)}
          />
        );
      })()}

      {/* テーブル仕様フッター */}
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          { label: "全体解像度", value: `${canvas.width} × ${canvas.height}` },
          { label: "ゾーン解像度", value: `${canvas.zone_width} × ${canvas.zone_height}` },
          { label: "テーブルサイズ", value: `${canvas.table_width_mm.toLocaleString()} × ${canvas.table_height_mm}mm` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-[#080f1a] rounded-lg border border-blue-400/[0.06] p-2.5">
            <div className="text-[10px] text-slate-500">{label}</div>
            <div className="text-[11px] font-mono text-slate-300 mt-0.5">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
