"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { AnimatePresence, motion } from "framer-motion";
import type { PersonaType } from "@/data/personas";
import { House } from "lucide-react";
import { ProgressBar } from "@/components/onboarding/progress-bar";
import { SelectCard } from "@/components/onboarding/select-card";
import { getOnboardingCopy } from "@/lib/onboarding-content";
import {
  readOnboardingFormDraft,
  writeOnboardingFormDraft,
} from "@/lib/onboarding-form-draft";
import {
  trackFormAbandon,
  trackFormStepComplete,
  trackFormStepView,
  trackOnboardingStepDwell,
} from "@/lib/analytics/events";
import { buildTravelRecommendRequest } from "@/lib/travel-recommend-request";
import dynamic from "next/dynamic";

const IS_DEBUG = process.env.NEXT_PUBLIC_DEBUG_MODE === "1";

const CityDebugPanel = IS_DEBUG
  ? dynamic(() => import("@/components/debug/CityDebugPanel"), { ssr: false })
  : null;

// ── Types ────────────────────────────────────────────────────────

interface FormData {
  travel_month: number | string;   // 1..12, "" = 미정
  nights: number | string;          // 박 수
  budget_krw: number | null;        // 총 예산(원)
  interests: string[];              // 휴양·자연·도시·미식·액티비티·문화 등
  persona: string;                  // 퀴즈 결과 매핑 (힐링 휴양러 등)
  preferred_regions: string[];      // 동남아·유럽·동북아 등
  companion_type: string;           // 혼자/커플/가족/친구
  headcount: number;
  companion_ages: string[];         // 성인·아동·영유아·시니어
  accessibility: string[];          // 없음·유아동반·휠체어 등
  pace: string;                     // 휴양 위주·균형·빡빡하게
}

const INITIAL_FORM: FormData = {
  travel_month: "",
  nights: 4,
  budget_krw: null,
  interests: [],
  persona: "",
  preferred_regions: [],
  companion_type: "",
  headcount: 1,
  companion_ages: [],
  accessibility: [],
  pace: "",
};

const TOTAL_STEPS = 5;

const PERSONA_TO_TRAVEL: Record<string, string> = {
  wanderer: "탐험가형",
  local: "현지 몰입형",
  planner: "계획형 여행자",
  free_spirit: "자유로운 영혼",
  pioneer: "오프비트 개척자",
};

const personaGif: Record<string, string> = {
  wanderer: "/wanderer.gif",
  local: "/local.gif",
  planner: "/planner.gif",
  free_spirit: "/free_spirit.gif",
  pioneer: "/pioneer.gif",
};

// ── Option data (inline, ko-first; i18n keys are Task 6) ─────────

const TRAVEL_MONTH_OPTIONS_KO = [
  { label: "1월", value: "1" },
  { label: "2월", value: "2" },
  { label: "3월", value: "3" },
  { label: "4월", value: "4" },
  { label: "5월", value: "5" },
  { label: "6월", value: "6" },
  { label: "7월", value: "7" },
  { label: "8월", value: "8" },
  { label: "9월", value: "9" },
  { label: "10월", value: "10" },
  { label: "11월", value: "11" },
  { label: "12월", value: "12" },
];

const TRAVEL_MONTH_OPTIONS_EN = [
  { label: "Jan", value: "1" },
  { label: "Feb", value: "2" },
  { label: "Mar", value: "3" },
  { label: "Apr", value: "4" },
  { label: "May", value: "5" },
  { label: "Jun", value: "6" },
  { label: "Jul", value: "7" },
  { label: "Aug", value: "8" },
  { label: "Sep", value: "9" },
  { label: "Oct", value: "10" },
  { label: "Nov", value: "11" },
  { label: "Dec", value: "12" },
];

const NIGHTS_OPTIONS_KO = [
  { label: "2박 3일", value: "2" },
  { label: "3박 4일", value: "3" },
  { label: "4박 5일", value: "4" },
  { label: "일주일+", value: "7" },
];

