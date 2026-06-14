import test from "node:test";
import assert from "node:assert/strict";
import { enrichDestinations } from "./destination-enrich.ts";

test("passes through destination fields unchanged", () => {
  const list = [{ id: "DPS", city: "Bali", country_id: "ID", vibe: "휴양" }];
  const out = enrichDestinations(list, {});
  assert.equal(out[0].id, "DPS");
  assert.equal(out[0].city, "Bali");
  assert.equal(out[0].vibe, "휴양");
});

test("adds city_description from descriptions map by ID_SLUG key", () => {
  const list = [{ id: "DPS", city: "Bali", country_id: "ID" }];
  const descriptions = { ID_BALI: "발리 설명" };
  const out = enrichDestinations(list, descriptions);
  assert.equal(out[0].city_description, "발리 설명");
});

test("city_description is null when no match", () => {
  const out = enrichDestinations([{ id: "X", city: "Nowhere", country_id: "ZZ" }], {});
  assert.equal(out[0].city_description, null);
});

test("returns empty array for empty input", () => {
  assert.deepEqual(enrichDestinations([], {}), []);
  assert.deepEqual(enrichDestinations(undefined, {}), []);
});
