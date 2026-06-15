/**
 * 일정(itinerary) 마크다운을 렌더링 가능한 노드 배열로 변환하는 순수 헬퍼.
 * UI 컴포넌트와 분리해 단위 테스트로 검증한다.
 */

export type ItineraryNodeType = "h1" | "h2" | "h3" | "li" | "p";

export interface ItineraryNode {
  type: ItineraryNodeType;
  /** heading/표시 텍스트 (목록 마커 `- `, heading `#` 제거됨) */
  text: string;
}

/**
 * 마크다운 문자열 → 노드 배열.
 * - 빈 줄은 제거.
 * - `#`/`##`/`###` heading, `-`/`*` 목록, 그 외는 문단(p).
 * - heading 4단계 이상(`####`)은 h3로 흡수.
 */
export function parseItineraryMarkdown(markdown: string): ItineraryNode[] {
  if (typeof markdown !== "string") return [];

  const nodes: ItineraryNode[] = [];
  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.trim();
    if (line.length === 0) continue;

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      if (text.length === 0) continue;
      const type: ItineraryNodeType = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
      nodes.push({ type, text });
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const text = line.replace(/^[-*]\s+/, "").trim();
      if (text.length === 0) continue;
      nodes.push({ type: "li", text });
      continue;
    }

    nodes.push({ type: "p", text: line });
  }

  return nodes;
}
