/**
 * 공동 플래너(plan-items) 표시용 순수 헬퍼.
 * 정렬·Day 그룹핑·카테고리·편집권한 — UI와 분리해 단위 테스트로 검증한다.
 * 백엔드 계약: day 1~60, place 필수, category 6종 고정.
 */

export const PLAN_CATEGORIES = [
  "관광",
  "식사",
  "이동",
  "숙소",
  "액티비티",
  "기타",
] as const;

export type PlanCategory = (typeof PLAN_CATEGORIES)[number];

const CATEGORY_EMOJI: Record<PlanCategory, string> = {
  관광: "📸",
  식사: "🍽️",
  이동: "🚌",
  숙소: "🏨",
  액티비티: "🏄",
  기타: "📌",
};

export interface PlanItem {
  id: number;
  trip_id?: string;
  day: number;
  time?: string | null;
  place: string;
  category: string;
  memo?: string | null;
  added_by: string;
  created_at?: string | null;
}

export interface DayGroup {
  day: number;
  items: PlanItem[];
}

export function isValidCategory(value: string): value is PlanCategory {
  return (PLAN_CATEGORIES as readonly string[]).includes(value);
}

export function categoryEmoji(category: string): string {
  return isValidCategory(category) ? CATEGORY_EMOJI[category] : CATEGORY_EMOJI.기타;
}

/** day → time(빈 값은 맨 뒤) → id 순 정렬. 원본 배열은 변경하지 않는다. */
export function sortPlanItems(items: PlanItem[]): PlanItem[] {
  return [...items].sort((a, b) => {
    if (a.day !== b.day) return a.day - b.day;
    const at = a.time?.trim() || "";
    const bt = b.time?.trim() || "";
    if (at !== bt) {
      if (at === "") return 1; // 시간 없는 항목은 같은 day 안에서 뒤로
      if (bt === "") return -1;
      return at < bt ? -1 : 1;
    }
    return a.id - b.id;
  });
}

/** 정렬된 항목을 Day별로 묶는다(day 오름차순). 빈 입력 → 빈 배열. */
export function groupPlanItemsByDay(items: PlanItem[]): DayGroup[] {
  const sorted = sortPlanItems(items);
  const groups: DayGroup[] = [];
  let current: DayGroup | null = null;
  for (const item of sorted) {
    if (!current || current.day !== item.day) {
      current = { day: item.day, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  }
  return groups;
}

/** 수정/삭제 권한: 작성자(added_by) 또는 Trip owner. */
export function canEditPlanItem(
  item: Pick<PlanItem, "added_by">,
  currentUserId: string | null | undefined,
  ownerUserId: string | null | undefined
): boolean {
  if (!currentUserId) return false;
  return item.added_by === currentUserId || ownerUserId === currentUserId;
}

export interface PlanItemDraft {
  day?: number | string;
  time?: string;
  place?: string;
  category?: string;
  memo?: string;
}

export interface NormalizedPlanItemDraft {
  day: number;
  time: string;
  place: string;
  category: PlanCategory;
  memo: string;
}

/**
 * 입력 폼 draft → 백엔드 전송 가능한 정규화 결과 또는 에러.
 * place 필수, day 1~60, category 6종.
 */
export function validatePlanItemDraft(
  draft: PlanItemDraft
): { ok: true; value: NormalizedPlanItemDraft } | { ok: false; error: string } {
  const place = (draft.place ?? "").trim();
  if (place.length === 0) return { ok: false, error: "장소를 입력해주세요." };

  const day = Number(draft.day);
  if (!Number.isInteger(day) || day < 1 || day > 60) {
    return { ok: false, error: "일자는 1~60 사이여야 합니다." };
  }

  const category = draft.category ?? "기타";
  if (!isValidCategory(category)) {
    return { ok: false, error: "올바른 카테고리를 선택해주세요." };
  }

  return {
    ok: true,
    value: {
      day,
      time: (draft.time ?? "").trim(),
      place,
      category,
      memo: (draft.memo ?? "").trim(),
    },
  };
}