const NIGHTS_OPTIONS_EN = [
  { label: "2 nights", value: "2" },
  { label: "3 nights", value: "3" },
  { label: "4 nights", value: "4" },
  { label: "7+ nights", value: "7" },
];

const BUDGET_OPTIONS_KO = [
  { label: "100만 이하", value: "1000000" },
  { label: "100~200만", value: "2000000" },
  { label: "200~400만", value: "4000000" },
  { label: "400만+", value: "6000000" },
];

const BUDGET_OPTIONS_EN = [
  { label: "Under ₩1M", value: "1000000" },
  { label: "₩1M–2M", value: "2000000" },
  { label: "₩2M–4M", value: "4000000" },
  { label: "₩4M+", value: "6000000" },
];

const INTERESTS_OPTIONS_KO = [
  { label: "휴양", value: "휴양" },
  { label: "자연", value: "자연" },
  { label: "도시", value: "도시" },
  { label: "미식", value: "미식" },
  { label: "액티비티", value: "액티비티" },
  { label: "문화", value: "문화" },
  { label: "쇼핑", value: "쇼핑" },
  { label: "나이트라이프", value: "나이트라이프" },
];

const INTERESTS_OPTIONS_EN = [
  { label: "Relaxation", value: "휴양" },
  { label: "Nature", value: "자연" },
  { label: "City", value: "도시" },
  { label: "Food", value: "미식" },
  { label: "Activities", value: "액티비티" },
  { label: "Culture", value: "문화" },
  { label: "Shopping", value: "쇼핑" },
  { label: "Nightlife", value: "나이트라이프" },
];

const REGIONS_OPTIONS_KO = [
  { label: "동남아", value: "동남아" },
  { label: "동북아", value: "동북아" },
  { label: "유럽", value: "유럽" },
  { label: "북미", value: "북미" },
  { label: "오세아니아", value: "오세아니아" },
  { label: "중동", value: "중동" },
  { label: "상관없음", value: "상관없음" },
];

const REGIONS_OPTIONS_EN = [
  { label: "Southeast Asia", value: "동남아" },
  { label: "Northeast Asia", value: "동북아" },
  { label: "Europe", value: "유럽" },
  { label: "North America", value: "북미" },
  { label: "Oceania", value: "오세아니아" },
  { label: "Middle East", value: "중동" },
  { label: "No preference", value: "상관없음" },
];

const COMPANION_TYPE_OPTIONS_KO = [
  { label: "혼자", value: "혼자" },
  { label: "커플", value: "커플" },
  { label: "가족", value: "가족" },
  { label: "친구", value: "친구" },
];

const COMPANION_TYPE_OPTIONS_EN = [
  { label: "Solo", value: "혼자" },
  { label: "Couple", value: "커플" },
  { label: "Family", value: "가족" },
  { label: "Friends", value: "친구" },
];

const COMPANION_AGES_OPTIONS_KO = [
  { label: "성인", value: "성인" },
  { label: "아동 (7~12세)", value: "아동" },
  { label: "영유아 (0~6세)", value: "영유아" },
  { label: "시니어", value: "시니어" },
];

const COMPANION_AGES_OPTIONS_EN = [
  { label: "Adult", value: "성인" },
  { label: "Child (7–12)", value: "아동" },
  { label: "Infant (0–6)", value: "영유아" },
  { label: "Senior", value: "시니어" },
];

const ACCESSIBILITY_OPTIONS_KO = [
  { label: "없음", value: "없음" },
  { label: "유아 동반", value: "유아동반" },
  { label: "휠체어 필요", value: "휠체어" },
];

const ACCESSIBILITY_OPTIONS_EN = [
  { label: "None", value: "없음" },
  { label: "With infants", value: "유아동반" },
  { label: "Wheelchair access", value: "휠체어" },
];

const PACE_OPTIONS_KO = [
  { label: "휴양 위주", value: "휴양 위주" },
  { label: "균형 잡힌", value: "균형" },
  { label: "빡빡하게", value: "빡빡하게" },
];

