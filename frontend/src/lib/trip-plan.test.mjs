import test from "node:test";
import assert from "node:assert/strict";
import {
  PLAN_CATEGORIES,
  isValidCategory,
  categoryEmoji,
  sortPlanItems,
  groupPlanItemsByDay,
  canEditPlanItem,
  validatePlanItemDraft,
} from "./trip-plan.ts";

const mk = (over) => ({
  id: 1,
  day: 1,
  time: "09:00",
  place: "장소",
  category: "관광",
  added_by: "u1",
  ...over,
});

test("category set is the fixed backend contract", () => {
  assert.deepEqual([...PLAN_CATEGORIES], ["관광", "식사", "이동", "숙소", "액티비티", "기타"]);
  assert.ok(isValidCategory("식사"));
  assert.ok(!isValidCategory("쇼핑"));
});

test("categoryEmoji falls back to 기타 for unknown", () => {
  assert.equal(categoryEmoji("식사"), "🍽️");
  assert.equal(categoryEmoji("존재안함"), "📌");
});

test("sorts by day, then time, then id; empty time goes last within a day", () => {
  const items = [
    mk({ id: 3, day: 2, time: "08:00" }),
    mk({ id: 1, day: 1, time: "" }),
    mk({ id: 2, day: 1, time: "10:00" }),
    mk({ id: 4, day: 1, time: "10:00" }),
  ];
  const sorted = sortPlanItems(items);
  assert.deepEqual(sorted.map((i) => i.id), [2, 4, 1, 3]);
});

test("sortPlanItems does not mutate input", () => {
  const items = [mk({ id: 2, day: 2 }), mk({ id: 1, day: 1 })];
  const before = items.map((i) => i.id);
  sortPlanItems(items);
  assert.deepEqual(items.map((i) => i.id), before);
});

test("groups items by day in ascending order", () => {
  const items = [
    mk({ id: 1, day: 2, time: "09:00" }),
    mk({ id: 2, day: 1, time: "09:00" }),
    mk({ id: 3, day: 2, time: "11:00" }),
  ];
  const groups = groupPlanItemsByDay(items);
  assert.deepEqual(groups.map((g) => g.day), [1, 2]);
  assert.deepEqual(groups[1].items.map((i) => i.id), [1, 3]);
});

test("empty input groups to empty array", () => {
  assert.deepEqual(groupPlanItemsByDay([]), []);
});

test("edit permission: author or owner only", () => {
  const item = mk({ added_by: "author" });
  assert.ok(canEditPlanItem(item, "author", "owner"));   // 작성자
  assert.ok(canEditPlanItem(item, "owner", "owner"));    // owner
  assert.ok(!canEditPlanItem(item, "stranger", "owner")); // 비작성자·비owner
  assert.ok(!canEditPlanItem(item, null, "owner"));       // 미로그인
});

test("draft validation rejects empty place", () => {
  const r = validatePlanItemDraft({ place: "  ", day: 1, category: "관광" });
  assert.equal(r.ok, false);
});

test("draft validation rejects out-of-range day", () => {
  assert.equal(validatePlanItemDraft({ place: "우붓", day: 0 }).ok, false);
  assert.equal(validatePlanItemDraft({ place: "우붓", day: 61 }).ok, false);
  assert.equal(validatePlanItemDraft({ place: "우붓", day: 1.5 }).ok, false);
});

test("draft validation rejects bad category", () => {
  const r = validatePlanItemDraft({ place: "우붓", day: 1, category: "쇼핑" });
  assert.equal(r.ok, false);
});

test("draft validation normalizes and trims a valid draft", () => {
  const r = validatePlanItemDraft({
    day: "2",
    time: " 09:00 ",
    place: "  우붓  ",
    category: "관광",
    memo: "  아침  ",
  });
  assert.equal(r.ok, true);
  assert.deepEqual(r.value, {
    day: 2,
    time: "09:00",
    place: "우붓",
    category: "관광",
    memo: "아침",
  });
});

test("draft validation defaults missing category to 기타", () => {
  const r = validatePlanItemDraft({ place: "공항", day: 1 });
  assert.equal(r.ok, true);
  assert.equal(r.value.category, "기타");
});
