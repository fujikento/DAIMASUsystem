"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Film,
  Projector,
  Wand2,
  Palette,
  BarChart2,
  KeyRound,
} from "lucide-react";

// ── メインナビゲーション ─────────────────────────────────────

const MAIN_NAV = [
  {
    href: "/generation",
    label: "台本・映像生成",
    icon: Wand2,
    description: "AI映像コンテンツ作成",
    primary: true,
  },
  {
    href: "/",
    label: "ダッシュボード",
    icon: LayoutDashboard,
    description: "本日の運営状況",
    primary: false,
  },
  {
    href: "/control",
    label: "投影制御",
    icon: Projector,
    description: "プロジェクター操作",
    primary: false,
  },
  {
    href: "/content",
    label: "コンテンツ管理",
    icon: Film,
    description: "映像ライブラリ",
    primary: false,
  },
  {
    href: "/analytics",
    label: "分析",
    icon: BarChart2,
    description: "生成統計・コスト",
    primary: false,
  },
];

// ── 設定グループ ─────────────────────────────────────────────

const SETTINGS_NAV = [
  {
    href: "/settings",
    label: "曜日テーマ設定",
    icon: Palette,
    description: "テーマカラー・アイコン",
  },
  {
    href: "/app-settings",
    label: "APIキー設定",
    icon: KeyRound,
    description: "Runway・Kling など",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-[260px] bg-[#0a1222] border-r border-blue-400/[0.08] flex flex-col z-50">
      {/* ロゴ */}
      <div className="px-6 py-5 border-b border-blue-400/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Projector size={16} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide text-white">
              IMMERSIVE DINING
            </h1>
            <p className="text-[10px] text-slate-500 tracking-wider">
              映像投影システム
            </p>
          </div>
        </div>
      </div>

      {/* メインナビゲーション */}
      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {/* 生成ワークフロー（最重要） */}
        {MAIN_NAV.filter((item) => item.primary).map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-3 rounded-xl text-[13px] font-semibold transition-all group mb-2 ${
                isActive
                  ? "bg-blue-600/[0.15] text-blue-300 border border-blue-400/[0.20]"
                  : "text-slate-300 hover:text-white hover:bg-blue-400/[0.06] border border-transparent"
              }`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-all ${
                  isActive
                    ? "bg-blue-500/20"
                    : "bg-blue-400/[0.06] group-hover:bg-blue-400/[0.10]"
                }`}
              >
                <Icon
                  size={15}
                  strokeWidth={isActive ? 2.3 : 1.9}
                  className={isActive ? "text-blue-400" : "text-slate-400"}
                />
              </div>
              <div className="min-w-0">
                <div className="truncate">{item.label}</div>
                {item.description && (
                  <div className="text-[10px] text-slate-500 truncate font-normal group-hover:text-slate-400 transition-colors mt-0.5">
                    {item.description}
                  </div>
                )}
              </div>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
              )}
            </Link>
          );
        })}

        {/* セパレーター */}
        <div className="my-2 border-t border-blue-400/[0.05]" />

        {/* その他のナビゲーション */}
        <p className="text-[10px] font-medium text-slate-600 uppercase tracking-widest px-3 mb-2 mt-3">
          運営管理
        </p>
        <div className="space-y-0.5">
          {MAIN_NAV.filter((item) => !item.primary).map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all group ${
                  isActive
                    ? "bg-blue-500/10 text-blue-400"
                    : "text-slate-400 hover:text-white hover:bg-blue-400/[0.04]"
                }`}
              >
                <Icon
                  size={17}
                  strokeWidth={isActive ? 2.2 : 1.8}
                  className="flex-shrink-0"
                />
                <div className="min-w-0">
                  <div className="truncate">{item.label}</div>
                  {item.description && (
                    <div className="text-[10px] text-slate-600 truncate group-hover:text-slate-500 transition-colors">
                      {item.description}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* 設定グループ (フッター上) */}
      <div className="px-3 pb-2 border-t border-blue-400/[0.06] pt-3">
        <p className="text-[10px] font-medium text-slate-600 uppercase tracking-widest px-3 mb-2">
          設定
        </p>
        <div className="space-y-0.5">
          {SETTINGS_NAV.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all group ${
                  isActive
                    ? "bg-blue-500/10 text-blue-400"
                    : "text-slate-400 hover:text-white hover:bg-blue-400/[0.04]"
                }`}
              >
                <Icon
                  size={17}
                  strokeWidth={isActive ? 2.2 : 1.8}
                  className="flex-shrink-0"
                />
                <div className="min-w-0">
                  <div className="truncate">{item.label}</div>
                  {item.description && (
                    <div className="text-[10px] text-slate-600 truncate group-hover:text-slate-500 transition-colors">
                      {item.description}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* フッター */}
      <div className="px-6 py-3 border-t border-blue-400/[0.06]">
        <p className="text-[10px] text-slate-600">v0.1.0</p>
      </div>
    </aside>
  );
}
