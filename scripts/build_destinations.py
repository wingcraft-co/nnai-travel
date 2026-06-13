"""scripts/build_destinations.py — city_scores.json + editorial CSV → destinations.json.

실행: python -m scripts.build_destinations   (repo 루트에서)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from utils.data_paths import resolve_data_path
from utils.destinations import (
    derive_budget_tier, derive_best_months, derive_vibe, derive_activities,
    derive_peak_season, derive_kid_friendly, derive_romantic, derive_nightlife,
    derive_accessibility, validate_destination,
)

ROOT = Path(__file__).parent.parent
EDITORIAL_CSV = ROOT / "data" / "rawdata" / "destination_editorial.csv"
FRONTEND_COPY = ROOT / "frontend" / "src" / "data" / "destinations.json"

# 인천(ICN) 출발 근사 직항/환승 비행시간 (시간). 큐레이션 상수.
FLIGHT_HOURS_FROM_ICN = {
    "KL": 6.5, "PG": 6.5, "LIS": 14.5, "PTO": 15.0, "CNX": 6.0, "BKK": 6.0,
    "TLL": 11.0, "BCN": 13.5, "MAD": 14.5, "DPS": 7.0, "BLN": 11.0, "TBS": 11.0,
    "SJO": 18.0, "SJD": 14.0, "ATH": 12.0, "HER": 13.0, "MNL": 4.0, "CEU": 5.0,
    "HAN": 5.0, "SGN": 5.5, "VLC": 14.0, "PRG": 11.0, "BUD": 11.0, "AMS": 11.0,
    "VIE": 11.0, "WAW": 10.5, "KRK": 11.0, "MUC": 11.0, "MIL": 12.5, "DBV": 13.0,
    "BEG": 11.5, "SKP": 12.0, "NIC": 12.0, "IST": 11.5, "CEI": 7.0, "USM": 7.0,
    "OSA": 1.5, "TYO": 2.5, "FUK": 1.5, "MEX": 14.5, "OAX": 16.0, "LIM": 20.0,
    "EZE": 24.0, "MDE": 19.0, "MIA": 15.5, "RAK": 16.0, "DXB": 9.5, "DAD": 5.0,
    "TPE": 2.5, "HKT": 7.0, "ASU": 25.0, "DOH": 10.0,
}


def _load_editorial() -> dict[str, dict]:
    if not EDITORIAL_CSV.exists():
        return {}
    with open(EDITORIAL_CSV, encoding="utf-8") as f:
        return {row["id"].strip(): row for row in csv.DictReader(f)}


def _split(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split("|") if x.strip()]


def _split_months(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x) for x in raw.split("|") if x.strip().isdigit()]


def _ed_int(ed: dict, key: str, fallback: int) -> int:
    raw = ed.get(key)
    if raw is not None and str(raw).strip().isdigit():
        return int(raw)
    return fallback


def build() -> list[dict]:
    cities = json.loads(resolve_data_path("city_scores.json").read_text(encoding="utf-8"))["cities"]
    editorial = _load_editorial()
    dests: list[dict] = []
    for c in cities:
        cid = c["id"]
        climate = c.get("climate", "")
        ed = editorial.get(cid, {})
        if cid not in FLIGHT_HOURS_FROM_ICN:
            raise ValueError(f"{cid}: FLIGHT_HOURS_FROM_ICN 에 비행시간 없음")
        d = {
            "id": cid,
            "city": c["city"],
            "city_kr": c["city_kr"],
            "country": c["country"],
            "country_id": c["country_id"],
            "monthly_cost_usd": c["monthly_cost_usd"],
            "internet_mbps": c["internet_mbps"],
            "english_score": c["english_score"],
            "climate": climate,
            "safety_score": c["safety_score"],
            "best_months": _split_months(ed.get("best_months")) or derive_best_months(climate),
            "peak_season": ed.get("peak_season") or derive_peak_season(climate),
            "avg_flight_hours_from_icn": FLIGHT_HOURS_FROM_ICN[cid],
            "budget_tier": derive_budget_tier(c["monthly_cost_usd"]),
            "activities": _split(ed.get("activities")) or derive_activities(climate),
            "vibe": ed.get("vibe") or derive_vibe(climate),
            "safety": round(c["safety_score"]),
            "kid_friendly": _ed_int(ed, "kid_friendly", derive_kid_friendly(c["safety_score"], c["english_score"])),
            "romantic": _ed_int(ed, "romantic", derive_romantic(climate)),
            "accessibility_score": _ed_int(ed, "accessibility_score", derive_accessibility(c["country_id"])),
            "nightlife": _ed_int(ed, "nightlife", derive_nightlife(c.get("community_size", "medium"))),
            "must_see": _split(ed.get("must_see")),
            "curated": cid in editorial,
        }
        errs = validate_destination(d)
        if errs:
            raise ValueError(f"{cid} 검증 실패: {errs}")
        dests.append(d)
    return dests


def main() -> None:
    dests = build()
    payload = {"destinations": dests}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out = resolve_data_path("destinations.json")
    out.write_text(text, encoding="utf-8")
    FRONTEND_COPY.write_text(text, encoding="utf-8")
    curated = sum(1 for d in dests if d["curated"])
    print(f"wrote {len(dests)} destinations ({curated} curated) → {out}")
    print(f"  frontend copy → {FRONTEND_COPY}")


if __name__ == "__main__":
    main()
