import { NextRequest, NextResponse } from "next/server";
import cityDescriptions from "@/data/city_descriptions.json";
import { enrichDestinations } from "@/lib/destination-enrich";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const cookie = req.headers.get("cookie") ?? "";

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api.nnai.app";
  const response = await fetch(`${apiBase}/api/travel/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    return NextResponse.json(
      { error: "여행 추천 API 호출 실패" },
      { status: response.status }
    );
  }

  const data = await response.json();
  data.top_destinations = enrichDestinations(
    data.top_destinations,
    cityDescriptions as Record<string, string>
  );
  return NextResponse.json(data);
}
