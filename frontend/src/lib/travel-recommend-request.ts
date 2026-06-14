export interface TravelFormState {
  travel_month?: number | string;
  nights?: number | string;
  budget_krw?: number | null;
  interests?: string[];
  persona?: string;
  preferred_regions?: string[];
  companion_type?: string;
  headcount?: number;
  companion_ages?: string[];
  accessibility?: string[];
  pace?: string;
}

export interface TravelRecommendRequest {
  travel_month: number | null;
  nights: number;
  budget_krw: number | null;
  interests: string[];
  persona: string;
  preferred_regions: string[];
  companions: {
    type: string;
    headcount: number;
    ages: string[];
    accessibility: string[];
    pace: string;
  };
  top_n: number;
  language: string;
}

function clampMonth(m: unknown): number | null {
  const n = Number(m);
  if (!Number.isInteger(n) || n < 1 || n > 12) return null;
  return n;
}

function clampNights(v: unknown): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(60, Math.trunc(n)));
}

/** 폼 상태 → /api/travel/recommend request body. locale로 응답 언어 결정. */
export function buildTravelRecommendRequest(
  form: TravelFormState,
  locale: string
): TravelRecommendRequest {
  return {
    travel_month: clampMonth(form.travel_month),
    nights: clampNights(form.nights),
    budget_krw: form.budget_krw ?? null,
    interests: form.interests ?? [],
    persona: form.persona ?? "",
    preferred_regions: form.preferred_regions ?? [],
    companions: {
      type: form.companion_type ?? "혼자 (솔로)",
      headcount: form.headcount ?? 1,
      ages: form.companion_ages ?? [],
      accessibility: form.accessibility ?? [],
      pace: form.pace ?? "",
    },
    top_n: 5,
    language: locale === "en" ? "English" : "한국어",
  };
}
