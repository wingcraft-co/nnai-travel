import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/trips-proxy";

// GET /api/trips → 내가 멤버인 Trip 목록
export async function GET(req: NextRequest) {
  return proxyToBackend("/api/trips", {
    method: "GET",
    cookie: req.headers.get("cookie") ?? "",
  });
}

// POST /api/trips → Trip 생성
export async function POST(req: NextRequest) {
  const body = await req.json();
  return proxyToBackend("/api/trips", {
    method: "POST",
    cookie: req.headers.get("cookie") ?? "",
    body,
  });
}
