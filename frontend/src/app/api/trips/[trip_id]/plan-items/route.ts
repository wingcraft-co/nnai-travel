import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// GET /api/trips/{trip_id}/plan-items → 계획 항목 목록 (멤버)
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string }> }
) {
  const { trip_id } = await ctx.params;
  return proxyToBackend(`/api/trips/${encodeURIComponent(trip_id)}/plan-items`, {
    method: "GET",
    cookie: req.headers.get("cookie") ?? "",
  });
}

// POST /api/trips/{trip_id}/plan-items → 계획 항목 추가 (멤버)
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string }> }
) {
  const { trip_id } = await ctx.params;
  const body = await req.json();
  return proxyToBackend(`/api/trips/${encodeURIComponent(trip_id)}/plan-items`, {
    method: "POST",
    cookie: req.headers.get("cookie") ?? "",
    body,
  });
}
