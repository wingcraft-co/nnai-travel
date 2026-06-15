import { NextRequest, NextResponse } from "next/server";

/**
 * BFF: 선택 여행지 + 여행 프로필 → 백엔드 `/api/travel/itinerary` 프록시.
 * 백엔드가 Gemini로 N박M일 일정을 생성해 `{ markdown, itinerary }`를 반환한다.
 */
export async function POST(req: NextRequest) {
  const body = await req.json();
  const cookie = req.headers.get("cookie") ?? "";

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api.nnai.app";
  const response = await fetch(`${apiBase}/api/travel/itinerary`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    return NextResponse.json(
      { error: "여행 일정 생성 API 호출 실패" },
      { status: response.status }
    );
  }

  const data = await response.json();
  return NextResponse.json(data);
}
