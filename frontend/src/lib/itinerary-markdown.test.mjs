import test from "node:test";
import assert from "node:assert/strict";
import { parseItineraryMarkdown } from "./itinerary-markdown.ts";

test("parses headings into typed nodes", () => {
  const nodes = parseItineraryMarkdown("# 발리 4박 5일\n## Day 1\n### 오전");
  assert.deepEqual(nodes, [
    { type: "h1", text: "발리 4박 5일" },
    { type: "h2", text: "Day 1" },
    { type: "h3", text: "오전" },
  ]);
});

test("strips list markers and keeps text", () => {
  const nodes = parseItineraryMarkdown("- 우붓 방문\n* 해변 산책");
  assert.deepEqual(nodes, [
    { type: "li", text: "우붓 방문" },
    { type: "li", text: "해변 산책" },
  ]);
});

test("drops blank lines", () => {
  const nodes = parseItineraryMarkdown("# 제목\n\n\n본문\n   \n끝");
  assert.deepEqual(nodes, [
    { type: "h1", text: "제목" },
    { type: "p", text: "본문" },
    { type: "p", text: "끝" },
  ]);
});

test("absorbs deep headings (#### and beyond) into h3", () => {
  const nodes = parseItineraryMarkdown("#### 세부\n###### 더 세부");
  assert.deepEqual(nodes, [
    { type: "h3", text: "세부" },
    { type: "h3", text: "더 세부" },
  ]);
});

test("treats plain lines as paragraphs", () => {
  const nodes = parseItineraryMarkdown("그냥 한 줄짜리 설명입니다.");
  assert.deepEqual(nodes, [
    { type: "p", text: "그냥 한 줄짜리 설명입니다." },
  ]);
});

test("returns an empty array for empty or non-string input", () => {
  assert.deepEqual(parseItineraryMarkdown(""), []);
  assert.deepEqual(parseItineraryMarkdown("   \n  \n"), []);
  assert.deepEqual(parseItineraryMarkdown(null), []);
  assert.deepEqual(parseItineraryMarkdown(undefined), []);
});
