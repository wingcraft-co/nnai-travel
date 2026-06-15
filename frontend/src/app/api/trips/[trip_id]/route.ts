import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// GET /api/trips/{trip_id} → Trip 상세 + 멤버 (멤버만)
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string }> }
) {
  const { trip_id } = await ctx.params;
  return proxyToBackend(`/api/trips/${encodeURIComponent(trip_id)}`, {
    method: "GET",
    cookie: req.headers.get("cookie") ?? "",
  });
}
