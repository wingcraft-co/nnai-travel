"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "@/i18n/navigation";
import TarotDeck from "@/components/tarot/TarotDeck";
import type { DeckStage } from "@/components/tarot/TarotDeck";
import type { CityData, TarotSession } from "@/components/tarot/types";
import { TAROT_SESSION_KEY } from "@/components/tarot/types";
import { RitualTransition } from "@/components/transition/RitualTransition";
import {
  trackRecommendFailure,
  trackRecommendSubmit,
  trackRecommendSuccess,
  trackResultRevealComplete,
} from "@/lib/analytics/events";
import { applyLibraryAuthScope, collectLibraryCities } from "@/lib/library-storage";
import { clearServerOnboardingDrafts } from "@/lib/onboarding-draft-sync.mjs";
import { clearOnboardingFormDraft } from "@/lib/onboarding-form-draft";
import { clearOnboardingQuizDraft } from "@/lib/onboarding-quiz-draft";
import { normalizeCompletedResultSession } from "@/lib/result-session";

// ── Constants ──────────────────────────────────────────────────────

const RECOMMEND_PAYLOAD_KEY = "recommend_payload";
const TRAVEL_PROFILE_KEY = "travel_profile";
const RECOMMEND_SERVER_ERROR_MESSAGE = "서버가 불안정합니다.\n잠시 후 다시 시도해주세요.";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860";
const GUIDE_RESULT_RESTORE_KEY = "guide_result_restore_requested";

// ── Stage ──────────────────────────────────────────────────────────

type Stage = "loading" | DeckStage;
// DeckStage = "selecting" | "revealing" | "done"

// ── Session persistence ────────────────────────────────────────────

interface SessionV2 {
  session_id: string;
  allCities: CityData[];
  selectedIndices: number[];
  revealedCities: CityData[];
  readingCityIndex: number | null;
  readingMarkdown: string | null;
  parsedData: Record<string, unknown> | null;
  stage: Stage;
}

const SESSION_V2_KEY = "result_session_v2";

function resolveRecommendEntry(payload: Record<string, unknown>): "quiz" | "direct" {
  return payload.persona_type || payload.persona ? "quiz" : "direct";
}

function resolveErrorKind(error: unknown): "network" | "http" | "invalid_payload" {
  if (error instanceof SyntaxError) return "invalid_payload";
  if (error instanceof Error && /status|error/i.test(error.message)) return "http";
  return "network";
}

// ── Result Page ────────────────────────────────────────────────────

