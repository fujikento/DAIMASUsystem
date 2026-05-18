"use client";

/**
 * テーブル模型プレビュー
 * 物理サイズ (mm) を維持したテーブル俯瞰図に動画を流して投影シミュレーションする。
 *
 * Mode:
 *  - unified:      テーブル全幅に 1 つの動画 (連結モード)
 *  - per_zone:     ゾーンごとに別動画 (席ごと独立)
 *  - synchronized: 全ゾーンに同じ動画を同期再生
 *
 * sources:
 *  - unified: { unified: string }
 *  - per_zone: { byZone: { [zone_index]: string } }
 *  - synchronized: { sync: string }
 */

import { useMemo } from "react";
import type { ProjectionTable, SeatSpec } from "@/lib/api";

export type MockupMode = "unified" | "per_zone" | "synchronized";

interface Sources {
  unified?: string | null;
  sync?: string | null;
  byZone?: Record<number, string | null>;
}

interface Props {
  table: ProjectionTable;
  mode?: MockupMode;
  sources?: Sources;
  /** プレビューエリアの最大幅 (px)。default: container 100% */
  maxWidth?: number;
  /** プレビューエリアの最大高さ (px)。default: 320 */
  maxHeight?: number;
  /** PJ 数 + ブレンド領域を可視化するか */
  showProjectorOverlay?: boolean;
  /** 席名・定員を表示するか */
  showSeatLabels?: boolean;
  /** 動画の muted を制御 (default true) */
  muted?: boolean;
}

