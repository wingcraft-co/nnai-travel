import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// PUT /api/trips/{trip_id}/plan-items/{item_id} → 항목 수정 (작성자/owner)
export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string; item_id: string }> }
) {
  const { trip_id, item_id } = await ctx.params;
  const body = await req.json();
  return proxyToBackend(
    `/api/trips/${encodeURIComponent(trip_id)}/plan-items/${encodeURIComponent(item_id)}`,
    { method: "PUT", cookie: req.headers.get("cookie") ?? "", body }
  );
}

// DELETE /api/trips/{trip_id}/plan-items/{item_id} → 항목 삭제 (작성자/owner)
export async function DELETE(
  req: NextRequest,
  ctx: { params: Promise<{ trip_id: string; item_id: string }> }
) {
  const { trip_id, item_id } = await ctx.params;
  return proxyToBackend(
    `/api/trips/${encodeURIComponent(trip_id)}/plan-items/${encodeURIComponent(item_id)}`,
    { method: "DELETE", cookie: req.headers.get("cookie") ?? "" }
  );
}
