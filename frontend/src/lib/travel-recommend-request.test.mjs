import test from "node:test";
import assert from "node:assert/strict";
import { buildTravelRecommendRequest } from "./travel-recommend-request.ts";

const baseForm = {
  travel_month: 7,
  nights: 4,
  budget_krw: 2000000,
  interests: ["휴양", "자연"],
  persona: "힐링 휴양러",
  preferred_regions: ["동남아"],
  companion_type: "커플(허니문)",
  headcount: 2,
  companion_ages: ["성인"],
  accessibility: ["없음"],
  pace: "휴양 위주",
};

test("maps form to travel recommend request", () => {
  const req = buildTravelRecommendRequest(baseForm, "ko");
  assert.equal(req.travel_month, 7);
  assert.equal(req.nights, 4);
  assert.equal(req.budget_krw, 2000000);
  assert.deepEqual(req.interests, ["휴양", "자연"]);
  assert.equal(req.persona, "힐링 휴양러");
  assert.deepEqual(req.preferred_regions, ["동남아"]);
  assert.equal(req.top_n, 5);
  assert.equal(req.language, "한국어");
});

test("nests companions object", () => {
  const req = buildTravelRecommendRequest(baseForm, "ko");
  assert.equal(req.companions.type, "커플(허니문)");
  assert.equal(req.companions.headcount, 2);
  assert.deepEqual(req.companions.ages, ["성인"]);
  assert.deepEqual(req.companions.accessibility, ["없음"]);
  assert.equal(req.companions.pace, "휴양 위주");
});

test("language follows locale", () => {
  assert.equal(buildTravelRecommendRequest(baseForm, "en").language, "English");
});

test("clamps month to 1..12 or null", () => {
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: 0 }, "ko").travel_month, null);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: 13 }, "ko").travel_month, null);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: "" }, "ko").travel_month, null);
});

test("clamps nights to 0..60", () => {
  assert.equal(buildTravelRecommendRequest({ ...baseForm, nights: 999 }, "ko").nights, 60);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, nights: -1 }, "ko").nights, 0);
});

test("defaults empty arrays when missing", () => {
  const req = buildTravelRecommendRequest({}, "ko");
  assert.deepEqual(req.interests, []);
  assert.deepEqual(req.preferred_regions, []);
  assert.equal(req.companions.headcount, 1);
});
