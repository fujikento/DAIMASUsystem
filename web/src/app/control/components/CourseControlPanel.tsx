"use client";

import { useEffect, useState, useCallback } from "react";
import { ChefHat, Utensils, Check, AlertTriangle, Plus, X } from "lucide-react";
import {
  fetchTableSessions,
  createTableSession,
  serveCourse,
  clearCourse,
  completeTableSession,
  type TableSession,
  type TableSessionCreate,
} from "@/lib/api";

const COURSES: { key: string; label: string; labelEn: string }[] = [
  { key: "welcome", label: "ウェルカム", labelEn: "Welcome" },
  { key: "appetizer", label: "前菜", labelEn: "Appetizer" },
  { key: "soup", label: "スープ", labelEn: "Soup" },
  { key: "main", label: "メイン", labelEn: "Main" },
  { key: "dessert", label: "デザート", labelEn: "Dessert" },
];

const COURSE_ORDER = COURSES.map((c) => c.key);

function getCourseIndex(courseKey: string | null): number {
  if (!courseKey) return -1;
  return COURSE_ORDER.indexOf(courseKey);
}

function CourseStep({
  course,
  currentCourse,
  onServe,
  onClear,
  loading,
}: {
  course: { key: string; label: string; labelEn: string };
  currentCourse: string | null;
  onServe: (key: string) => void;
  onClear: (key: string) => void;
  loading: boolean;
}) {
  const currentIdx = getCourseIndex(currentCourse);
  const thisIdx = COURSE_ORDER.indexOf(course.key);
  const isActive = currentCourse === course.key;
  const isDone = currentIdx > thisIdx;
  const isPending = currentIdx < thisIdx;

  return (
    <div
      className={`rounded-xl p-4 border transition-all ${
        isActive
          ? "border-amber-400 bg-amber-400/10"
          : isDone
          ? "border-emerald-600/40 bg-emerald-900/10"
          : "border-[#1e3050] bg-[#0e1d32]/60"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isDone ? (
            <Check className="w-5 h-5 text-emerald-400" />
          ) : isActive ? (
            <Utensils className="w-5 h-5 text-amber-400" />
          ) : (
            <span className="w-5 h-5 rounded-full border border-[#2a4060] flex items-center justify-center text-xs text-slate-500">
              {thisIdx + 1}
            </span>
          )}
          <div>
            <span
              className={`font-semibold text-sm ${
                isActive ? "text-amber-200" : isDone ? "text-emerald-400" : "text-slate-400"
              }`}
            >
              {course.label}
            </span>
            <span className="ml-2 text-xs text-slate-600">{course.labelEn}</span>
          </div>
        </div>
        {isDone && (
          <span className="text-xs text-emerald-500 bg-emerald-900/30 px-2 py-0.5 rounded-full">
            完了
          </span>
        )}
        {isActive && (
          <span className="text-xs text-amber-400 bg-amber-900/30 px-2 py-0.5 rounded-full animate-pulse">
            提供中
          </span>
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onServe(course.key)}
          disabled={loading || isDone || (isPending && thisIdx > currentIdx + 1)}
          className={`flex-1 py-3 rounded-lg text-sm font-semibold transition-all active:scale-95 ${
            isActive || (isPending && thisIdx === currentIdx + 1) || currentIdx === -1 && thisIdx === 0
              ? "bg-amber-500 hover:bg-amber-400 text-black"
              : isDone
              ? "bg-[#0e1d32] text-slate-600 cursor-not-allowed"
              : "bg-[#0e1d32] text-slate-500 cursor-not-allowed"
          }`}
        >
          提供
        </button>
        <button
          onClick={() => onClear(course.key)}
          disabled={loading || !isActive}
          className={`flex-1 py-3 rounded-lg text-sm font-semibold transition-all active:scale-95 ${
            isActive
              ? "bg-[#1e3050] hover:bg-[#243660] text-slate-200"
              : "bg-[#0e1d32] text-slate-600 cursor-not-allowed"
          }`}
          title="料理を下げ、次のコースへ進みます"
        >
          提供済・次へ
        </button>
      </div>
    </div>
  );
}

function NewSessionModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (s: TableSession) => void;
}) {
  const [guestCount, setGuestCount] = useState(2);
  const [tableNumber, setTableNumber] = useState(1);
  const [creating, setCreating] = useState(false);

  async function handleCreate() {
    setCreating(true);
    try {
      const data: TableSessionCreate = {
        guest_count: guestCount,
        table_number: tableNumber,
      };
      const session = await createTableSession(data);
      onCreated(session);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0e1d32] border border-[#1e3050] rounded-2xl p-6 w-80">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-white font-semibold text-lg">新規セッション</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-slate-400 text-xs mb-1 block">テーブル番号</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((n) => (
                <button
                  key={n}
                  onClick={() => setTableNumber(n)}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
                    tableNumber === n
                      ? "bg-blue-600 text-white"
                      : "bg-[#1e3050] text-slate-300 hover:bg-[#243660]"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-slate-400 text-xs mb-1 block">ゲスト人数</label>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setGuestCount(Math.max(1, guestCount - 1))}
                className="w-10 h-10 rounded-full bg-[#1e3050] text-white text-lg hover:bg-[#243660]"
              >
                -
              </button>
              <span className="text-white text-2xl font-bold w-10 text-center">{guestCount}</span>
              <button
                onClick={() => setGuestCount(Math.min(20, guestCount + 1))}
                className="w-10 h-10 rounded-full bg-[#1e3050] text-white text-lg hover:bg-[#243660]"
              >
                +
              </button>
            </div>
          </div>
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="w-full mt-6 py-3 bg-amber-500 hover:bg-amber-400 text-black font-bold rounded-xl transition-all active:scale-95 disabled:opacity-50"
        >
          {creating ? "作成中..." : "セッション開始"}
        </button>
      </div>
    </div>
  );
}

export default function CourseControlPanel() {
  const [sessions, setSessions] = useState<TableSession[]>([]);
  const [activeSession, setActiveSession] = useState<TableSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [showModal, setShowModal] = useState(false);

  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchTableSessions();
      setSessions(data);
      if (activeSession) {
        const updated = data.find((s) => s.id === activeSession.id);
        if (updated) setActiveSession(updated);
      } else if (data.length > 0) {
        setActiveSession(data[0]);
      }
    } catch {
      // API が起動していない場合はエラーをサイレントに処理
    }
  }, [activeSession]);

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 10000);
    return () => clearInterval(interval);
  }, [loadSessions]);

  function showFeedback(msg: string, type: "ok" | "err" = "ok") {
    setFeedback({ msg, type });
    setTimeout(() => setFeedback(null), 3000);
  }

  async function handleServe(courseKey: string) {
    if (!activeSession) return;
    setLoading(true);
    try {
      const updated = await serveCourse(activeSession.id, courseKey);
      setActiveSession(updated);
      showFeedback(`${COURSES.find((c) => c.key === courseKey)?.label} を提供しました`);
    } catch {
      showFeedback("提供トリガーに失敗しました", "err");
    } finally {
      setLoading(false);
    }
  }

  async function handleClear(courseKey: string) {
    if (!activeSession) return;
    setLoading(true);
    try {
      const updated = await clearCourse(activeSession.id, courseKey);
      setActiveSession(updated);
      showFeedback(`${COURSES.find((c) => c.key === courseKey)?.label} を下げました`);
    } catch {
      showFeedback("下げトリガーに失敗しました", "err");
    } finally {
      setLoading(false);
    }
  }

  async function handleComplete() {
    if (!activeSession) return;
    setLoading(true);
    try {
      await completeTableSession(activeSession.id);
      showFeedback("セッションを完了しました");
      setActiveSession(null);
      loadSessions();
    } catch {
      showFeedback("セッション完了に失敗しました", "err");
    } finally {
      setLoading(false);
    }
  }

  const currentIdx = getCourseIndex(activeSession?.current_course ?? null);
  const progressPct =
    activeSession && currentIdx >= 0
      ? Math.round(((currentIdx + 1) / COURSES.length) * 100)
      : 0;

  const specialRequests = activeSession?.special_requests
    ? (() => {
        try {
          return JSON.parse(activeSession.special_requests);
        } catch {
          return null;
        }
      })()
    : null;
  const hasAllergen = specialRequests?.allergies?.length > 0 || specialRequests?.dietary;

  return (
    <div className="bg-[#080f1a] min-h-screen text-white p-4 max-w-lg mx-auto">
      {/* ヘッダー */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <ChefHat className="w-6 h-6 text-amber-400" />
          <h1 className="text-lg font-bold text-white">料理コントロール</h1>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1 bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-2 rounded-lg transition-all active:scale-95"
        >
          <Plus className="w-4 h-4" />
          新規
        </button>
      </div>

      {/* フィードバックバー */}
      {feedback && (
        <div
          className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${
            feedback.type === "ok"
              ? "bg-emerald-900/50 text-emerald-300 border border-emerald-700/40"
              : "bg-red-900/50 text-red-300 border border-red-700/40"
          }`}
        >
          {feedback.msg}
        </div>
      )}

      {/* セッション選択タブ */}
      {sessions.length > 1 && (
        <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSession(s)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                activeSession?.id === s.id
                  ? "bg-amber-500 text-black"
                  : "bg-[#1e3050] text-slate-300 hover:bg-[#243660]"
              }`}
            >
              Table {s.table_number}
            </button>
          ))}
        </div>
      )}

      {/* アクティブセッション情報 */}
      {activeSession ? (
        <>
          <div className="bg-[#0e1d32] rounded-2xl p-4 mb-4 border border-[#1e3050]">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-slate-400 text-xs mb-0.5">アクティブセッション</div>
                <div className="text-white font-bold text-xl">
                  Table {activeSession.table_number}
                </div>
                <div className="text-slate-400 text-sm">
                  {activeSession.guest_count}名 &middot; ID #{activeSession.id}
                </div>
              </div>
              {hasAllergen && (
                <div className="flex items-center gap-1 bg-red-900/40 border border-red-600/40 rounded-lg px-2 py-1">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <span className="text-red-300 text-xs font-medium">アレルギー</span>
                </div>
              )}
            </div>

            {/* プログレスバー */}
            <div className="mt-4">
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>コース進行</span>
                <span>{progressPct}%</span>
              </div>
              <div className="h-1.5 bg-[#1e3050] rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-400 rounded-full transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          </div>

          {/* コースステッパー */}
          <div className="space-y-2 mb-4">
            {COURSES.map((course) => (
              <CourseStep
                key={course.key}
                course={course}
                currentCourse={activeSession.current_course}
                onServe={handleServe}
                onClear={handleClear}
                loading={loading}
              />
            ))}
          </div>

          {/* セッション完了ボタン */}
          <button
            onClick={() => {
              if (confirm("セッションを完了しますか？\nゲストが退席したことを確認してください。")) {
                handleComplete();
              }
            }}
            disabled={loading}
            className="w-full py-4 bg-red-500/[0.08] hover:bg-red-500/[0.15] border border-red-500/[0.20] hover:border-red-500/[0.35] text-red-400 font-semibold rounded-xl transition-all active:scale-95 disabled:opacity-50 text-sm"
          >
            退席・セッション終了
          </button>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <ChefHat className="w-12 h-12 text-slate-600 mb-3" />
          <div className="text-slate-400 text-sm mb-4">アクティブなセッションがありません</div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-amber-500 hover:bg-amber-400 text-black font-bold px-6 py-3 rounded-xl transition-all active:scale-95"
          >
            <Plus className="w-5 h-5" />
            セッションを開始
          </button>
        </div>
      )}

      {/* 新規セッションモーダル */}
      {showModal && (
        <NewSessionModal
          onClose={() => setShowModal(false)}
          onCreated={(s) => {
            setActiveSession(s);
            setShowModal(false);
            loadSessions();
          }}
        />
      )}
    </div>
  );
}
