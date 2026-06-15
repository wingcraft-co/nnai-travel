import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// POST /api/trips/{trip_id}/invites → 초대 링크 발급 (멤버만)
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string }> }
) {
  const { trip_id } = await ctx.params;
  return proxyToBackend(`/api/trips/${encodeURIComponent(trip_id)}/invites`, {
    method: "POST",
    cookie: req.headers.get("cookie") ?? "",
    body: {},
  });
}