const PACE_OPTIONS_EN = [
  { label: "Relaxed", value: "휴양 위주" },
  { label: "Balanced", value: "균형" },
  { label: "Packed", value: "빡빡하게" },
];

// ── Helpers ──────────────────────────────────────────────────────

function hasKids(companionType: string) {
  return companionType.includes("가족") || companionType.includes("아이");
}

// ── Component ────────────────────────────────────────────────────

export default function FormPage() {
  const locale = useLocale();
  const router = useRouter();
  const copy = getOnboardingCopy(locale);
  const [personaType, setPersonaType] = useState<PersonaType | null>(null);
  const [personaVector, setPersonaVector] = useState<Record<string, number> | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const previousStepRef = useRef<number | null>(null);
  const stepEnteredAtRef = useRef(Date.now());
  const currentStepRef = useRef(1);
  const submittedRef = useRef(false);
  const [draftHydrated, setDraftHydrated] = useState(false);
  const [reviewStep, setReviewStep] = useState<number | null>(null);

  // Locale-branched option sets
  const isEn = locale === "en";
  const travelMonthOptions = isEn ? TRAVEL_MONTH_OPTIONS_EN : TRAVEL_MONTH_OPTIONS_KO;
  const nightsOptions = isEn ? NIGHTS_OPTIONS_EN : NIGHTS_OPTIONS_KO;
  const budgetOptions = isEn ? BUDGET_OPTIONS_EN : BUDGET_OPTIONS_KO;
  const interestsOptions = isEn ? INTERESTS_OPTIONS_EN : INTERESTS_OPTIONS_KO;
  const regionsOptions = isEn ? REGIONS_OPTIONS_EN : REGIONS_OPTIONS_KO;
  const companionTypeOptions = isEn ? COMPANION_TYPE_OPTIONS_EN : COMPANION_TYPE_OPTIONS_KO;
  const companionAgesOptions = isEn ? COMPANION_AGES_OPTIONS_EN : COMPANION_AGES_OPTIONS_KO;
  const accessibilityOptions = isEn ? ACCESSIBILITY_OPTIONS_EN : ACCESSIBILITY_OPTIONS_KO;
  const paceOptions = isEn ? PACE_OPTIONS_EN : PACE_OPTIONS_KO;

  useEffect(() => {
    const stored = localStorage.getItem("persona_type") as PersonaType | null;
    setPersonaType(stored);
    const vectorStr = localStorage.getItem("persona_vector");
    if (vectorStr) {
      try { setPersonaVector(JSON.parse(vectorStr)); } catch {}
    }

    const draft = readOnboardingFormDraft(localStorage);
    if (draft) {
      setForm({ ...INITIAL_FORM, ...draft.form });
      setCurrentStep(Math.min(Math.max(Math.trunc(draft.currentStep), 1), TOTAL_STEPS));
    }
    setDraftHydrated(true);
  }, []);

  useEffect(() => {
    if (!draftHydrated || submittedRef.current) return;
    writeOnboardingFormDraft(localStorage, { currentStep, form });
  }, [currentStep, draftHydrated, form]);

  useEffect(() => {
    const now = Date.now();
    const previousStep = previousStepRef.current;

    if (previousStep !== null && previousStep !== currentStep) {
      trackOnboardingStepDwell({
        flow: "form",
        stepNumber: previousStep,
        durationMs: now - stepEnteredAtRef.current,
      });
      stepEnteredAtRef.current = now;
    }

    previousStepRef.current = currentStep;
    currentStepRef.current = currentStep;
    trackFormStepView(currentStep);
  }, [currentStep]);

  useEffect(() => {
    return () => {
      if (submittedRef.current) return;

      trackOnboardingStepDwell({
        flow: "form",
        stepNumber: currentStepRef.current,
        durationMs: Date.now() - stepEnteredAtRef.current,
      });
      trackFormAbandon({
        flow: "form",
        stepNumber: currentStepRef.current,
      });
    };
  }, []);

  function canProceed(): boolean {
    switch (currentStep) {
      case 1: return form.nights !== "";
      case 2: return form.budget_krw !== null;
      case 3: return form.interests.length > 0;
      case 4: return form.preferred_regions.length > 0;
      case 5: return form.companion_type !== "" && form.pace !== "";
      default: return false;
    }
  }

  function toggleMulti(field: keyof FormData, value: string, max?: number) {
    setReviewStep(null);
    setForm((prev) => {
      const arr = prev[field] as string[];
      if (arr.includes(value)) {
        return { ...prev, [field]: arr.filter((v) => v !== value) };
      }
      if (max && arr.length >= max) return prev;
      return { ...prev, [field]: [...arr, value] };
    });
  }

  function updateForm(patch: Partial<FormData>) {
    setReviewStep(null);
    setForm((prev) => ({ ...prev, ...patch }));
  }

  async function handleSubmit() {
    setIsLoading(true);
    setError(null);

    try {
      if (!completedSteps.includes(currentStep)) {
        trackFormStepComplete(currentStep);
        setCompletedSteps((prev) => [...prev, currentStep]);
      }

      const payload = buildTravelRecommendRequest(
        {
          travel_month: form.travel_month,
          nights: form.nights,
          budget_krw: form.budget_krw,
          interests: form.interests,
          persona: form.persona || PERSONA_TO_TRAVEL[personaType ?? ""] || "",
          preferred_regions: form.preferred_regions,
          companion_type: form.companion_type,
          headcount: form.headcount,
          companion_ages: form.companion_ages,
          accessibility: form.accessibility,
          pace: form.pace,
        },
        locale
      );

      // Save payload so result page can call /api/travel/recommend itself
      localStorage.setItem("recommend_payload", JSON.stringify(payload));
      // Clear any stale tarot session from a previous run
      localStorage.removeItem("tarot_session");

      submittedRef.current = true;
      router.push("/result");
    } catch {
      setError(copy.form.navigation.error);
    } finally {
      setIsLoading(false);
    }
  }

  function handleNext() {
    if (currentStep < TOTAL_STEPS) {
      if (!completedSteps.includes(currentStep)) {
        trackFormStepComplete(currentStep);
        setCompletedSteps((prev) => [...prev, currentStep]);
      }
      setCurrentStep(currentStep + 1);
    } else {
      handleSubmit();
    }
  }

  function shouldAutoAdvance(): boolean {
    // All steps in the travel form use explicit buttons (multi-select or compound),
    // so auto-advance is disabled. Steps 1-4 still advance via the Next button.
    return false;
  }

  useEffect(() => {
    if (currentStep >= 5) return;
    if (reviewStep === currentStep) return;
    if (!shouldAutoAdvance()) return;

    const timer = setTimeout(() => {
      handleNext();
    }, 300);

    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, reviewStep]);

  function handleBack() {
    if (currentStep <= 1) return;
    const prev = currentStep - 1;
    setReviewStep(prev);
    setCurrentStep(prev);
  }

  const stepTitles = isEn
    ? [
        "When are you traveling?",
        "What's your budget?",
        "What are you into?",
        "Where do you want to go?",
        "Who are you traveling with?",
      ]
    : [
        "언제 여행을 떠날 계획이에요?",
        "여행 예산은 어느 정도예요?",
        "어떤 여행을 원해요?",
        "가고 싶은 지역이 있어요?",
        "누구와 함께 가나요?",
      ];

  return (
    <>
    {CityDebugPanel && (
      <CityDebugPanel
        incomeRange=""
        timeline=""
        preferredCountries={form.preferred_regions}
      />
    )}
    <div className="mx-auto flex min-h-screen max-w-sm w-full flex-col">
      {/* 프로그레스바 */}
      <div className="flex items-center gap-3 pt-6 px-4">
        {currentStep === 1 ? (
          <button
            type="button"
            onClick={() => router.push("/?nav=home")}
            className="shrink-0 cursor-pointer text-muted-foreground transition-colors hover:text-foreground"
          >
            <House className="size-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleBack}
            className="shrink-0 cursor-pointer text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {copy.form.navigation.back}
          </button>
        )}
        <ProgressBar current={currentStep} total={TOTAL_STEPS} />
      </div>

      {/* 콘텐츠 */}
      <div className="flex flex-1 flex-col justify-start pt-24 px-4">
        {/* 스텝 캐릭터 — 배지 바로 위, 스텝 간 슬라이드 이동 */}
        <div className="relative h-12">
          {personaType ? (
          <motion.img
            src={personaGif[personaType] ?? "/earth_64.gif"}
            alt=""
            width={40}
            height={40}
            className="absolute bottom-0 object-contain"
            style={{ imageRendering: "pixelated" }}
            animate={{
              left: `${((currentStep - 1) / (TOTAL_STEPS - 1)) * 100}%`,
              x: "-50%",
            }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
          />
          ) : (
          <motion.div
            className="absolute bottom-0 flex"
            animate={{
              left: `${((currentStep - 1) / (TOTAL_STEPS - 1)) * 100}%`,
              x: "-50%",
            }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
          >
            <img
              src="/grace_64.gif"
              alt=""
              width={40}
              height={40}
              className="object-contain"
              style={{ imageRendering: "pixelated" }}
            />
            <img
              src="/rocky_64.gif"
              alt=""
              width={40}
              height={40}
              className="object-contain -ml-4"
              style={{ imageRendering: "pixelated" }}
            />
          </motion.div>
          )}
        </div>

        {/* 페르소나 배지 */}
        {personaType && (() => {
          const label = copy.result.personas[personaType].label;
          const badgeText = locale === "ko"
            ? `${label}${(() => {
                const lastChar = label.slice(-1);
                const code = lastChar.charCodeAt(0) - 0xAC00;
                return code >= 0 && code % 28 > 0 ? "을" : "를";
              })()}${copy.form.personaBadge.suffix}`
            : `${copy.form.personaBadge.prefix}${label}${copy.form.personaBadge.suffix}`;

          return (
            <div className="mb-6 border border-primary/20 bg-primary/5 px-3 py-2 text-center text-xs text-primary">
              {badgeText}
            </div>
          );
        })()}

        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { duration: 0.35 } }}
            exit={{ opacity: 0, transition: { duration: 0.25 } }}
          >
            <h2 className="whitespace-pre-line text-xl font-medium leading-relaxed text-foreground mb-8">
              {stepTitles[currentStep - 1]}
            </h2>

            {/* Step 1: 여행 시기·기간 */}
            {currentStep === 1 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">
                    {isEn ? "Travel month (optional)" : "여행 월 (선택)"}
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {travelMonthOptions.map((option) => {
                      const isActive = String(form.travel_month) === option.value;
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => updateForm({ travel_month: isActive ? "" : option.value })}
                          className={`w-full cursor-pointer border px-2 py-3 text-center text-sm font-medium transition-colors ${
                            isActive
                              ? "border-[#d97706] bg-[#d97706] text-white"
                              : "border-border bg-muted text-foreground hover:bg-accent"
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">
                    {isEn ? "Trip length" : "여행 기간"}
                  </label>
                  <SelectCard
                    options={nightsOptions}
                    selected={String(form.nights)}
                    onSelect={(v) => updateForm({ nights: Number(v) })}
                    mode="single"
                  />
                </div>
              </div>
            )}

            {/* Step 2: 예산 */}
            {currentStep === 2 && (
              <div className="space-y-2">
                <label className="text-sm text-muted-foreground">
                  {isEn ? "Total trip budget" : "총 여행 예산"}
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {budgetOptions.map((option) => {
                    const isActive = form.budget_krw === Number(option.value);
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => updateForm({ budget_krw: Number(option.value) })}
                        className={`w-full cursor-pointer border px-4 py-3.5 text-left text-sm font-medium transition-colors ${
                          isActive
                            ? "border-[#d97706] bg-[#d97706] text-white"
                            : "border-border bg-muted text-foreground hover:bg-accent"
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Step 3: 관심사 */}
            {currentStep === 3 && (
              <div className="space-y-2">
                <label className="text-sm text-muted-foreground">
                  {isEn ? "Select all that apply" : "복수 선택 가능"}
                </label>
                <SelectCard
                  options={interestsOptions}
                  selected={form.interests}
                  onSelect={(v) => toggleMulti("interests", v)}
                  mode="multi"
                />
              </div>
            )}

            {/* Step 4: 선호 권역 */}
            {currentStep === 4 && (
              <div className="space-y-2">
                <label className="text-sm text-muted-foreground">
                  {isEn ? "Select all that apply" : "복수 선택 가능"}
                </label>
                <SelectCard
                  options={regionsOptions}
                  selected={form.preferred_regions}
                  onSelect={(v) => toggleMulti("preferred_regions", v)}
                  mode="multi"
                />
              </div>
            )}

            {/* Step 5: 동행 유형 + 인원 + 조건부 필드 + 여행 페이스 */}
            {currentStep === 5 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">
                    {isEn ? "Companion type" : "동행 유형"}
                  </label>
                  <SelectCard
                    options={companionTypeOptions}
                    selected={form.companion_type}
                    onSelect={(v) => updateForm({ companion_type: v })}
                    mode="single"
                  />
                </div>

                {form.companion_type !== "" && (
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">
                      {isEn ? "Number of travelers" : "총 인원 수"}
                    </label>
                    <div className="flex items-center gap-4">
                      <button
                        type="button"
                        onClick={() => updateForm({ headcount: Math.max(1, form.headcount - 1) })}
                        className="cursor-pointer border border-border bg-muted px-4 py-2 text-lg font-medium hover:bg-accent"
                      >
                        −
                      </button>
                      <span className="min-w-[2rem] text-center text-base font-medium">{form.headcount}</span>
                      <button
                        type="button"
                        onClick={() => updateForm({ headcount: Math.min(20, form.headcount + 1) })}
                        className="cursor-pointer border border-border bg-muted px-4 py-2 text-lg font-medium hover:bg-accent"
                      >
                        +
                      </button>
                    </div>
                  </div>
                )}

                {hasKids(form.companion_type) && (
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">
                      {isEn ? "Ages in your group" : "동행 나이대"}
                    </label>
                    <SelectCard
                      options={companionAgesOptions}
                      selected={form.companion_ages}
                      onSelect={(v) => toggleMulti("companion_ages", v)}
                      mode="multi"
                    />
                  </div>
                )}

                {hasKids(form.companion_type) && (
                  <div className="space-y-2">
                    <label className="text-sm text-muted-foreground">
                      {isEn ? "Accessibility needs" : "이동 편의"}
                    </label>
                    <SelectCard
                      options={accessibilityOptions}
                      selected={form.accessibility}
                      onSelect={(v) => toggleMulti("accessibility", v)}
                      mode="multi"
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">
                    {isEn ? "Travel pace" : "여행 페이스"}
                  </label>
                  <SelectCard
                    options={paceOptions}
                    selected={form.pace}
                    onSelect={(v) => updateForm({ pace: v })}
                    mode="single"
                  />
                </div>
              </div>
            )}

            {/* CTA 버튼 — 모든 스텝에서 표시 */}
            <div className="mt-10 space-y-3">
              {error && (
                <p className="mb-3 text-center text-sm text-destructive">{error}</p>
              )}
              <button
                type="button"
                onClick={handleNext}
                disabled={!canProceed() || isLoading}
                className="w-full cursor-pointer bg-primary py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-30"
              >
                {isLoading ? copy.form.navigation.loading : currentStep === TOTAL_STEPS ? copy.form.navigation.submit : copy.form.navigation.next}
              </button>
              {currentStep === 5 && !isLoading && (
                <button
                  type="button"
                  onClick={handleSubmit}
                  className="w-full cursor-pointer py-1.5 text-xs font-medium text-muted-foreground/60 transition-colors hover:text-muted-foreground"
                >
                  {copy.form.navigation.skip}
                </button>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
    </>
  );
}