export default function ResultPage() {
  const router = useRouter();

  const [stage, setStage] = useState<Stage>("loading");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [allCities, setAllCities] = useState<CityData[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [revealedCities, setRevealedCities] = useState<CityData[] | null>(null);
  const [parsedData, setParsedData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [flippedIndices, setFlippedIndices] = useState<number[]>([]);
  const [travelOnlyRetry, setTravelOnlyRetry] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function detect() {
      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          cache: "no-store",
          credentials: "include",
        });
        if (cancelled || !response.ok) return;
        const payload = await response.json().catch(() => null);
        applyLibraryAuthScope(payload);
        const loggedIn = Boolean(payload?.logged_in);
        const hasPersona = Boolean(localStorage.getItem("persona_type"));
        if (!cancelled) setTravelOnlyRetry(loggedIn && hasPersona);
      } catch {
        applyLibraryAuthScope(null);
        // ignore
      }
    }
    detect();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Save session ────────────────────────────────────────────────

  const saveSession = useCallback(
    (overrides: Partial<SessionV2> & { stage: Stage }) => {
      const session: SessionV2 = {
        session_id: overrides.session_id ?? sessionId ?? "",
        allCities: overrides.allCities ?? allCities,
        selectedIndices: overrides.selectedIndices ?? selectedIndices,
        revealedCities: overrides.revealedCities ?? revealedCities ?? [],
        readingCityIndex: overrides.readingCityIndex ?? null,
        readingMarkdown: overrides.readingMarkdown ?? null,
        parsedData: overrides.parsedData ?? parsedData ?? null,
        stage: overrides.stage,
      };
      localStorage.setItem(SESSION_V2_KEY, JSON.stringify(session));

      // Legacy key for OAuth redirect
      const legacy: TarotSession = {
        session_id: session.session_id,
        selectedIndices: session.selectedIndices,
        revealedCities: session.revealedCities,
        readingCityIndex: session.readingCityIndex,
        readingMarkdown: session.readingMarkdown,
        stage: session.stage === "selecting" ? "selecting" : "reading",
      };
      localStorage.setItem(TAROT_SESSION_KEY, JSON.stringify(legacy));
    },
    [sessionId, allCities, selectedIndices, revealedCities, parsedData]
  );

  // ── API: recommend ───────────────────────────────────────────────

  const startRecommend = useCallback(async () => {
    const payloadStr = localStorage.getItem(RECOMMEND_PAYLOAD_KEY);
    if (!payloadStr) {
      router.replace("/onboarding/form");
      return;
    }

    setStage("loading");
    setError(null);

    try {
      const payload = JSON.parse(payloadStr) as Record<string, unknown>;
      const hasPersona = Boolean(payload.persona_type);
      trackRecommendSubmit({
        entry: resolveRecommendEntry(payload),
        hasPersona,
      });

      const res = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`recommend error: ${res.status}`);
      const data = (await res.json()) as {
        top_destinations?: CityData[];
        notes?: string[];
      };

      const topDestinations = data.top_destinations ?? [];
      if (topDestinations.length < 5) {
        trackRecommendFailure({
          stage: "recommend",
          errorKind: "invalid_payload",
        });
        setError(RECOMMEND_SERVER_ERROR_MESSAGE);
        setStage("loading");
        return;
      }

      trackRecommendSuccess({
        cardCount: topDestinations.length,
        hasPersona,
      });

      // 여행 일정(itinerary) 생성에 재사용할 프로필을 보존 (recommend payload는 곧 삭제됨)
      localStorage.setItem(TRAVEL_PROFILE_KEY, payloadStr);
      localStorage.removeItem(RECOMMEND_PAYLOAD_KEY);
      clearOnboardingFormDraft(localStorage);
      void clearServerOnboardingDrafts({ apiBase: API_BASE }).catch(() => undefined);

      const syntheticSessionId = `travel-${Date.now()}`;
      const destinationIndices = topDestinations.map((_, index) => index);
      setSessionId(syntheticSessionId);
      setParsedData(null);
      setAllCities(topDestinations);
      setSelectedIndices(destinationIndices);
      setRevealedCities(topDestinations);
      setFlippedIndices([]);
      setStage("selecting");

      saveSession({
        session_id: syntheticSessionId,
        allCities: topDestinations,
        selectedIndices: destinationIndices,
        revealedCities: topDestinations,
        parsedData: null,
        stage: "selecting",
      });
    } catch (error) {
      trackRecommendFailure({
        stage: "recommend",
        errorKind: resolveErrorKind(error),
      });
      setError(RECOMMEND_SERVER_ERROR_MESSAGE);
      setStage("loading");
    }
  }, [router, saveSession]);

  // ── Mount: restore or start ──────────────────────────────────────

  useEffect(() => {
    function restoreCompletedSession(): boolean {
      const savedStr = localStorage.getItem(SESSION_V2_KEY);
      if (!savedStr) return false;

      try {
        const saved = JSON.parse(savedStr) as SessionV2;
        const restored = normalizeCompletedResultSession(saved);
        if (restored) {
          setSessionId(restored.session_id);
          setAllCities(restored.allCities as CityData[]);
          setSelectedIndices(restored.selectedIndices);
          setRevealedCities(restored.revealedCities as CityData[]);
          setParsedData(restored.parsedData);
          setFlippedIndices(restored.selectedIndices);
          setStage("done");
          return true;
        }
      } catch {
        // corrupted
      }

      localStorage.removeItem(SESSION_V2_KEY);
      return false;
    }

    const shouldRestoreFromGuide = localStorage.getItem(GUIDE_RESULT_RESTORE_KEY) === "1";
    if (shouldRestoreFromGuide) {
      localStorage.removeItem(GUIDE_RESULT_RESTORE_KEY);
      if (restoreCompletedSession()) return;
    }

    const hasNewPayload = !!localStorage.getItem(RECOMMEND_PAYLOAD_KEY);

    if (hasNewPayload) {
      localStorage.removeItem(SESSION_V2_KEY);
      localStorage.removeItem(TAROT_SESSION_KEY);
      startRecommend();
      return;
    }

    // Restore previous session
    if (restoreCompletedSession()) return;

    // Legacy fallback
    const legacyStr = localStorage.getItem(TAROT_SESSION_KEY);
    if (legacyStr) {
      try {
        const saved = JSON.parse(legacyStr) as TarotSession;
        if (saved.session_id && saved.revealedCities?.length) {
          setSessionId(saved.session_id);
          setRevealedCities(saved.revealedCities);
          setFlippedIndices(saved.revealedCities.map((_, index) => index));
          setStage("done");
          return;
        }
      } catch {
        // corrupted
      }
      localStorage.removeItem(TAROT_SESSION_KEY);
    }

    router.replace("/onboarding/form");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Card selection ──────────────────────────────────────────────

  function toggleSelect(i: number) {
    setSelectedIndices((prev) => {
      if (prev.includes(i)) return prev.filter((x) => x !== i);
      if (prev.length >= 3) return prev;
      return [...prev, i];
    });
  }

  // ── Confirm → client flip → done ───────────────────────────────

  async function handleConfirm() {
    if (allCities.length === 0) return;
    setIsLoading(true);
    setError(null);

    try {
      const destinationIndices = allCities.map((_, index) => index);
      collectLibraryCities(allCities);
      setSelectedIndices(destinationIndices);
      setRevealedCities(allCities);
      setFlippedIndices([]);
      setStage("revealing");

      saveSession({
        selectedIndices: destinationIndices,
        revealedCities: allCities,
        stage: "revealing",
      });
      runFullSequence(allCities);
    } catch (err) {
      trackRecommendFailure({
        stage: "recommend",
        errorKind: resolveErrorKind(err),
      });
      setError(err instanceof Error ? err.message : "카드 열기에 실패했어요.");
    } finally {
      setIsLoading(false);
    }
  }

  function runFullSequence(cities: CityData[]) {
    const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

    (async () => {
      await delay(300);
      const opened: number[] = [];
      for (let i = 0; i < cities.length; i += 1) {
        opened.push(i);
        setFlippedIndices([...opened]);
        await delay(700);
      }
      await delay(900);

      setStage("done");
      trackResultRevealComplete(cities.length);
      saveSession({
        selectedIndices: cities.map((_, index) => index),
        revealedCities: cities,
        stage: "done",
      });
    })();
  }

  // ── Retry ──────────────────────────────────────────────────────

  function handleRetry() {
    setStage("loading");
    setSessionId(null);
    setAllCities([]);
    setSelectedIndices([]);
    setRevealedCities(null);
    setFlippedIndices([]);
    setParsedData(null);
    setError(null);
    setIsLoading(false);
    localStorage.removeItem(SESSION_V2_KEY);
    localStorage.removeItem(TAROT_SESSION_KEY);
    localStorage.removeItem(RECOMMEND_PAYLOAD_KEY);

    if (travelOnlyRetry) {
      router.push("/onboarding/form");
      return;
    }

    localStorage.removeItem("persona_type");
    clearOnboardingQuizDraft(localStorage);
    router.push("/onboarding/quiz");
  }

  const retryLabel = travelOnlyRetry ? "여행 유형 다시 고르기" : "처음부터 다시하기";

  // ── Render ──────────────────────────────────────────────────────

  const isDeckStage = stage !== "loading";

  return (
    <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col bg-background text-foreground">
      <RitualTransition />
      {/* Loading */}
      {stage === "loading" && (
        <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-4 px-4">
          {error ? (
            <>
              <p className="max-w-xs whitespace-pre-line text-center text-sm leading-6 text-red-500/80">{error}</p>
              <button type="button" onClick={() => startRecommend()} className="cursor-pointer px-6 py-2 text-sm font-medium bg-primary text-primary-foreground">
                카드 펼치기
              </button>
              <button type="button" onClick={handleRetry} className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                {retryLabel}
              </button>
            </>
          ) : (
            <p className="animate-pulse text-sm text-muted-foreground">
              맞춤 여행지를 분석하고 있어요...
            </p>
          )}
        </div>
      )}

      {/* Deck: selecting → revealing → done (5장 고정) */}
      {isDeckStage && (
        <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-6 px-4 py-10">
          {stage === "selecting" && (
            <div className="text-center">
              <h1 className="font-serif text-xl font-bold text-foreground mb-1">
                당신을 위한 여행지 TOP 5
              </h1>
              <p className="text-sm text-muted-foreground">
                카드를 열면 추천 여행지가 순서대로 공개됩니다
              </p>
            </div>
          )}

          {stage === "revealing" && (
            <div className="text-center">
              <h1 className="font-serif text-xl font-bold text-foreground mb-1">
                여행지 카드가 열립니다
              </h1>
            </div>
          )}

          {error && stage === "selecting" && (
            <p className="text-sm text-destructive text-center">{error}</p>
          )}

          <TarotDeck
            stage={stage as DeckStage}
            cities={allCities}
            selectedIndices={selectedIndices}
            revealedCities={revealedCities ?? allCities}
            flippedIndices={flippedIndices}
            onToggleSelect={toggleSelect}
            onConfirm={handleConfirm}
            onRetry={handleRetry}
            retryLabel={retryLabel}
            isLoading={isLoading}
          />
        </div>
      )}
    </div>
  );
}
