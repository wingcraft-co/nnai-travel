import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// POST /api/trips/join → 초대 토큰으로 합류 (멱등)
export async function POST(req: NextRequest) {
  const body = await req.json();
  return proxyToBackend("/api/trips/join", {
    method: "POST",
    cookie: req.headers.get("cookie") ?? "",
    body,
  });
}
