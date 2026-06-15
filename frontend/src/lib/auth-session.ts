const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860";

export interface AuthMe {
  logged_in: boolean;
  uid?: string | null;
  name?: string | null;
}

/** 현재 로그인 상태 조회. 실패 시 logged_in=false. */
export async function fetchAuthMe(): Promise<AuthMe> {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!res.ok) return { logged_in: false };
    const data = await res.json().catch(() => null);
    return {
      logged_in: Boolean(data?.logged_in),
      uid: data?.uid ?? null,
      name: data?.name ?? null,
    };
  } catch {
    return { logged_in: false };
  }
}

/** Google 로그인으로 보내고 현재 페이지로 복귀시킨다. */
export function goToGoogleLogin(returnTo?: string) {
  const ret = returnTo ?? (typeof window !== "undefined" ? window.location.href : "");
  const url = `${API_BASE}/auth/google?return_to=${encodeURIComponent(ret)}`;
  window.location.assign(url);
}
