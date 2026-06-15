import test from "node:test";
import assert from "node:assert/strict";
import { buildItineraryRequest } from "./itinerary-request.ts";

const baseDestination = {
  id: "DPS",
  city: "Bali",
  city_kr: "발리",
  country: "Indonesia",
  country_id: "ID",
  vibe: "휴양",
  best_months: [5, 6, 7, 8, 9],
  activities: ["해변", "서핑"],
  must_see: ["우붓"],
  est_cost_krw: 1500000,
  score: 8.4,
};

const baseProfile = {
  language: "한국어",
  nights: 4,
  travel_month: 7,
  interests: ["휴양"],
  persona: "힐링 휴양러",
  preferred_regions: ["동남아"],
  companions: { type: "커플(허니문)", headcount: 2, pace: "휴양 위주" },
  top_n: 5,
};

test("snapshots the destination fields the planner needs", () => {
  const req = buildItineraryRequest(baseDestination, baseProfile, "ko");
  assert.deepEqual(req.destination, {
    city: "Bali",
    city_kr: "발리",
    country_id: "ID",
    vibe: "휴양",
    best_months: [5, 6, 7, 8, 9],
    activities: ["해변", "서핑"],
    must_see: ["우붓"],
    est_cost_krw: 1500000,
  });
});

test("carries only the itinerary-relevant profile fields", () => {
  const req = buildItineraryRequest(baseDestination, baseProfile, "ko");
  assert.deepEqual(req.travel_profile, {
    language: "한국어",
    nights: 4,
    travel_month: 7,
    interests: ["휴양"],
    persona: "힐링 휴양러",
    companions: { type: "커플(허니문)", pace: "휴양 위주" },
  });
});

test("falls back to locale for language when profile omits it", () => {
  const en = buildItineraryRequest(baseDestination, { ...baseProfile, language: undefined }, "en");
  assert.equal(en.travel_profile.language, "English");
  const ko = buildItineraryRequest(baseDestination, { ...baseProfile, language: "" }, "ko");
  assert.equal(ko.travel_profile.language, "한국어");
});

test("clamps nights and rejects out-of-range months", () => {
  const req = buildItineraryRequest(
    baseDestination,
    { ...baseProfile, nights: 999, travel_month: 13 },
    "ko"
  );
  assert.equal(req.travel_profile.nights, 60);
  assert.equal(req.travel_profile.travel_month, null);
});

test("tolerates a missing profile entirely", () => {
  const req = buildItineraryRequest(baseDestination, null, "ko");
  assert.equal(req.travel_profile.language, "한국어");
  assert.equal(req.travel_profile.nights, 0);
  assert.equal(req.travel_profile.travel_month, null);
  assert.deepEqual(req.travel_profile.interests, []);
  assert.equal(req.travel_profile.persona, "");
  assert.equal(req.travel_profile.companions.type, "혼자 (솔로)");
});

test("normalizes missing destination arrays to empty arrays", () => {
  const sparse = {
    city: "Nowhere",
    city_kr: "노웨어",
    country_id: "XX",
    score: 1,
  };
  const req = buildItineraryRequest(sparse, baseProfile, "ko");
  assert.deepEqual(req.destination.best_months, []);
  assert.deepEqual(req.destination.activities, []);
  assert.deepEqual(req.destination.must_see, []);
  assert.equal(req.destination.vibe, null);
  assert.equal(req.destination.est_cost_krw, null);
});
