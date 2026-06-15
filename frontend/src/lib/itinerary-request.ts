import type { CityData } from "@/components/tarot/types";

/**
 * 저장된 여행 추천 요청(recommend payload) 또는 그 부분집합.
 * `/api/travel/recommend`로 보냈던 body가 그대로 들어온다.
 */
export interface TravelProfileLike {
  language?: string | null;
  nights?: number | string | null;
  travel_month?: number | string | null;
  interests?: string[] | null;
  persona?: string | null;
  companions?: {
    type?: string | null;
    pace?: string | null;
    [key: string]: unknown;
  } | null;
}

export interface ItineraryRequest {
  destination: {
    city: string;
    city_kr: string;
    country_id: string;
    vibe: string | null;
    best_months: (number | string)[];
    activities: string[];
    must_see: string[];
    est_cost_krw: number | null;
  };
  travel_profile: {
    language: string;
    nights: number;
    travel_month: number | null;
    interests: string[];
    persona: string;
    companions: { type: string; pace: string };
  };
}

function clampMonth(value: unknown): number | null {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 1 || n > 12) return null;
  return n;
}

function clampNights(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(60, Math.trunc(n)));
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

/**
 * 선택한 여행지(추천 카드) + 저장된 여행 프로필 → `/api/travel/itinerary` request body.
 *
 * - destination은 백엔드 일정 생성에 필요한 필드만 추려 스냅샷한다.
 * - travel_profile은 저장된 recommend payload에서 일정에 영향을 주는 필드만 옮긴다.
 * - language는 프로필에 없으면 locale로 결정(en → English, 그 외 → 한국어).
 */
export function buildItineraryRequest(
  destination: CityData,
  profile: TravelProfileLike | null | undefined,
  locale: string
): ItineraryRequest {
  const p = profile ?? {};
  const language =
    typeof p.language === "string" && p.language.trim().length > 0
      ? p.language
      : locale === "en"
        ? "English"
        : "한국어";

  return {
    destination: {
      city: destination.city,
      city_kr: destination.city_kr,
      country_id: destination.country_id,
      vibe: destination.vibe ?? null,
      best_months: Array.isArray(destination.best_months)
        ? destination.best_months
        : [],
      activities: asStringArray(destination.activities),
      must_see: asStringArray(destination.must_see),
      est_cost_krw:
        typeof destination.est_cost_krw === "number"
          ? destination.est_cost_krw
          : null,
    },
    travel_profile: {
      language,
      nights: clampNights(p.nights),
      travel_month: clampMonth(p.travel_month),
      interests: asStringArray(p.interests),
      persona: typeof p.persona === "string" ? p.persona : "",
      companions: {
        type:
          typeof p.companions?.type === "string"
            ? p.companions.type
            : "혼자 (솔로)",
        pace: typeof p.companions?.pace === "string" ? p.companions.pace : "",
      },
    },
  };
}
