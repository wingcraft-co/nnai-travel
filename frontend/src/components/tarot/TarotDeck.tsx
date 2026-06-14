"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLocale } from "next-intl";
import { Banknote, Calendar, Plane, X, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import TarotCard from "./TarotCard";
import type { CityData } from "./types";
import {
  useKrwRate,
  formatMonthly,
  formatVisa,
  formatInternet,
  normalizeVisaType,
  formatClimate,
  computeCityTags,
} from "./format";
import { buildGoogleLoginUrl } from "@/lib/legal-content.mjs";
import { buildCityResourceLinks } from "@/lib/city-links.mjs";
import {
  markLoginPending,
  trackLoginClick,
  trackResultCardInteraction,
} from "@/lib/analytics/events";
import { readDevPreview, appendDevPreviewQuery } from "@/lib/dev-preview";
import { countryFlagEmoji } from "@/lib/country-flag";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860";
const PENDING_LOGIN_CITY_KEY = "pending_login_city_id";

// ── Google logo (official brand SVG — HEX 하드코딩은 브랜드 에셋 예외) ─────

function GoogleLogo({ size = 20 }: { size?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}

function VisaTitle({ title }: { title: string }) {
  const parenIndex = title.indexOf("(");
  if (parenIndex <= 0) {
    return <>{title}</>;
  }

  const main = title.slice(0, parenIndex).trimEnd();
  const parenthetical = title.slice(parenIndex).trimStart();
  return (
    <>
      {main}
      <br aria-hidden="true" />
      {parenthetical}
    </>
  );
}

function CityTitle({ title }: { title: string }) {
  const parenIndex = title.indexOf("(");
  if (parenIndex <= 0) {
    return <>{title}</>;
  }

  const main = title.slice(0, parenIndex).trimEnd();
  const detail = title.slice(parenIndex).trimStart();
  if (!main || !detail) {
    return <>{title}</>;
  }

  return (
    <>
      {main}
      <br aria-hidden="true" />
      {detail}
    </>
  );
}

function formatTravelCost(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "확인 중";
  return `약 ${Math.round(value / 10000).toLocaleString("ko-KR")}만원`;
}

function formatBestMonths(months: CityData["best_months"], locale: string): string {
  if (!Array.isArray(months) || months.length === 0) return locale === "en" ? "Checking" : "확인 중";
  return months.map((month) => `${month}${locale === "en" ? "" : "월"}`).join(locale === "en" ? ", " : ", ");
}

function shortList(items: string[] | null | undefined, limit = 4): string {
  if (!Array.isArray(items) || items.length === 0) return "";
  return items.slice(0, limit).join(", ");
}

// ── Stage type ────────────────────────────────────────────────────

export type DeckStage = "selecting" | "revealing" | "done";

// ── Personalized insight (ko only) ────────────────────────────────

function getPersonalizedInsight(
  persona: string | null,
  travelType: string | null,
  timeline: string | null,
  city: CityData,
): string | null {
  const tt = travelType ?? "";
  const hasCompanion =
    tt.includes("배우자") || tt.includes("파트너") || tt.includes("가족");

  // 1) 동반자 + 치안 >=8
  if (hasCompanion && city.safety_score != null && city.safety_score >= 8) {
    return `동반자와 함께라면 치안 ${city.safety_score}/10은 든든한 조건이에요.`;
  }
  // 2) 동반자 + 한인 커뮤니티 large
  if (hasCompanion && city.korean_community_size === "large") {
    return "한인 커뮤니티가 크게 형성되어 있어, 동반자와 함께 정착 초기에 도움이 돼요.";
  }
  // 3) free_spirit + tropical 계열 기후
  if (persona === "free_spirit" && city.climate?.includes("tropical")) {
    return "열대 기후는 자유로운 성향과 자연스럽게 맞아요.";
  }
  // 4) free_spirit + 무비자 90일+
  if (persona === "free_spirit" && (city.visa_free_days ?? 0) >= 90) {
    return "비자 걱정 없이 90일, 자유롭게 머물 수 있는 조건이에요.";
  }
  // 5) free_spirit + 갱신 가능
  if (persona === "free_spirit" && city.renewable === true) {
    return "갱신 가능한 비자라 눌러앉고 싶어지면 그냥 있어도 돼요.";
  }
  // 6) 단기 체류 + 무비자 60일+
  if (timeline?.includes("단기") && (city.visa_free_days ?? 0) >= 60) {
    return `단기 체류라면 비자 없이 바로 들어갈 수 있어요. (${city.visa_free_days ?? 0}일)`;
  }
  return null;
}

function guidePathForCity(city: CityData, locale: string): string {
  const raw = city.id || city.city || city.city_kr || "city";
  const cityId = String(raw).toLowerCase().trim().replace(/\s+/g, "-");
  return `/${locale}/guide/${encodeURIComponent(cityId)}`;
}

function normalizeRestoreKey(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

function cityRestoreKeys(city: CityData): string[] {
  return [city.id, city.city, city.city_kr]
    .map(normalizeRestoreKey)
    .filter((value, index, all) => value.length > 0 && all.indexOf(value) === index);
}

function rememberPendingLoginCity(city: CityData) {
  if (typeof window === "undefined") return;
  const key = cityRestoreKeys(city)[0];
  if (!key) return;
  try {
    sessionStorage.setItem(PENDING_LOGIN_CITY_KEY, key);
  } catch {
    // Storage can be unavailable in private browsing; login should still proceed.
  }
}

// ── City Lightbox ─────────────────────────────────────────────────

interface LightboxCard {
  state: "front" | "locked";
  city: CityData | null;
  orderNumber: number; // 1-based, for locked teaser label
}

function CityLightbox({
  cards,
  startIndex,
  onClose,
}: {
  cards: LightboxCard[];
  startIndex: number;
  onClose: () => void;
}) {
  const locale = useLocale();
  const krwRate = useKrwRate();
  const [index, setIndex] = useState(startIndex);
  const current = cards[index] ?? cards[0];
  const directCheckoutUrl =
    process.env.NEXT_PUBLIC_BILLING_PROVIDER === "polar"
      ? process.env.NEXT_PUBLIC_POLAR_CHECKOUT_URL ?? null
      : null;
  const isEn = locale === "en";

  const goPrev = () => setIndex((i) => (i - 1 + cards.length) % cards.length);
  const goNext = () => setIndex((i) => (i + 1) % cards.length);

  // Keyboard: ESC + ← →
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIndex((i) => (i - 1 + cards.length) % cards.length);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        setIndex((i) => (i + 1) % cards.length);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, cards.length]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="relative flex items-center gap-2"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Prev button (outside card left) */}
        <button
          type="button"
          onClick={goPrev}
          aria-label={isEn ? "Previous" : "이전"}
          className="shrink-0 w-8 h-8 cursor-pointer flex items-center justify-center transition-colors"
          style={{ color: "rgba(255,255,255,0.8)" }}
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        {/* Card wrapper (relative for external × positioning) */}
        <div className="relative">
          {/* × close — 카드 외부 우상단 (대각선 위) */}
          <button
            type="button"
            onClick={onClose}
            aria-label={isEn ? "Close" : "닫기"}
            className="absolute left-full bottom-full w-11 h-11 cursor-pointer flex items-center justify-center transition-colors"
            style={{ color: "rgba(255,255,255,0.8)", cursor: "pointer" }}
          >
            <X className="w-5 h-5" />
          </button>

          {/* Card frame — viewport-clamped so dense cards can scroll without clipping CTAs */}
          <motion.div
            key={index}
            initial={{ opacity: 0.4 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.18 }}
            className="flex flex-col overflow-hidden"
            style={{
              width: "min(340px, calc(100vw - 96px))",
              height: "min(620px, calc(100dvh - 128px))",
              maxHeight: "calc(100dvh - 128px)",
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              // 한국어 어절 중간에서 줄바꿈되는 CJK 기본 동작을 막고, 공백·구두점 경계에서만 wrap.
              // 영문은 기본대로 공백 기준, 너무 긴 영단어는 overflow-wrap으로 안전망.
              wordBreak: "keep-all",
              overflowWrap: "break-word",
            }}
          >
            {current.state === "front" && current.city ? (
              <LightboxFrontContent
                city={current.city}
                locale={locale}
                krwRate={krwRate}
              />
            ) : (
              <LightboxLockedTeaser
                orderNumber={current.orderNumber}
                locale={locale}
                checkoutUrl={directCheckoutUrl}
              />
            )}
          </motion.div>
        </div>

        {/* Next button (outside card right) */}
        <button
          type="button"
          onClick={goNext}
          aria-label={isEn ? "Next" : "다음"}
          className="shrink-0 w-8 h-8 cursor-pointer flex items-center justify-center transition-colors"
          style={{ color: "rgba(255,255,255,0.8)" }}
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </motion.div>
  );
}

