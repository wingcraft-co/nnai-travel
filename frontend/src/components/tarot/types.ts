// Shared types for all tarot components

export interface CityData {
  id?: string | null;
  city: string;
  city_kr: string;
  country: string;
  country_id: string;
  vibe?: string | null;
  budget_tier?: string | null;
  best_months?: number[] | string[] | null;
  peak_season?: string | null;
  avg_flight_hours_from_icn?: number | null;
  activities?: string[] | null;
  must_see?: string[] | null;
  est_cost_krw?: number | null;
  reasons?: { point?: string }[] | null;
  notes?: string[] | null;
  visa_type?: string | null;
  visa_url?: string | null;
  monthly_cost_usd?: number | null;
  score: number;
  plan_b_trigger?: boolean | null;
  climate?: string | null;
  data_verified_date?: string | null;
  city_description?: string | null;
  city_insight?: string | null;
  internet_mbps?: number | null;
  safety_score?: number | null;
  english_score?: number | null;
  nomad_score?: number | null;
  coworking_score?: number | null;
  cowork_usd_month?: number | null;
  community_size?: string | null;
  korean_community_size?: string | null;
  mid_term_rent_usd?: number | null;
  tax_residency_days?: number | null;
  flatio_search_url?: string | null;
  anyplace_search_url?: string | null;
  nomad_meetup_url?: string | null;
  entry_tips?: Record<string, unknown> | null;
  visa_free_days?: number | null;
  stay_months?: number | null;
  renewable?: boolean | null;
  key_docs?: string[] | null;
  visa_fee_usd?: number | null;
  tax_note?: string | null;
  double_tax_treaty_with_kr?: boolean | null;
  visa_notes?: string[] | null;
  reading_text?: string | null;
}

export type TarotStage =
  | "loading"
  | "selecting"
  | "revealed"
  | "reading"
  | "comparing";

export interface TarotSession {
  session_id: string;
  selectedIndices: number[];
  revealedCities: CityData[];
  readingCityIndex: number | null;
  readingMarkdown: string | null;
  stage: TarotStage;
}

export const TAROT_SESSION_KEY = "tarot_session";
