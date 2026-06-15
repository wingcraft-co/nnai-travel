import { NextResponse } from "next/server";

/**
 * Trip BFF 공용 프록시: 백엔드로 요청을 전달하고 상태코드+본문을 그대로 통과시킨다.
 * recommend/detail BFF와 달리 401/403/404/410 등 상태코드가 의미를 가지므로 collapse하지 않는다.
 */
function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL || "https://api.nnai.app";
}

export async function proxyToBackend(
  path: string,
  init: { method: string; cookie: string; body?: unknown }
): Promise<NextResponse> {
  let res: Response;
  try {
    res = await fetch(`${apiBase()}${path}`, {
      method: init.method,
      headers: {
        "Content-Type": "application/json",
        ...(init.cookie ? { Cookie: init.cookie } : {}),
      },
      ...(init.body !== undefined ? { body: JSON.stringify(init.body) } : {}),
    });
  } catch {
    return NextResponse.json({ error: "백엔드 연결 실패" }, { status: 502 });
  }

  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text };
  }
  return NextResponse.json(data, { status: res.status });
}
