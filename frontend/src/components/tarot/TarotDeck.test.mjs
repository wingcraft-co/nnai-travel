import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "TarotDeck.tsx"), "utf8");
const cardSource = readFileSync(join(__dirname, "TarotCard.tsx"), "utf8");

test("card open CTA shows a pointer cursor when actionable", () => {
  assert.match(source, /className="[^"]*cursor-pointer[^"]*"/);
  assert.match(source, /disabled:cursor-not-allowed/);
});

test("detail CTA does not repeat the city-specific guide label above the button", () => {
  assert.doesNotMatch(source, /\{city\.city_kr \|\| city\.city\} 상세 페이지 받기/);
});

test("travel plan CTA shows a pointer cursor when actionable", () => {
  assert.match(source, /className="[^"]*cursor-pointer[^"]*"[\s\S]*?>\s*\{isEn \? "Build itinerary" : "이 여행지로 일정 만들기"\}/);
  assert.doesNotMatch(source, />\s*상세 페이지 받기\s*</);
});

test("travel plan CTA stores the selected destination and navigates to the itinerary page", () => {
  assert.match(source, /function handlePlanClick/);
  assert.match(source, /sessionStorage\.setItem\("selected_destination", JSON\.stringify\(city\)\)/);
  assert.match(source, /window\.location\.assign\(`\/\$\{locale\}\/itinerary`\)/);
  // placeholder copy from the pre-wiring phase must be gone
  assert.doesNotMatch(source, /일정 생성 기능은 다음 단계에서 연결됩니다\./);
  assert.doesNotMatch(source, /Loader2/);
  assert.doesNotMatch(source, /animate-spin/);
});

test("destination loading CTA dims the loading copy instead of changing the whole button", () => {
  assert.match(source, /여행지를 열고 있어요\.\.\./);
  assert.match(source, /<span className="animate-pulse">\s*\{isEn\s*\?\s*"Opening destinations\.\.\."\s*:\s*"여행지를 열고 있어요\.\.\."\}\s*<\/span>/);
});

test("lightbox previous, next, and close controls show a pointer cursor", () => {
  assert.match(source, /aria-label=\{isEn \? "Previous" : "이전"\}\s+className="[^"]*cursor-pointer[^"]*"/);
  assert.match(source, /aria-label=\{isEn \? "Next" : "다음"\}\s+className="[^"]*cursor-pointer[^"]*"/);
  assert.match(source, /aria-label=\{isEn \? "Close" : "닫기"\}\s+className="[^"]*cursor-pointer[^"]*"/);
  assert.match(source, /style=\{\{ color: "rgba\(255,255,255,0\.8\)", cursor: "pointer" \}\}/);
});

test("locked card Korean copy uses neutral lock wording", () => {
  assert.match(source, /: `잠겨진 카드 #\$\{orderNumber\}`/);
  assert.match(source, /: "잠금 해제"/);
  assert.doesNotMatch(source, /Pro 전용 카드/);
  assert.doesNotMatch(source, /Pro로 모든 도시 보기/);
});

test("done retry CTA shows a pointer cursor", () => {
  assert.match(source, /retryLabel = "처음부터 다시하기"/);
  assert.match(source, /className="[^"]*cursor-pointer[^"]*"[\s\S]*?>\s*\{retryLabel\}/);
});

test("lightbox card protects long city copy from clipping the CTA", () => {
  assert.match(source, /height: "min\(620px, calc\(100dvh - 128px\)\)"/);
  assert.match(source, /maxHeight: "calc\(100dvh - 128px\)"/);
  assert.match(source, /className="[^"]*overflow-y-auto[^"]*overscroll-contain[^"]*"/);
  assert.match(source, /className="[^"]*sticky[^"]*bottom-0[^"]*"/);
  assert.doesNotMatch(source, /<div className="flex-1" \/>/);
});

test("long visa names wrap inside the card instead of overflowing", () => {
  assert.match(source, /className="[^"]*min-w-0[^"]*max-w-full[^"]*break-words[^"]*"/);
  assert.doesNotMatch(source, /className="inline-flex items-center gap-1 leading-tight w-fit"/);
});

test("visa titles with parentheses start the parenthetical on a new line", () => {
  assert.match(source, /function VisaTitle/);
  assert.match(source, /const parenIndex = title\.indexOf\("\("\)/);
  assert.match(source, /<br aria-hidden="true" \/>/);
  assert.match(source, /<VisaTitle title=\{normalizedVisaType\} \/>/);
});

test("city names with parentheses show the parenthetical on a clean second line", () => {
  assert.match(source, /function CityTitle/);
  assert.match(source, /const detail = title\.slice\(parenIndex\)\.trimStart\(\)/);
  assert.match(source, /<CityTitle title=\{city\.city_kr\} \/>/);
  assert.match(cardSource, /function CityTitle/);
  assert.match(cardSource, /const detail = title\.slice\(parenIndex\)\.trimStart\(\)/);
  assert.match(cardSource, /<CityTitle title=\{cityData\.city_kr\} \/>/);
  assert.doesNotMatch(cardSource, />\s*\{cityData\.city_kr\}\s*</);
});

test("tarot card flag map includes Taiwan for Taipei cards", () => {
  assert.match(cardSource, /import \{ countryFlagEmoji \} from "@\/lib\/country-flag"/);
  assert.match(cardSource, /countryFlagEmoji\(cityData\.country_id\)/);
});

test("google login restores the selected city lightbox after oauth return", () => {
  assert.match(source, /const PENDING_LOGIN_CITY_KEY = "pending_login_city_id"/);
  assert.match(source, /function rememberPendingLoginCity/);
  assert.match(source, /try \{\s*sessionStorage\.setItem\(PENDING_LOGIN_CITY_KEY, key\)/);
  assert.match(source, /function cityRestoreKeys/);
  assert.match(source, /sessionStorage\.getItem\(PENDING_LOGIN_CITY_KEY\)/);
  assert.match(source, /cityRestoreKeys\(c\)\.includes\(pendingId\)/);
  assert.match(source, /sessionStorage\.removeItem\(PENDING_LOGIN_CITY_KEY\)/);
});
