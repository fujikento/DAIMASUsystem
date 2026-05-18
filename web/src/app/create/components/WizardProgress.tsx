"use client";

import { CheckCircle2 } from "lucide-react";

const STEPS = [
  { num: 1, label: "テーマ" },
  { num: 2, label: "台本" },
  { num: 3, label: "画像" },
  { num: 4, label: "動画" },
];

export default function WizardProgress({ current }: { current: 1 | 2 | 3 | 4 }) {
  return (
    <div className="flex items-center justify-center gap-1 sm:gap-3 pb-2">
      {STEPS.map((s, i) => {
        const done = s.num < current;
        const active = s.num === current;
        return (
          <div key={s.num} className="flex items-center gap-1 sm:gap-3">
            <div className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  done
                    ? "bg-emerald-500/20 text-emerald-400 border-2 border-emerald-500/50"
                    : active
                    ? "bg-blue-600 text-white border-2 border-blue-400 shadow-lg shadow-blue-900/50"
                    : "bg-neutral-800 text-neutral-600 border-2 border-neutral-700"
                }`}
              >
                {done ? <CheckCircle2 size={14} /> : s.num}
              </div>
              <span
                className={`text-xs font-semibold hidden sm:inline ${
                  done
                    ? "text-emerald-400"
                    : active
                    ? "text-white"
                    : "text-neutral-600"
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`w-6 sm:w-12 h-0.5 ${
                  done ? "bg-emerald-500/50" : "bg-neutral-800"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
