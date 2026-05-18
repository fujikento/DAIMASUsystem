"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Loader2, AlertCircle } from "lucide-react";
import {
  fetchStoryboard,
  type StoryboardData,
} from "@/lib/api";
import WizardProgress from "../components/WizardProgress";
import Step2Script from "../components/Step2Script";
import Step3Images from "../components/Step3Images";
import Step4Video from "../components/Step4Video";

function deriveStep(sb: StoryboardData): 2 | 3 | 4 {
  if (sb.status === "video_ready") return 4;
  if (sb.status === "images_ready") return 4;
  const anyImage = sb.scenes.some(
    (s) => s.image_status === "complete" || s.image_status === "approved"
  );
  if (anyImage) return 3;
  return 2;
}

export default function WizardPage(props: { params: Promise<{ id: string }> }) {
  const { id: idStr } = use(props.params);
  const router = useRouter();
  const search = useSearchParams();
  const stepOverride = search.get("step");

  const id = Number(idStr);
  const [storyboard, setStoryboard] = useState<StoryboardData | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (Number.isNaN(id)) {
      setLoadErr("台本IDが無効です");
      return;
    }
    try {
      const data = await fetchStoryboard(id);
      setStoryboard(data);
      setLoadErr(null);
    } catch (e) {
      setLoadErr(e instanceof Error ? e.message : "台本が見つかりません");
    }
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  // ─ Loading state ─
  if (!storyboard && !loadErr) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 size={24} className="animate-spin text-neutral-500" />
      </div>
    );
  }

  // ─ Error state ─
  if (loadErr) {
    return (
      <div className="max-w-md mx-auto text-center py-20 space-y-4">
        <AlertCircle size={36} className="text-red-400/60 mx-auto" />
        <h2 className="text-lg font-semibold text-white">{loadErr}</h2>
        <Link
          href="/create"
          className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300"
        >
          <ChevronLeft size={14} />
          一覧に戻る
        </Link>
      </div>
    );
  }

  if (!storyboard) return null;

  // ─ Step decision: query param override > derived from status ─
  const requestedStep = stepOverride ? Number(stepOverride) : null;
  const derived = deriveStep(storyboard);
  const step =
    requestedStep && [2, 3, 4].includes(requestedStep)
      ? (requestedStep as 2 | 3 | 4)
      : derived;

  return (
    <div className="max-w-5xl mx-auto space-y-8 py-2">
      {/* ─ Top bar ─ */}
      <div className="flex items-center justify-between">
        <Link
          href="/create"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-white transition-colors"
        >
          <ChevronLeft size={14} />
          一覧
        </Link>
        <div className="text-right">
          <h1 className="text-lg font-semibold text-white">
            {storyboard.title}
          </h1>
          {storyboard.theme && (
            <p className="text-xs text-neutral-500 capitalize">
              {storyboard.theme} · シーン {storyboard.scenes.length}件
            </p>
          )}
        </div>
      </div>

      <WizardProgress current={step} />

      {/* ─ Step content ─ */}
      {step === 2 && (
        <Step2Script
          storyboard={storyboard}
          onReload={reload}
          onNext={() => router.push(`/create/${storyboard.id}?step=3`)}
        />
      )}
      {step === 3 && (
        <Step3Images
          storyboard={storyboard}
          onReload={reload}
          onBack={() => router.push(`/create/${storyboard.id}?step=2`)}
          onNext={() => router.push(`/create/${storyboard.id}?step=4`)}
        />
      )}
      {step === 4 && (
        <Step4Video
          storyboard={storyboard}
          onReload={reload}
          onBack={() => router.push(`/create/${storyboard.id}?step=3`)}
        />
      )}
    </div>
  );
}
