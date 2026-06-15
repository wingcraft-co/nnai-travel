import type { CityData } from "@/components/tarot/types";
import type { PlanItem } from "@/lib/trip-plan";

/** 클라이언트 → 같은 출처 BFF(/api/trips/*) 호출 래퍼. 쿠키는 자동 전송. */

export interface TripMember {
  user_id: string;
  role: "owner" | "member";
  joined_at?: string | null;
}

export interface Trip {
  id: string;
  owner_user_id: string;
  title: string;
  destination: CityData | Record<string, unknown>;
  start_date?: string | null;
  end_date?: string | null;
  created_at?: string | null;
  members?: TripMember[];
}

export interface InviteResponse {
  token: string;
  invite_url: string;
  expires_at?: string | null;
}

export class TripsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "TripsApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail =
      (data as { detail?: string; error?: string })?.detail ??
      (data as { error?: string })?.error ??
      `요청 실패 (${res.status})`;
    throw new TripsApiError(res.status, detail);
  }
  return data as T;
}

export function createTrip(input: {
  title?: string;
  destination: CityData | Record<string, unknown>;
  start_date?: string | null;
  end_date?: string | null;
}): Promise<Trip> {
  return request<Trip>("/api/trips", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTrips(): Promise<{ trips: Trip[] }> {
  return request<{ trips: Trip[] }>("/api/trips");
}

export function getTrip(tripId: string): Promise<Trip> {
  return request<Trip>(`/api/trips/${encodeURIComponent(tripId)}`);
}

export function createInvite(tripId: string): Promise<InviteResponse> {
  return request<InviteResponse>(
    `/api/trips/${encodeURIComponent(tripId)}/invites`,
    { method: "POST", body: "{}" }
  );
}

export function joinTrip(token: string): Promise<Trip> {
  return request<Trip>("/api/trips/join", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function listPlanItems(tripId: string): Promise<{ plan_items: PlanItem[] }> {
  return request<{ plan_items: PlanItem[] }>(
    `/api/trips/${encodeURIComponent(tripId)}/plan-items`
  );
}

export function addPlanItem(
  tripId: string,
  item: { day: number; time: string; place: string; category: string; memo: string }
): Promise<PlanItem> {
  return request<PlanItem>(
    `/api/trips/${encodeURIComponent(tripId)}/plan-items`,
    { method: "POST", body: JSON.stringify(item) }
  );
}

export function updatePlanItem(
  tripId: string,
  itemId: number,
  item: { day: number; time: string; place: string; category: string; memo: string }
): Promise<PlanItem> {
  return request<PlanItem>(
    `/api/trips/${encodeURIComponent(tripId)}/plan-items/${itemId}`,
    { method: "PUT", body: JSON.stringify(item) }
  );
}

export function deletePlanItem(
  tripId: string,
  itemId: number
): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(
    `/api/trips/${encodeURIComponent(tripId)}/plan-items/${itemId}`,
    { method: "DELETE" }
  );
}
