"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Projector,
  Wand2,
  ChevronDown,
  Film,
  Palette,
  BarChart2,
  KeyRound,
  Smartphone,
  Menu,
  X,
} from "lucide-react";

// ── Primary nav (always visible — 3 items) ──────────────────────
const PRIMARY = [
  {
    href: "/",
    label: "ホーム",
    icon: LayoutDashboard,
    sub: "全体の状況",
    matchExact: true,
  },
  {
    href: "/create",
    label: "つくる",
    icon: Wand2,
    sub: "台本 → 画像 → 動画",
    matchExact: false,
  },
  {
    href: "/control",
    label: "ながす",
    icon: Projector,
    sub: "投影制御",
    matchExact: false,
  },
];

// ── Secondary nav (collapsible) ────────────────────────────────
const SECONDARY = [
  {
    href: "/content",
    label: "コンテンツライブラリ",
    icon: Film,
  },
  {
    href: "/operator",
    label: "オペレーター画面",
    icon: Smartphone,
  },
  {
    href: "/analytics",
    label: "分析・コスト",
    icon: BarChart2,
  },
  {
    href: "/settings",
    label: "曜日テーマ",
    icon: Palette,
  },
  {
    href: "/app-settings",
    label: "APIキー設定",
    icon: KeyRound,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const isActive = (href: string, matchExact: boolean) => {
    if (matchExact) return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <>
      {/* ─ Mobile top bar (hamburger) ─ */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-[#0a1222]/95 backdrop-blur border-b border-blue-400/10 flex items-center justify-between px-4 z-40">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
            <Projector size={14} className="text-white" />
          </div>
          <span className="text-sm font-bold tracking-wide text-white">
            IMMERSIVE
          </span>
        </Link>
        <button
          onClick={() => setMobileOpen(true)}
          className="w-9 h-9 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-white transition-colors"
          aria-label="メニュー"
        >
          <Menu size={18} />
        </button>
      </div>

      {/* ─ Mobile overlay ─ */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ─ Sidebar (desktop fixed; mobile slide-in) ─ */}
      <aside
        className={`fixed left-0 top-0 h-screen w-[240px] bg-[#0a1222] border-r border-blue-400/[0.08] flex flex-col z-50 transition-transform md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="md:hidden absolute top-3 right-3 w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-white"
          aria-label="閉じる"
        >
          <X size={16} />
        </button>
      {/* ─ Logo ─ */}
      <div className="px-5 py-5 border-b border-blue-400/[0.06]">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
            <Projector size={17} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide text-white">
              IMMERSIVE
            </h1>
            <p className="text-[10px] text-slate-500 tracking-wider">
              DINING SYSTEM
            </p>
          </div>
        </Link>
      </div>

      {/* ─ Primary navigation (3 big items) ─ */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {PRIMARY.map((item) => {
          const active = isActive(item.href, item.matchExact);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-3 px-3 py-3 rounded-xl transition-all border ${
                active
                  ? "bg-blue-600/15 border-blue-400/30 text-white"
                  : "border-transparent text-slate-300 hover:text-white hover:bg-blue-400/[0.05]"
              }`}
            >
              <div
                className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-all ${
                  active
                    ? "bg-blue-500/25"
                    : "bg-blue-400/[0.05] group-hover:bg-blue-400/[0.10]"
                }`}
              >
                <Icon
                  size={17}
                  strokeWidth={active ? 2.3 : 1.9}
                  className={active ? "text-blue-300" : "text-slate-400"}
                />
              </div>
              <div className="min-w-0 flex-1">
                <div
                  className={`text-sm font-semibold truncate ${
                    active ? "text-white" : "text-slate-200"
                  }`}
                >
                  {item.label}
                </div>
                <div className="text-[10px] text-slate-500 truncate mt-0.5">
                  {item.sub}
                </div>
              </div>
              {active && (
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
              )}
            </Link>
          );
        })}

        {/* ─ Secondary toggle ─ */}
        <div className="pt-4">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-medium text-slate-600 hover:text-slate-400 uppercase tracking-widest transition-colors"
          >
            <span>その他</span>
            <ChevronDown
              size={12}
              className={`transition-transform ${
                showAdvanced ? "rotate-180" : ""
              }`}
            />
          </button>

          {showAdvanced && (
            <div className="space-y-0.5 mt-1">
              {SECONDARY.map((item) => {
                const active = isActive(item.href, false);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      active
                        ? "bg-blue-500/10 text-blue-300"
                        : "text-slate-500 hover:text-white hover:bg-blue-400/[0.04]"
                    }`}
                  >
                    <Icon
                      size={14}
                      strokeWidth={active ? 2.2 : 1.8}
                      className="shrink-0"
                    />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </nav>

      {/* ─ Footer ─ */}
      <div className="px-5 py-3 border-t border-blue-400/[0.06]">
        <p className="text-[10px] text-slate-600">v0.2.0 · 大桝 BAR</p>
      </div>
      </aside>
    </>
  );
}
