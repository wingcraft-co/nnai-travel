"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { fetchAuthMe, goToGoogleLogin } from "@/lib/auth-session";
import { joinTrip, TripsApiError } from "@/lib/trips-api";

type Stage = "loading" | "anon" | "no_token" | "invalid" | "expired" | "error";

export default function TripJoinPage() {
  const router = useRouter();
  const locale = useLocale();
  const isEn = locale === "en";

  const [stage, setStage] = useState<Stage>("loading");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStage("no_token");
      return;
    }

    (async () => {
      const me = await fetchAuthMe();
      if (!me.logged_in) {
        setStage("anon");
        return;
      }
      try {
        const trip = await joinTrip(token);
        router.replace(`/trips/${trip.id}`);
      } catch (err) {
        if (err instanceof TripsApiError) {
          if (err.status === 400) return setStage("invalid");
          if (err.status === 410) return setStage("expired");
        }
        setStage("error");
      }
    })();
  }, [router]);

  return (
    <div className="dark flex min-h-0 w-full min-w-0 flex-1 flex-col items-center justify-center gap-4 bg-background px-4 text-foreground">
      {stage === "loading" && (
        <p className="animate-pulse text-sm text-muted-foreground">
          {isEn ? "Joining the trip..." : "여행에 합류하는 중..."}
        </p>
      )}
      {stage === "anon" && (
        <>
          <p className="text-sm text-muted-foreground">
            {isEn ? "Sign in to join this trip." : "이 여행에 합류하려면 로그인하세요."}
          </p>
          <button type="button" onClick={() => goToGoogleLogin()} className="cursor-pointer bg-primary px-5 py-2 text-sm font-medium text-primary-foreground">
            {isEn ? "Continue with Google" : "Google로 계속하기"}
          </button>
        </>
      )}
      {stage === "no_token" && (
        <p className="text-sm text-muted-foreground">
          {isEn ? "Invalid invite link." : "유효하지 않은 초대 링크예요."}
        </p>
      )}
      {stage === "invalid" && (
        <p className="text-sm text-muted-foreground">
          {isEn ? "This invite link is not valid." : "유효하지 않은 초대 링크예요."}
        </p>
      )}
      {stage === "expired" && (
        <p className="text-sm text-muted-foreground">
          {isEn ? "This invite has expired." : "초대 링크가 만료되었어요."}
        </p>
      )}
      {stage === "error" && (
        <p className="text-sm text-red-500/80">
          {isEn ? "Could not join the trip. Please try again." : "여행 합류에 실패했어요. 다시 시도해주세요."}
        </p>
      )}
    </div>
  );
}
