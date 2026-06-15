"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { MapPin, Plus, Users } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import { fetchAuthMe, goToGoogleLogin } from "@/lib/auth-session";
import { listTrips, type Trip } from "@/lib/trips-api";

type Stage = "loading" | "anon" | "ready" | "error";

function destinationCity(trip: Trip, isEn: boolean): string {
  const d = trip.destination as { city?: string; city_kr?: string };
  if (isEn) return d?.city ?? "";
  return d?.city_kr || d?.city || "";
}

function dateRange(trip: Trip): string {
  if (trip.start_date && trip.end_date) return `${trip.start_date} ~ ${trip.end_date}`;
  return trip.start_date || "";
}

export default function TripsListPage() {
  const router = useRouter();
  const locale = useLocale();
  const isEn = locale === "en";

  const [stage, setStage] = useState<Stage>("loading");
  const [trips, setTrips] = useState<Trip[]>([]);

  const load = useCallback(async () => {
    setStage("loading");
    const me = await fetchAuthMe();
    if (!me.logged_in) {
      setStage("anon");
      return;
    }
    try {
      const data = await listTrips();
      setTrips(data.trips ?? []);
      setStage("ready");
    } catch {
      setStage("error");
    }
  }, []);

  useEffect(() => {
    // load() sets a transient "loading" state before fetching — intentional.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return (
    <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col bg-background text-foreground">
      <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-5 py-8">
        <h1 className="mb-6 font-serif text-2xl font-bold text-foreground">
          {isEn ? "My trips" : "내 여행"}
        </h1>

        {stage === "loading" && (
          <p className="animate-pulse text-sm text-muted-foreground">
            {isEn ? "Loading..." : "불러오는 중..."}
          </p>
        )}

        {stage === "anon" && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted-foreground">
              {isEn ? "Sign in to see your saved trips." : "저장한 여행을 보려면 로그인하세요."}
            </p>
            <button
              type="button"
              onClick={() => goToGoogleLogin()}
              className="cursor-pointer bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
            >
              {isEn ? "Continue with Google" : "Google로 계속하기"}
            </button>
          </div>
        )}

        {stage === "error" && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-red-500/80">
              {isEn ? "Could not load trips." : "여행을 불러오지 못했어요."}
            </p>
            <button
              type="button"
              onClick={() => void load()}
              className="cursor-pointer bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
            >
              {isEn ? "Retry" : "다시 시도"}
            </button>
          </div>
        )}

        {stage === "ready" && trips.length === 0 && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-muted-foreground">
              {isEn ? "No saved trips yet." : "아직 저장한 여행이 없어요."}
            </p>
            <button
              type="button"
              onClick={() => router.push("/onboarding/form")}
              className="flex cursor-pointer items-center gap-1 bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
            >
              <Plus className="h-4 w-4" />
              {isEn ? "Find a destination" : "여행지 찾기"}
            </button>
          </div>
        )}

        {stage === "ready" && trips.length > 0 && (
          <ul className="flex flex-col gap-3">
            {trips.map((trip) => (
              <li key={trip.id}>
                <button
                  type="button"
                  onClick={() => router.push(`/trips/${trip.id}`)}
                  className="flex w-full cursor-pointer flex-col gap-1 border border-border bg-card px-4 py-3 text-left transition-colors hover:border-primary"
                >
                  <span className="font-serif text-base font-bold text-foreground">
                    {trip.title || destinationCity(trip, isEn) || (isEn ? "Untitled trip" : "이름 없는 여행")}
                  </span>
                  <span className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {destinationCity(trip, isEn)}
                    </span>
                    {dateRange(trip) && <span>{dateRange(trip)}</span>}
                    {trip.members && (
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" />
                        {trip.members.length}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
