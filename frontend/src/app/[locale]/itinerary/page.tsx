"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { ChevronLeft, Bookmark } from "lucide-react";
import { useRouter } from "@/i18n/navigation";
import type { CityData } from "@/components/tarot/types";
import {
  buildItineraryRequest,
  type TravelProfileLike,
} from "@/lib/itinerary-request";
import {
  parseItineraryMarkdown,
  type ItineraryNode,
} from "@/lib/itinerary-markdown";
import { fetchAuthMe, goToGoogleLogin } from "@/lib/auth-session";
import { createTrip, TripsApiError } from "@/lib/trips-api";

const SELECTED_DESTINATION_KEY = "selected_destination";
const TRAVEL_PROFILE_KEY = "travel_profile";

type Stage = "loading" | "done" | "error";

function readSelectedDestination(): CityData | null {
  try {
    const raw = sessionStorage.getItem(SELECTED_DESTINATION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CityData;
    return parsed && typeof parsed.city === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function readTravelProfile(): TravelProfileLike | null {
  try {
    const raw = localStorage.getItem(TRAVEL_PROFILE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as TravelProfileLike;
  } catch {
    return null;
  }
}

function MarkdownNodes({ nodes }: { nodes: ItineraryNode[] }) {
  return (
    <div className="space-y-3">
      {nodes.map((node, index) => {
        switch (node.type) {
          case "h1":
            return (
              <h1 key={index} className="font-serif text-2xl font-bold text-foreground">
                {node.text}
              </h1>
            );
          case "h2":
            return (
              <h2 key={index} className="pt-5 font-serif text-xl font-bold text-foreground">
                {node.text}
              </h2>
            );
          case "h3":
            return (
              <h3 key={index} className="pt-3 font-serif text-lg font-bold text-primary">
                {node.text}
              </h3>
            );
          case "li":
            return (
              <p key={index} className="pl-3 text-sm leading-7 text-foreground/90">
                • {node.text}
              </p>
            );
          default:
            return (
              <p key={index} className="text-sm leading-7 text-foreground/90">
                {node.text}
              </p>
            );
        }
      })}
    </div>
  );
}

export default function ItineraryPage() {
  const router = useRouter();
  const locale = useLocale();
  const isEn = locale === "en";

  const [stage, setStage] = useState<Stage>("loading");
  const [destination, setDestination] = useState<CityData | null>(null);
  const [nodes, setNodes] = useState<ItineraryNode[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSaveTrip = useCallback(async () => {
    if (!destination) return;
    setSaving(true);
    setSaveError(null);
    const me = await fetchAuthMe();
    if (!me.logged_in) {
      goToGoogleLogin();
      return;
    }
    try {
      const title = destination.city_kr || destination.city;
      const trip = await createTrip({ title, destination });
      router.push(`/trips/${trip.id}`);
    } catch (err) {
      setSaveError(
        err instanceof TripsApiError
          ? err.message
          : isEn
            ? "Could not save the trip."
            : "여행 저장에 실패했어요."
      );
      setSaving(false);
    }
  }, [destination, router, isEn]);

  const generate = useCallback(
    async (dest: CityData, profile: TravelProfileLike | null) => {
      setStage("loading");
      setErrorMessage(null);

      try {
        const requestBody = buildItineraryRequest(dest, profile, locale);
        const res = await fetch("/api/itinerary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        });
        if (!res.ok) throw new Error(`itinerary error: ${res.status}`);

        const data = (await res.json()) as { markdown?: string };
        const markdown = data.markdown ?? "";
        const parsed = parseItineraryMarkdown(markdown);
        if (parsed.length === 0) {
          throw new Error("empty itinerary");
        }
        setNodes(parsed);
        setStage("done");
      } catch {
        setErrorMessage(
          isEn
            ? "The itinerary service is unstable.\nPlease try again in a moment."
            : "일정 생성 서비스가 불안정합니다.\n잠시 후 다시 시도해주세요."
        );
        setStage("error");
      }
    },
    [locale, isEn]
  );

  useEffect(() => {
    const dest = readSelectedDestination();
    if (!dest) {
      router.replace("/result");
      return;
    }
    setDestination(dest);
    void generate(dest, readTravelProfile());
  }, [router, generate]);

  const title = destination
    ? isEn
      ? `${destination.city} itinerary`
      : `${destination.city_kr || destination.city} 여행 일정`
    : isEn
      ? "Itinerary"
      : "여행 일정";

  return (
    <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col bg-background text-foreground">
      {/* Header */}
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <button
          type="button"
          onClick={() => router.push("/result")}
          className="flex cursor-pointer items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          {isEn ? "Back to destinations" : "추천 여행지로"}
        </button>
      </div>

      {/* Loading */}
      {stage === "loading" && (
        <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-3 px-4">
          <p className="animate-pulse text-sm text-muted-foreground">
            {isEn
              ? "Crafting your day-by-day itinerary..."
              : "맞춤 여행 일정을 짜고 있어요..."}
          </p>
        </div>
      )}

      {/* Error */}
      {stage === "error" && (
        <div className="flex min-h-full flex-1 flex-col items-center justify-center gap-4 px-4">
          <p className="max-w-xs whitespace-pre-line text-center text-sm leading-6 text-red-500/80">
            {errorMessage}
          </p>
          <button
            type="button"
            onClick={() => {
              if (destination) void generate(destination, readTravelProfile());
            }}
            className="cursor-pointer bg-primary px-6 py-2 text-sm font-medium text-primary-foreground"
          >
            {isEn ? "Try again" : "다시 시도"}
          </button>
        </div>
      )}

      {/* Done — 마크다운이 자체 h1으로 시작하면 페이지 제목 h1은 생략(중복 방지) */}
      {stage === "done" && (
        <div className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-5 py-8">
          <div className="mb-5 flex items-center justify-between gap-3">
            {nodes[0]?.type !== "h1" ? (
              <h1 className="font-serif text-2xl font-bold text-foreground">{title}</h1>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={() => void handleSaveTrip()}
              disabled={saving}
              className="flex shrink-0 cursor-pointer items-center gap-1.5 bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              <Bookmark className="h-4 w-4" />
              {saving ? (isEn ? "Saving..." : "저장 중...") : isEn ? "Save as trip" : "Trip으로 저장"}
            </button>
          </div>
          {saveError && <p className="mb-4 text-sm text-red-500/80">{saveError}</p>}
          <MarkdownNodes nodes={nodes} />
        </div>
      )}
    </div>
  );
}
