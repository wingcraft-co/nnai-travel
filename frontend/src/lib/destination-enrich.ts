type Destination = Record<string, unknown> & { city?: string; country_id?: string };

/** city 이름 → CITY_SLUG (대문자, 공백→_, 괄호 제거). recommend BFF의 기존 규칙과 동일. */
function citySlug(city: string): string {
  return city.toUpperCase().replace(/ /g, "_").replace(/[()]/g, "");
}

/**
 * 여행 추천 top_destinations에 city_description을 보강한다.
 * 백엔드가 이미 여행 필드(vibe/best_months/activities 등)를 채워 반환하므로 통과시키고,
 * 카드 본문용 설명만 destinations 설명 맵에서 ID_SLUG 키로 조회해 붙인다.
 */
export function enrichDestinations(
  list: Destination[] | undefined,
  descriptions: Record<string, string>
): Destination[] {
  if (!list) return [];
  return list.map((d) => {
    const city = (d.city as string) ?? "";
    const countryId = (d.country_id as string) ?? "";
    const key = `${countryId}_${citySlug(city)}`;
    return { ...d, city_description: descriptions[key] ?? null };
  });
}