export default function TableMockup({
  table,
  mode = "unified",
  sources,
  maxWidth,
  maxHeight = 320,
  showProjectorOverlay = false,
  showSeatLabels = true,
  muted = true,
}: Props) {
  // ─ 物理比率から表示サイズ算出 ─
  const aspect = table.table_width_mm / Math.max(table.table_height_mm, 1);
  const dims = useMemo(() => {
    // height を上限とした幅、width 上限とした高さの小さい方
    const byH = { w: maxHeight * aspect, h: maxHeight };
    if (maxWidth) {
      const byW = { w: maxWidth, h: maxWidth / aspect };
      return byH.w <= maxWidth ? byH : byW;
    }
    return byH;
  }, [aspect, maxHeight, maxWidth]);

  const seats: SeatSpec[] = table.seats?.length
    ? table.seats
    : Array.from({ length: table.zone_count }, (_, i) => ({
        zone_index: i,
        name: `${String.fromCharCode(65 + i)}席`,
        party_size: 2,
      }));

  const zoneWidthPx = dims.w / Math.max(table.zone_count, 1);

  // PJ ブレンド領域のピクセル位置 (テーブル全幅基準)
  const pjOverlays = useMemo(() => {
    if (!showProjectorOverlay || table.pj_count <= 1) return [];
    const pjW = (table.pj_width / table.full_width) * dims.w;
    const blendW = (table.blend_overlap / table.full_width) * dims.w;
    const overlays: Array<{ x: number; w: number }> = [];
    for (let i = 0; i < table.pj_count - 1; i++) {
      const x = pjW * (i + 1) - blendW * (i + 0.5);
      overlays.push({ x, w: blendW });
    }
    return overlays;
  }, [showProjectorOverlay, table, dims.w]);

  return (
    <div
      className="relative bg-[#06080c] rounded-md border border-white/[0.04] overflow-hidden"
      style={{ padding: 16 }}
    >
      {/* room floor texture (subtle radial) */}
      <div
        className="absolute inset-0 opacity-30 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(80,80,90,0.15) 0%, transparent 70%)",
        }}
      />

      {/* table footprint */}
      <div className="relative mx-auto" style={{ width: dims.w, height: dims.h }}>
        {/* table base (wood surface tone) */}
        <div
          className="absolute inset-0 rounded-sm shadow-[0_8px_24px_rgba(0,0,0,0.5)] border border-black/40"
          style={{
            background:
              "linear-gradient(180deg, #2a2620 0%, #1c1916 50%, #14110d 100%)",
          }}
        />

        {/* projected video layer (sits ON the table) */}
        <div className="absolute inset-0 overflow-hidden rounded-sm">
          {mode === "unified" && sources?.unified ? (
            <video
              src={sources.unified}
              muted={muted}
              loop
              autoPlay
              playsInline
              className="w-full h-full object-cover opacity-90 mix-blend-screen"
            />
          ) : mode === "synchronized" && sources?.sync ? (
            // 同期モード: 全ゾーンに同じ動画 (zone_count 個に複製表示)
            <div
              className="absolute inset-0 grid"
              style={{
                gridTemplateColumns: `repeat(${table.zone_count}, 1fr)`,
              }}
            >
              {Array.from({ length: table.zone_count }, (_, i) => (
                <video
                  key={i}
                  src={sources.sync ?? undefined}
                  muted={muted}
                  loop
                  autoPlay
                  playsInline
                  className="w-full h-full object-cover opacity-90 mix-blend-screen"
                />
              ))}
            </div>
          ) : mode === "per_zone" && sources?.byZone ? (
            <div
              className="absolute inset-0 grid"
              style={{
                gridTemplateColumns: `repeat(${table.zone_count}, 1fr)`,
              }}
            >
              {seats.map((seat) => {
                const src = sources.byZone?.[seat.zone_index];
                return src ? (
                  <video
                    key={seat.zone_index}
                    src={src}
                    muted={muted}
                    loop
                    autoPlay
                    playsInline
                    className="w-full h-full object-cover opacity-90 mix-blend-screen"
                  />
                ) : (
                  <div
                    key={seat.zone_index}
                    className="w-full h-full bg-neutral-900/40 flex items-center justify-center"
                  >
                    <span className="text-[10px] text-neutral-600">未生成</span>
                  </div>
                );
              })}
            </div>
          ) : (
            // No video source: empty table illustration
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[10px] text-neutral-700 uppercase tracking-widest">
                no video
              </span>
            </div>
          )}
        </div>

        {/* zone division lines */}
        {table.zone_count > 1 &&
          Array.from({ length: table.zone_count - 1 }, (_, i) => (
            <div
              key={i}
              className="absolute top-0 bottom-0 border-l border-dashed border-white/15"
              style={{ left: zoneWidthPx * (i + 1) }}
            />
          ))}

        {/* PJ blend overlays (optional) */}
        {pjOverlays.map((o, i) => (
          <div
            key={i}
            className="absolute top-0 bottom-0 bg-yellow-400/10 border-l border-r border-yellow-400/30 pointer-events-none"
            style={{ left: o.x, width: Math.max(o.w, 2) }}
          />
        ))}

        {/* seat labels (top edge) */}
        {showSeatLabels && (
          <div
            className="absolute top-0 left-0 right-0 grid pointer-events-none"
            style={{
              gridTemplateColumns: `repeat(${table.zone_count}, 1fr)`,
            }}
          >
            {seats.map((seat) => (
              <div
                key={seat.zone_index}
                className="text-center -mt-5"
              >
                <span className="inline-block text-[10px] text-neutral-400 bg-[#06080c] px-1.5 py-0.5 rounded-sm border border-white/[0.06]">
                  {seat.name}
                  <span className="ml-1 text-neutral-600 tabular-nums">
                    ({seat.party_size}名)
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}

        {/* dimensional markers (bottom edge) */}
        <div className="absolute -bottom-5 left-0 right-0 flex items-center justify-between text-[9px] text-neutral-600 tabular-nums px-1">
          <span>0</span>
          <span>{table.table_width_mm}mm</span>
        </div>
      </div>

      {/* Metadata footer */}
      <div className="relative mt-6 pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] text-neutral-500">
        <div className="flex items-center gap-3">
          <span>
            <span className="text-neutral-600">物理:</span>{" "}
            <span className="text-neutral-300 tabular-nums">
              {table.table_width_mm}×{table.table_height_mm}mm
            </span>
          </span>
          <span>
            <span className="text-neutral-600">投影:</span>{" "}
            <span className="text-neutral-300 tabular-nums">
              {table.full_width}×{table.full_height}px
            </span>
          </span>
          <span>
            <span className="text-neutral-600">PJ:</span>{" "}
            <span className="text-neutral-300 tabular-nums">{table.pj_count}台</span>
          </span>
        </div>
        <span className="uppercase tracking-widest text-neutral-600">
          mode: {mode}
        </span>
      </div>
    </div>
  );
}
