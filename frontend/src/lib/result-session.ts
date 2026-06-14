export interface ResultSessionCityLike {
  id?: unknown;
  city?: unknown;
  country_id?: unknown;
}

export interface ResultSessionLike {
  session_id?: unknown;
  allCities?: unknown;
  selectedIndices?: unknown;
  revealedCities?: unknown;
  parsedData?: unknown;
  stage?: unknown;
}

export interface NormalizedCompletedResultSession {
  session_id: string;
  allCities: ResultSessionCityLike[];
  selectedIndices: number[];
  revealedCities: ResultSessionCityLike[];
  parsedData: Record<string, unknown> | null;
}

const LEGACY_COMPLETED_CARD_COUNT = 3;
const TRAVEL_COMPLETED_CARD_COUNT = 5;

function isCityLike(value: unknown): value is ResultSessionCityLike {
  return Boolean(value && typeof value === "object" && "city" in value && "country_id" in value);
}

function cityMatchKey(city: ResultSessionCityLike): string | null {
  const id = typeof city.id === "string" && city.id.trim() ? city.id.trim() : null;
  if (id) return `id:${id}`;

  const name = typeof city.city === "string" ? city.city.trim().toLowerCase() : "";
  const country = typeof city.country_id === "string" ? city.country_id.trim().toUpperCase() : "";
  return name && country ? `city:${name}:${country}` : null;
}

function normalizeSelectedIndices(indices: unknown, cityCount: number, expectedCount: number): number[] | null {
  if (!Array.isArray(indices) || indices.length !== expectedCount) return null;

  const normalized = indices.filter(
    (index): index is number =>
      Number.isInteger(index) &&
      index >= 0 &&
      index < cityCount
  );
  if (normalized.length !== expectedCount) return null;
  if (new Set(normalized).size !== normalized.length) return null;

  return normalized;
}

function inferSelectedIndices(
  allCities: ResultSessionCityLike[],
  revealedCities: ResultSessionCityLike[],
  expectedCount: number
): number[] | null {
  const matched = revealedCities.slice(0, expectedCount).map((revealed) => {
    const key = cityMatchKey(revealed);
    if (!key) return -1;
    return allCities.findIndex((candidate) => cityMatchKey(candidate) === key);
  });

  if (matched.length !== expectedCount || matched.some((index) => index < 0)) return null;
  if (new Set(matched).size !== matched.length) return null;

  return matched;
}

export function normalizeCompletedResultSession(
  session: ResultSessionLike | null | undefined
): NormalizedCompletedResultSession | null {
  if (!session || session.stage === "loading" || session.stage === "selecting") return null;

  const revealedCities = Array.isArray(session.revealedCities)
    ? session.revealedCities.filter(isCityLike)
    : [];
  if (revealedCities.length < LEGACY_COMPLETED_CARD_COUNT) return null;

  const allCities = Array.isArray(session.allCities)
    ? session.allCities.filter(isCityLike)
    : [];

  const expectedCount =
    revealedCities.length >= TRAVEL_COMPLETED_CARD_COUNT
      ? TRAVEL_COMPLETED_CARD_COUNT
      : LEGACY_COMPLETED_CARD_COUNT;
  const selectedIndices =
    normalizeSelectedIndices(session.selectedIndices, allCities.length, expectedCount) ??
    inferSelectedIndices(allCities, revealedCities, expectedCount);

  if (!selectedIndices) return null;

  const parsedData =
    session.parsedData && typeof session.parsedData === "object" && !Array.isArray(session.parsedData)
      ? session.parsedData as Record<string, unknown>
      : null;

  return {
    session_id: typeof session.session_id === "string" ? session.session_id : "",
    allCities,
    selectedIndices,
    revealedCities,
    parsedData,
  };
}