// ── Lightbox Front Content (공개 카드) ─────────────────────────────

function LightboxFrontContent({
  city,
  locale,
  krwRate,
}: {
  city: CityData;
  locale: string;
  krwRate: number;
}) {
  const flag = countryFlagEmoji(city.country_id);
  const travelCost = formatTravelCost(city.est_cost_krw);
  const bestMonths = formatBestMonths(city.best_months, locale);
  const flightHours =
    city.avg_flight_hours_from_icn != null
      ? locale === "en"
        ? `${city.avg_flight_hours_from_icn}h`
        : `약 ${city.avg_flight_hours_from_icn}시간`
      : locale === "en"
        ? "Checking"
        : "확인 중";
  const activityList = shortList(city.activities);
  const mustSeeList = shortList(city.must_see);

  // Personalized insight (ko only)
  const [personalInsight, setPersonalInsight] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      if (locale !== "ko") {
        setPersonalInsight(null);
        return;
      }
      try {
        const persona = localStorage.getItem("persona_type");
        const sessionRaw = localStorage.getItem("result_session_v2");
        let travelType: string | null = null;
        let timeline: string | null = null;
        if (sessionRaw) {
          const session = JSON.parse(sessionRaw);
          const profile = session?.parsedData?._user_profile ?? {};
          travelType = typeof profile.travel_type === "string" ? profile.travel_type : null;
          timeline = typeof profile.timeline === "string" ? profile.timeline : null;
        }
        setPersonalInsight(getPersonalizedInsight(persona, travelType, timeline, city));
      } catch {
        setPersonalInsight(null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [city, locale]);

  // Auth check — /auth/me 쿠키 세션 (dev preview 모드면 강제 로그인 상태)
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(() => {
    if (typeof window === "undefined") return null;
    return readDevPreview().enabled ? true : null;
  });
  useEffect(() => {
    if (readDevPreview().enabled) return;
    let cancelled = false;
    fetch(`${API_BASE}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled) setIsLoggedIn(Boolean(data?.logged_in));
      })
      .catch(() => {
        if (!cancelled) setIsLoggedIn(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleGoogleLogin() {
    rememberPendingLoginCity(city);
    const returnTo = typeof window !== "undefined" ? window.location.href : "";
    markLoginPending();
    trackLoginClick("google");
    window.location.assign(buildGoogleLoginUrl(API_BASE, returnTo));
  }

  function handlePlanClick() {
    try {
      sessionStorage.setItem("selected_destination", JSON.stringify(city));
    } catch {
      // ignore storage failures; the placeholder state still renders
    }
    trackResultCardInteraction({
      action: "guide_click",
      cityId: city.id ?? undefined,
    });
  }

  const showLoginCta = false;
  const showDetailCta = false;
  const showDetailLoadingCta = false;
  const normalizedVisaType = normalizeVisaType(city.visa_type, city.country);
  const climateLabel = formatClimate(city.climate, locale);
  const isEn = locale === "en";

  // i18n 방어막 — 한국어 전용 데이터는 en locale에서 생략
  const showCityKr = !isEn && !!city.city_kr;
  const showCityInsight = !isEn && (!!city.city_insight || !!city.vibe);
  const showCityDescription = !isEn && !!city.city_description;
  // visa_type에 한글 잔존(대응 영문 없는 "없음/무비자" 계열)이면 en locale에서 섹션 생략
  const showVisaSection =
    false && !!normalizedVisaType && !(isEn && /[가-힣]/.test(normalizedVisaType));

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Header — flag + city */}
      <div className="flex shrink-0 flex-col items-center px-5 pb-3 pt-5">
        <span style={{ fontSize: 32 }}>{flag}</span>
        {showCityKr && (
          <h2 className="font-serif text-base font-bold text-center leading-tight mt-1.5" style={{ color: "var(--foreground)" }}>
            <CityTitle title={city.city_kr} />
          </h2>
        )}
        <p
          className="font-mono text-[11px] mt-0.5"
          style={{
            color: "var(--muted-foreground)",
            // en locale에서 city_kr 없이 city만 있을 땐 폰트 크기 올려 비중 보정
            fontSize: isEn ? 13 : undefined,
            marginTop: isEn ? 6 : undefined,
          }}
        >
          {city.city}, {city.country}
        </p>
      </div>

      {/* Primary metrics — 3x3 grid */}
      <div
        className="grid shrink-0 grid-cols-3 gap-y-0.5 px-5 py-3 text-center font-mono"
        style={{
          borderTop: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
          justifyItems: "center",
          alignItems: "center",
        }}
      >
        <Banknote className="w-4 h-4" style={{ color: "var(--muted-foreground)" }} />
        <Calendar className="w-4 h-4" style={{ color: "var(--muted-foreground)" }} />
        <Plane className="w-4 h-4" style={{ color: "var(--muted-foreground)" }} />

        <span className="text-[10px] uppercase leading-tight" style={{ color: "var(--muted-foreground)", letterSpacing: "0.05em" }}>
          {isEn ? "BUDGET" : "예상경비"}
        </span>
        <span className="text-[10px] uppercase leading-tight" style={{ color: "var(--muted-foreground)", letterSpacing: "0.05em" }}>
          {isEn ? "BEST" : "추천시기"}
        </span>
        <span className="text-[10px] uppercase leading-tight" style={{ color: "var(--muted-foreground)", letterSpacing: "0.05em" }}>
          {isEn ? "FLIGHT" : "비행"}
        </span>

        <span className="text-[13px] font-bold leading-tight" style={{ color: "var(--foreground)" }}>{travelCost}</span>
        <span className="text-[13px] font-bold leading-tight" style={{ color: "var(--foreground)" }}>{bestMonths}</span>
        <span className="text-[13px] font-bold leading-tight" style={{ color: "var(--foreground)" }}>{flightHours}</span>
      </div>

      {/* Body — scrolls independently so long copy never clips the bottom CTA */}
      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain flex flex-col gap-3 px-5 pt-3 pb-4 text-xs">
        {/* 1. City insight — 도시 한 줄 slogan (감성 intro, ko only) */}
        {showCityInsight && (
          <p className="text-xs italic leading-snug text-center" style={{ color: "var(--primary)" }}>
            {city.city_insight ?? city.vibe}
          </p>
        )}

        {/* 2. 비자 section — heading + 비자명(링크 통합) + 조건 라인 */}
        {showVisaSection && (
          <div className="flex flex-col gap-1">
            <h3
              className="font-serif text-[13px] font-bold"
              style={{ color: "var(--foreground)" }}
            >
              {isEn ? "Recommended Visa" : "추천 비자"}
            </h3>
            {city.visa_url ? (
              <a
                href={city.visa_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-w-0 max-w-full items-start gap-1 break-words leading-tight"
                style={{
                  color: "var(--foreground)",
                  textDecoration: "underline",
                  textUnderlineOffset: "2px",
                }}
              >
                <span className="min-w-0 break-words">
                  <VisaTitle title={normalizedVisaType} />
                </span>
                <ExternalLink className="w-3 h-3 shrink-0" aria-hidden="true" />
              </a>
            ) : (
              <p className="leading-tight" style={{ color: "var(--foreground)" }}>
                <VisaTitle title={normalizedVisaType} />
              </p>
            )}
            {(city.stay_months != null || city.renewable != null) && (
              <p
                className="font-mono text-[11px]"
                style={{ color: "var(--muted-foreground)", letterSpacing: "0.03em" }}
              >
                {city.stay_months != null &&
                  (isEn ? `Max stay ${city.stay_months} months` : `최대 체류 ${city.stay_months}개월`)}
                {city.stay_months != null && city.renewable != null && " · "}
                {city.renewable === true && (isEn ? "Renewable" : "연장 가능")}
                {city.renewable === false && (isEn ? "Non-renewable" : "연장 불가")}
              </p>
            )}
          </div>
        )}

        {/* 3. Personalized insight — 유저 맞춤 (ko only) */}
        {personalInsight && (
          <p className="font-serif text-xs leading-snug" style={{ color: "var(--primary)" }}>
            ✦ {personalInsight}
          </p>
        )}

        {/* 4. City description — 2–3줄 도시 소개 (ko only, 영어 번역 데이터 미보유) */}
        {showCityDescription && (
          <p className="leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
            {city.city_description}
          </p>
        )}

        {activityList && (
          <div className="flex flex-col gap-1">
            <h3 className="font-serif text-[13px] font-bold" style={{ color: "var(--foreground)" }}>
              {isEn ? "Good For" : "추천 활동"}
            </h3>
            <p className="leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
              {activityList}
            </p>
          </div>
        )}

        {mustSeeList && (
          <div className="flex flex-col gap-1">
            <h3 className="font-serif text-[13px] font-bold" style={{ color: "var(--foreground)" }}>
              {isEn ? "Must See" : "가볼 곳"}
            </h3>
            <p className="leading-relaxed" style={{ color: "var(--muted-foreground)" }}>
              {mustSeeList}
            </p>
          </div>
        )}

        {/* 5. Tags — 임계 돌파 강점 top 3 + climate (neutral descriptor) */}
        {(() => {
          const tags = computeCityTags(city, locale);
          if (city.vibe) tags.unshift(city.vibe);
          if (tags.length === 0 && !climateLabel) return null;
          return (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((label) => (
                <span
                  key={label}
                  className="inline-flex items-center px-2 py-0.5 font-mono text-[10px]"
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 9999,
                    color: "var(--muted-foreground)",
                    letterSpacing: "0.03em",
                  }}
                >
                  {label}
                </span>
              ))}
              {climateLabel && (
                <span
                  className="inline-flex items-center px-2 py-0.5 font-mono text-[10px]"
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 9999,
                    color: "var(--muted-foreground)",
                    letterSpacing: "0.03em",
                    opacity: 0.75,
                  }}
                >
                  {climateLabel}
                </span>
              )}
            </div>
          );
        })()}

        {/* 6. External links — 카테고리 3개 dot-joined 한 줄 (브랜드 노출 생략) */}
        {(() => {
          const links: { url: string; label: string }[] = buildCityResourceLinks(city, locale);
          if (links.length === 0) return null;
          return (
            <p className="text-[11px] text-center" style={{ color: "var(--muted-foreground)" }}>
              {links.map((l, i) => (
                <span key={l.url}>
                  {i > 0 && " · "}
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: "var(--primary)",
                      textDecoration: "underline",
                      textUnderlineOffset: "2px",
                    }}
                  >
                    {l.label}
                  </a>
                </span>
              ))}
            </p>
          );
        })()}

        <div
          className="sticky bottom-0 mt-auto flex shrink-0 flex-col gap-2 pt-3"
          style={{
            background:
              "linear-gradient(to bottom, color-mix(in srgb, var(--card) 0%, transparent), var(--card) 18%)",
          }}
        >
          <button
            type="button"
            onClick={handlePlanClick}
            className="w-full cursor-pointer py-2.5 text-center font-mono text-xs font-medium"
            style={{
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              borderRadius: 4,
              letterSpacing: "0.03em",
            }}
          >
            {isEn ? "Save for itinerary" : "이 여행지로 일정 만들기"}
          </button>
          <p className="text-center text-[10px]" style={{ color: "var(--muted-foreground)" }}>
            {isEn ? "Itinerary builder opens in the next phase." : "일정 생성 기능은 다음 단계에서 연결됩니다."}
          </p>
        </div>

        {showDetailLoadingCta && (
          <div
            className="sticky bottom-0 mt-auto flex shrink-0 flex-col pt-3"
            style={{
              background:
                "linear-gradient(to bottom, color-mix(in srgb, var(--card) 0%, transparent), var(--card) 18%)",
            }}
          >
            <button
              type="button"
              disabled
              className="w-full cursor-wait py-2.5 text-center font-mono text-xs font-medium"
              style={{
                background: "color-mix(in srgb, var(--primary) 72%, var(--muted-foreground))",
                color: "var(--primary-foreground)",
                borderRadius: 4,
                letterSpacing: "0.03em",
                opacity: 0.9,
              }}
            >
              <span className="inline-flex animate-pulse items-center justify-center">
                맞춤 보고서 준비 중
              </span>
            </button>
          </div>
        )}

        {/* Primary login CTA (ko + logged-out only) — 정보 텍스트 + Google Dark Theme 버튼 */}
        {showLoginCta && (
          <div
            className="sticky bottom-0 mt-auto flex shrink-0 flex-col gap-2 pt-3"
            style={{
              background:
                "linear-gradient(to bottom, color-mix(in srgb, var(--card) 0%, transparent), var(--card) 18%)",
            }}
          >
            <h3
              className="font-serif text-[13px] font-medium leading-tight text-center"
              style={{ color: "var(--foreground)" }}
            >
              로그인하고 {city.city_kr} 맞춤 가이드 받기
            </h3>
            {/* Google Sign-In 공식 Material Button Dark Theme — globals.css의 .gsi-material-button 그대로 */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              className="gsi-material-button"
              style={{ width: "100%", maxWidth: "none" }}
            >
              <div className="gsi-material-button-state" />
              <div className="gsi-material-button-content-wrapper">
                <div className="gsi-material-button-icon">
                  <GoogleLogo size={20} />
                </div>
                <span className="gsi-material-button-contents">
                  Google로 계속하기
                </span>
                <span style={{ display: "none" }}>Google로 계속하기</span>
              </div>
            </button>
          </div>
        )}

        {showDetailCta && (
          <div
            className="sticky bottom-0 mt-auto flex shrink-0 flex-col pt-3"
            style={{
              background:
                "linear-gradient(to bottom, color-mix(in srgb, var(--card) 0%, transparent), var(--card) 18%)",
            }}
          >
            <button
              type="button"
              onClick={handlePlanClick}
              className="w-full cursor-pointer py-2.5 text-center font-mono text-xs font-medium"
              style={{
                background: "var(--primary)",
                color: "var(--primary-foreground)",
                borderRadius: 4,
                letterSpacing: "0.03em",
              }}
            >
              맞춤 보고서 받기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Lightbox Locked Teaser (잠금 카드 — 추론 방지 skeleton) ────────

function LightboxLockedTeaser({
  orderNumber,
  locale,
  checkoutUrl,
}: {
  orderNumber: number;
  locale: string;
  checkoutUrl: string | null;
}) {
  const isEn = locale === "en";
  const label = isEn
    ? `PREMIUM PICK #${orderNumber}`
    : `잠겨진 카드 #${orderNumber}`;
  const ctaText = isEn ? "Unlock" : "잠금 해제";

  return (
    <div className="flex-1 min-h-0 flex flex-col items-center justify-between px-6 py-8">
      {/* Top — lock icon + order label */}
      <div className="flex flex-col items-center gap-3">
        <span style={{ fontSize: 48, opacity: 0.5 }}>🔒</span>
        <p
          className="font-mono text-[11px] uppercase"
          style={{ color: "var(--muted-foreground)", letterSpacing: "0.15em" }}
        >
          {label}
        </p>
      </div>

      {/* Middle — skeleton blocks (fixed shapes, 도시별 편차 없음) */}
      <div className="w-full flex flex-col items-center gap-5">
        <div className="w-full flex flex-col items-center gap-2">
          <div
            className="h-3.5 w-2/3 rounded"
            style={{ background: "color-mix(in srgb, var(--muted-foreground) 15%, transparent)" }}
          />
          <div
            className="h-2.5 w-1/2 rounded"
            style={{ background: "color-mix(in srgb, var(--muted-foreground) 10%, transparent)" }}
          />
        </div>

        <div
          className="w-full grid grid-cols-3 gap-3 py-3"
          style={{
            borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex flex-col items-center gap-1.5">
              <div
                className="h-3.5 w-3.5 rounded"
                style={{ background: "color-mix(in srgb, var(--muted-foreground) 20%, transparent)" }}
              />
              <div
                className="h-1.5 w-8 rounded"
                style={{ background: "color-mix(in srgb, var(--muted-foreground) 10%, transparent)" }}
              />
              <div
                className="h-2.5 w-6 rounded"
                style={{ background: "color-mix(in srgb, var(--muted-foreground) 18%, transparent)" }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Bottom — Pro CTA */}
      {checkoutUrl ? (
        <a
          href={checkoutUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackResultCardInteraction({ action: "unlock_click" })}
          className="w-full py-2.5 text-center font-mono text-xs font-medium"
          style={{
            background: "var(--primary)",
            color: "var(--primary-foreground)",
            borderRadius: 4,
            letterSpacing: "0.03em",
          }}
        >
          {ctaText}
        </a>
      ) : (
        <div className="w-full py-2.5" />
      )}
    </div>
  );
}


// ── Props ─────────────────────────────────────────────────────────

interface TarotDeckProps {
  stage: DeckStage;
  cities: CityData[];
  selectedIndices: number[];
  revealedCities: CityData[] | null;
  flippedIndices: number[];
  onToggleSelect: (index: number) => void;
  onConfirm: () => void;
  onRetry: () => void;
  retryLabel?: string;
  isLoading: boolean;
}

const MAX_SELECT = 3;

export default function TarotDeck({
  stage,
  cities,
  selectedIndices,
  revealedCities,
  flippedIndices,
  onToggleSelect,
  onConfirm,
  onRetry,
  retryLabel = "처음부터 다시하기",
  isLoading,
}: TarotDeckProps) {
  const count = cities.length;
  const allSelected = count > 0;
  const isSelecting = stage === "selecting";
  const isRevealing = stage === "revealing";
  const isDone = stage === "done";
  const isPostReveal = isRevealing || isDone;

  // ── Lightbox state ──────────────────────────────────────────────

  const [lightboxStartIndex, setLightboxStartIndex] = useState<number | null>(null);

  // OAuth 복귀 후 lightbox 자동 복원 — sessionStorage에 pending_login_city_id 저장된 경우
  useEffect(() => {
    if (!isPostReveal) return;
    let pendingId = "";
    try {
      pendingId = normalizeRestoreKey(sessionStorage.getItem(PENDING_LOGIN_CITY_KEY));
    } catch {
      return;
    }
    if (!pendingId) return;
    const pos = cities.findIndex(
      (c) => c && cityRestoreKeys(c).includes(pendingId)
    );
    if (pos < 0) {
      try {
        sessionStorage.removeItem(PENDING_LOGIN_CITY_KEY);
      } catch {
        // ignore storage failures
      }
      return;
    }
    try {
      sessionStorage.removeItem(PENDING_LOGIN_CITY_KEY);
    } catch {
      // ignore storage failures
    }
    setLightboxStartIndex(pos);
  }, [isPostReveal, cities]);

  const locale = useLocale();
  const isEn = locale === "en";

  // ── Per-card helpers ────────────────────────────────────────────

  function getCardState(i: number): "back" | "front" | "locked" {
    if (!isPostReveal) return "back";
    return "front";
  }

  function getCityForCard(i: number): CityData | null {
    if (!isPostReveal) return null;
    return cities[i] ?? null;
  }

  function isCardFlipped(i: number): boolean {
    if (!isPostReveal) return false;
    return flippedIndices.includes(i);
  }

  // ── Lightbox cards (5장 전체, 공개/잠금 혼합) ───────────────────

  const lightboxCards: LightboxCard[] = useMemo(() => {
    if (!isPostReveal) return [];
    return Array.from({ length: count }, (_, i) => {
      const city = cities[i] ?? null;
      return {
        state: "front" as const,
        city,
        orderNumber: i + 1,
      };
    });
  }, [cities, count, isPostReveal]);

  // ── Render card ─────────────────────────────────────────────────

  function renderCard(i: number) {
    const state = getCardState(i);
    const city = getCityForCard(i);
    const flipped = isCardFlipped(i);
    const isSelected = selectedIndices.includes(i);

    const handleClick = () => {
      if (isSelecting && !isLoading) {
        return;
      } else if (isDone) {
        if (city) {
          trackResultCardInteraction({
            action: "open_city",
            cityId: city.id ?? undefined,
          });
        }
        setLightboxStartIndex(i);
      }
    };

    return (
      <TarotCard
        key={i}
        state={state}
        size="sm"
        cityData={city}
        isSelected={false}
        isFlipped={flipped}
        onClick={isDone ? handleClick : undefined}
      />
    );
  }

  // ── Layout ──────────────────────────────────────────────────────

  return (
    <div className="flex flex-col items-center">
      {/* Cards — fixed position */}
      <div>
        <div className="hidden md:flex justify-center gap-3">
          {Array.from({ length: count }, (_, i) => renderCard(i))}
        </div>
        <div className="flex flex-col items-center gap-3 md:hidden">
          <div className="flex justify-center gap-3">
            {Array.from({ length: Math.min(3, count) }, (_, i) => renderCard(i))}
          </div>
          {count > 3 && (
            <div className="flex justify-center gap-3">
              {Array.from({ length: count - 3 }, (_, j) => renderCard(j + 3))}
            </div>
          )}
        </div>
      </div>

      {/* CTA area — fixed height with spacing from cards */}
      <div className="mt-8 h-20 flex items-center justify-center">
        <AnimatePresence>
          {isSelecting && allSelected && (
            <motion.button
              initial={{ opacity: 0, y: 8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.97 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              type="button"
              onClick={onConfirm}
              disabled={isLoading}
              className="cursor-pointer px-8 py-3 text-sm font-semibold disabled:cursor-not-allowed"
              style={{
                background: "var(--primary)",
                color: "var(--primary-foreground)",
                opacity: isLoading ? 0.5 : 1,
                boxShadow: "0 0 16px 2px color-mix(in srgb, var(--primary) 25%, transparent)",
                transition: "opacity 0.3s ease",
              }}
            >
              {isLoading ? (
                <span className="animate-pulse">
                  {isEn ? "Opening destinations..." : "여행지를 열고 있어요..."}
                </span>
              ) : isEn ? (
                "Open destinations"
              ) : (
                "여행지 카드 열기"
              )}
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Done: hint + actions */}
      {isDone && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex flex-col items-center gap-4"
        >
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            카드를 탭하면 상세 정보를 볼 수 있어요
          </p>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={onRetry}
              className="cursor-pointer text-xs transition-colors"
              style={{ color: "var(--muted-foreground)" }}
            >
              {retryLabel}
            </button>
          </div>
        </motion.div>
      )}

      {/* Lightbox */}
      <AnimatePresence>
        {lightboxStartIndex !== null && lightboxCards.length > 0 && (
          <CityLightbox
            cards={lightboxCards}
            startIndex={lightboxStartIndex}
            onClose={() => setLightboxStartIndex(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
