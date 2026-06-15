"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { useParams } from "next/navigation";
import { ChevronLeft, Copy, Pencil, RefreshCw, Trash2, UserPlus } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import { fetchAuthMe, goToGoogleLogin } from "@/lib/auth-session";
import {
  addPlanItem,
  createInvite,
  deletePlanItem,
  getTrip,
  listPlanItems,
  updatePlanItem,
  TripsApiError,
  type Trip,
} from "@/lib/trips-api";
import {
  PLAN_CATEGORIES,
  canEditPlanItem,
  categoryEmoji,
  groupPlanItemsByDay,
  validatePlanItemDraft,
  type PlanItem,
} from "@/lib/trip-plan";

type Stage = "loading" | "anon" | "forbidden" | "missing" | "ready" | "error";

interface DraftState {
  id: number | null; // null = 추가, 숫자 = 수정
  day: string;
  time: string;
  place: string;
  category: string;
  memo: string;
}

const EMPTY_DRAFT: DraftState = { id: null, day: "1", time: "", place: "", category: "관광", memo: "" };

export default function TripDetailPage() {
  const router = useRouter();
  const locale = useLocale();
  const isEn = locale === "en";
  const params = useParams<{ id: string }>();
  const tripId = params.id;

  const [stage, setStage] = useState<Stage>("loading");
  const [uid, setUid] = useState<string | null>(null);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [items, setItems] = useState<PlanItem[]>([]);
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [formError, setFormError] = useState<string | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  const loadPlanItems = useCallback(async () => {
    try {
      const data = await listPlanItems(tripId);
      setItems(data.plan_items ?? []);
    } catch {
      // 목록 새로고침 실패는 치명적이지 않음 — 기존 목록 유지
    }
  }, [tripId]);

  const load = useCallback(async () => {
    setStage("loading");
    const me = await fetchAuthMe();
    if (!me.logged_in) {
      setStage("anon");
      return;
    }
    setUid(me.uid ?? null);
    try {
      const t = await getTrip(tripId);
      setTrip(t);
      await loadPlanItems();
      setStage("ready");
    } catch (err) {
      if (err instanceof TripsApiError) {
        if (err.status === 403) return setStage("forbidden");
        if (err.status === 404) return setStage("missing");
      }
      setStage("error");
    }
  }, [tripId, loadPlanItems]);

  useEffect(() => {
    void load();
  }, [load]);

  function resetDraft() {
    setDraft(EMPTY_DRAFT);
    setFormError(null);
  }

  async function handleSubmitDraft() {
    const result = validatePlanItemDraft(draft);
    if (!result.ok) {
      setFormError(result.error);
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      if (draft.id === null) {
        await addPlanItem(tripId, result.value);
      } else {
        await updatePlanItem(tripId, draft.id, result.value);
      }
      resetDraft();
      await loadPlanItems();
    } catch (err) {
      setFormError(
        err instanceof TripsApiError ? err.message : isEn ? "Failed to save." : "저장에 실패했어요."
      );
    } finally {
      setBusy(false);
    }
  }

  function startEdit(item: PlanItem) {
    setDraft({
      id: item.id,
      day: String(item.day),
      time: item.time ?? "",
      place: item.place,
      category: item.category,
      memo: item.memo ?? "",
    });
    setFormError(null);
  }

  async function handleDelete(item: PlanItem) {
    setBusy(true);
    try {
      await deletePlanItem(tripId, item.id);
      if (draft.id === item.id) resetDraft();
      await loadPlanItems();
    } catch {
      // 무시 — 다음 새로고침에서 정합성 회복
    } finally {
      setBusy(false);
    }
  }

  async function handleInvite() {
    setBusy(true);
    try {
      const res = await createInvite(tripId);
      setInviteUrl(res.invite_url);
    } catch (err) {
      setInviteUrl(null);
      setFormError(
        err instanceof TripsApiError ? err.message : isEn ? "Failed to create invite." : "초대 링크 생성 실패."
      );
    } finally {
      setBusy(false);
    }
  }

  async function copyInvite() {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard 불가 환경 — URL은 화면에 노출돼 있음
    }
  }

  // ── 비ready 상태 ──────────────────────────────────────────────
  if (stage !== "ready") {
    return (
      <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col items-center justify-center gap-4 bg-background px-4 text-foreground">
        {stage === "loading" && (
          <p className="animate-pulse text-sm text-muted-foreground">
            {isEn ? "Loading trip..." : "여행을 불러오는 중..."}
          </p>
        )}
        {stage === "anon" && (
          <>
            <p className="text-sm text-muted-foreground">
              {isEn ? "Sign in to view this trip." : "이 여행을 보려면 로그인하세요."}
            </p>
            <button type="button" onClick={() => goToGoogleLogin()} className="cursor-pointer bg-primary px-5 py-2 text-sm font-medium text-primary-foreground">
              {isEn ? "Continue with Google" : "Google로 계속하기"}
            </button>
          </>
        )}
        {stage === "forbidden" && (
          <p className="text-sm text-muted-foreground">
            {isEn ? "You are not a member of this trip." : "이 여행의 멤버가 아니에요."}
          </p>
        )}
        {stage === "missing" && (
          <p className="text-sm text-muted-foreground">
            {isEn ? "Trip not found." : "여행을 찾을 수 없어요."}
          </p>
        )}
        {stage === "error" && (
          <button type="button" onClick={() => void load()} className="cursor-pointer bg-primary px-5 py-2 text-sm font-medium text-primary-foreground">
            {isEn ? "Retry" : "다시 시도"}
          </button>
        )}
      </div>
    );
  }

  // ── ready ─────────────────────────────────────────────────────
  const dest = trip?.destination as { city?: string; city_kr?: string } | undefined;
  const destName = isEn ? dest?.city : dest?.city_kr || dest?.city;
  const dayGroups = groupPlanItemsByDay(items);
  const ownerId = trip?.owner_user_id ?? null;

  return (
    <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col bg-background text-foreground">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <button type="button" onClick={() => router.push("/trips")} className="flex cursor-pointer items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-4 w-4" />
          {isEn ? "My trips" : "내 여행"}
        </button>
      </div>

      <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-5 py-6">
        {/* Header */}
        <h1 className="font-serif text-2xl font-bold text-foreground">
          {trip?.title || destName || (isEn ? "Trip" : "여행")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {destName}
          {trip?.start_date && trip?.end_date ? ` · ${trip.start_date} ~ ${trip.end_date}` : ""}
        </p>

        {/* Members + invite */}
        <section className="mt-5 border-t border-border pt-4">
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-base font-bold text-foreground">
              {isEn ? `Members (${trip?.members?.length ?? 0})` : `멤버 (${trip?.members?.length ?? 0})`}
            </h2>
            <button type="button" onClick={() => void handleInvite()} disabled={busy} className="flex cursor-pointer items-center gap-1 text-xs text-primary hover:underline disabled:opacity-50">
              <UserPlus className="h-3.5 w-3.5" />
              {isEn ? "Invite" : "동행 초대"}
            </button>
          </div>
          <ul className="mt-2 flex flex-wrap gap-2">
            {trip?.members?.map((m) => (
              <li key={m.user_id} className="flex items-center gap-1 border border-border px-2 py-1 text-xs text-foreground/90">
                {m.user_id === uid ? (isEn ? "You" : "나") : m.user_id.slice(0, 12)}
                {m.role === "owner" && (
                  <span className="text-[10px] uppercase text-primary">owner</span>
                )}
              </li>
            ))}
          </ul>
          {inviteUrl && (
            <div className="mt-3 flex items-center gap-2 border border-border bg-card px-3 py-2">
              <span className="flex-1 truncate font-mono text-[11px] text-muted-foreground">{inviteUrl}</span>
              <button type="button" onClick={() => void copyInvite()} className="flex cursor-pointer items-center gap-1 text-xs text-primary hover:underline">
                <Copy className="h-3.5 w-3.5" />
                {copied ? (isEn ? "Copied" : "복사됨") : isEn ? "Copy" : "복사"}
              </button>
            </div>
          )}
          <p className="mt-1 text-[10px] text-muted-foreground">
            {isEn ? "Invite links expire in 14 days." : "초대 링크는 14일 후 만료됩니다."}
          </p>
        </section>

        {/* Collaborative planner */}
        <section className="mt-6 border-t border-border pt-4">
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-base font-bold text-foreground">
              {isEn ? "Plan" : "공동 일정"}
            </h2>
            <button type="button" onClick={() => void loadPlanItems()} className="flex cursor-pointer items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <RefreshCw className="h-3.5 w-3.5" />
              {isEn ? "Refresh" : "새로고침"}
            </button>
          </div>

          {dayGroups.length === 0 && (
            <p className="mt-2 text-sm text-muted-foreground">
              {isEn ? "No plan items yet. Add the first one below." : "아직 일정이 없어요. 아래에서 추가해보세요."}
            </p>
          )}

          <div className="mt-3 flex flex-col gap-4">
            {dayGroups.map((group) => (
              <div key={group.day}>
                <h3 className="font-serif text-sm font-bold text-primary">Day {group.day}</h3>
                <ul className="mt-1 flex flex-col gap-1">
                  {group.items.map((item) => (
                    <li key={item.id} className="flex items-start gap-2 border-b border-border/40 py-1.5 text-sm">
                      <span className="w-12 shrink-0 font-mono text-xs text-muted-foreground">{item.time || "—"}</span>
                      <span className="shrink-0">{categoryEmoji(item.category)}</span>
                      <span className="flex-1 min-w-0">
                        <span className="text-foreground/90">{item.place}</span>
                        {item.memo && <span className="block text-xs text-muted-foreground">{item.memo}</span>}
                      </span>
                      {canEditPlanItem(item, uid, ownerId) && (
                        <span className="flex shrink-0 items-center gap-1.5">
                          <button type="button" aria-label={isEn ? "Edit" : "수정"} onClick={() => startEdit(item)} className="cursor-pointer text-muted-foreground hover:text-foreground">
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button type="button" aria-label={isEn ? "Delete" : "삭제"} onClick={() => void handleDelete(item)} disabled={busy} className="cursor-pointer text-muted-foreground hover:text-red-500 disabled:opacity-50">
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Add / edit form */}
          <div className="mt-5 border border-border bg-card p-3">
            <p className="mb-2 text-xs font-medium text-foreground">
              {draft.id === null ? (isEn ? "Add plan item" : "일정 추가") : isEn ? "Edit plan item" : "일정 수정"}
            </p>
            <div className="flex flex-wrap gap-2">
              <input
                type="number"
                min={1}
                max={60}
                value={draft.day}
                onChange={(e) => setDraft((d) => ({ ...d, day: e.target.value }))}
                placeholder="Day"
                aria-label={isEn ? "Day" : "일자"}
                className="w-16 border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              />
              <input
                type="time"
                value={draft.time}
                onChange={(e) => setDraft((d) => ({ ...d, time: e.target.value }))}
                aria-label={isEn ? "Time" : "시간"}
                className="w-28 border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              />
              <select
                value={draft.category}
                onChange={(e) => setDraft((d) => ({ ...d, category: e.target.value }))}
                aria-label={isEn ? "Category" : "카테고리"}
                className="cursor-pointer border border-border bg-background px-2 py-1.5 text-sm text-foreground"
              >
                {PLAN_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {categoryEmoji(c)} {c}
                  </option>
                ))}
              </select>
            </div>
            <input
              type="text"
              value={draft.place}
              onChange={(e) => setDraft((d) => ({ ...d, place: e.target.value }))}
              placeholder={isEn ? "Place (required)" : "장소 (필수)"}
              aria-label={isEn ? "Place" : "장소"}
              className="mt-2 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            />
            <input
              type="text"
              value={draft.memo}
              onChange={(e) => setDraft((d) => ({ ...d, memo: e.target.value }))}
              placeholder={isEn ? "Memo (optional)" : "메모 (선택)"}
              aria-label={isEn ? "Memo" : "메모"}
              className="mt-2 w-full border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            />
            {formError && <p className="mt-2 text-xs text-red-500/80">{formError}</p>}
            <div className="mt-3 flex items-center gap-2">
              <button type="button" onClick={() => void handleSubmitDraft()} disabled={busy} className="cursor-pointer bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50">
                {draft.id === null ? (isEn ? "Add" : "추가") : isEn ? "Save" : "저장"}
              </button>
              {draft.id !== null && (
                <button type="button" onClick={resetDraft} className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                  {isEn ? "Cancel" : "취소"}
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
