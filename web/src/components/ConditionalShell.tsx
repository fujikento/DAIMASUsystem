"use client";

/**
 * オペレーター画面 (/operator) などのフルスクリーン用途では sidebar / 余白を
 * 取り除く。それ以外のページは従来通り Sidebar + max-width 1400 の admin shell。
 */

import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";

const NO_SHELL_PATHS = ["/operator"];

export default function ConditionalShell({ children }: { children: ReactNode }) {
  const path = usePathname() || "";
  const noShell = NO_SHELL_PATHS.some((p) => path === p || path.startsWith(`${p}/`));

  if (noShell) {
    // sidebar / max-w を取り除いてフルスクリーン (スマホで意味があるサイズ)
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 md:pl-[240px] pt-14 md:pt-0">
        <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-6 md:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
