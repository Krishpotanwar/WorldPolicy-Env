"""
live_data.py — WorldPolicy-Env V6.1 live data layer (GDELT + World Bank).

P1: GDELT v2 doc API for crisis headlines (`get_live_crisis(crisis_type)`)
P2: World Bank API for per-country economic baselines (`get_wb_baseline(agent_id)`)
P2: GDELT per-country headlines for dynamic persona injection (`get_country_events`)

All calls:
  - 60-second in-memory cache (per crisis_type / per agent_id)
  - 3-second HTTP timeout
  - Fail-soft fallback to a 2023 static snapshot — env never crashes

This module is consumed by:
  - environment.py reset() → live crisis + WB baselines
  - persona_loader.build_system_prompt() → per-country event context (via P2)
  - server.py /live-crisis/{type} route → for the SPA + external probes

Plan note: yfinance market data (P3) and GDELT sentiment (P4) are deferred unless
P0–P2 ship clean and free time remains. Hooks here for later expansion.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
WB_API_TPL = "https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"

CACHE_TTL = 60  # seconds — same value across all live calls
HTTP_TIMEOUT = float(os.environ.get("WP_LIVE_TIMEOUT_S", 3.0))
USER_AGENT = "WorldPolicyEnv/1.0 (+https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6)"

_cache: Dict[str, Dict[str, Any]] = {}


def _cached(key: str) -> Optional[Any]:
    rec = _cache.get(key)
    if rec and time.time() - rec["ts"] < CACHE_TTL:
        return rec["data"]
    return None


def _store(key: str, data: Any) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


# ── P1: GDELT live crisis headlines ──────────────────────────────────────────

CRISIS_KEYWORDS: Dict[str, str] = {
    "natural_disaster":     "cyclone earthquake tsunami flood disaster humanitarian",
    "arms_race":            "nuclear weapons arms race military buildup missile",
    "trade_war":            "trade war tariffs sanctions economic coercion",
    "cultural_destruction": "heritage UNESCO destruction cultural artifact",
    "heritage_at_risk":     "world heritage site endangered cultural risk",
    "military_escalation":  "military escalation troops border conflict",
    "war_outbreak":         "war outbreak invasion military attack",
    "sanctions":            "economic sanctions embargo financial",
}

CRISIS_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "natural_disaster": {
        "type": "natural_disaster", "severity": 0.7, "live": False,
        "headline": "Severe cyclone makes landfall in Bay of Bengal; UNESCO heritage at risk.",
        "source_count": 0, "articles": [],
    },
    "arms_race": {
        "type": "arms_race", "severity": 0.85, "live": False,
        "headline": "Nuclear test reported; regional arms race accelerates.",
        "source_count": 0, "articles": [],
    },
    "trade_war": {
        "type": "trade_war", "severity": 0.55, "live": False,
        "headline": "Major economies impose retaliatory tariffs across critical sectors.",
        "source_count": 0, "articles": [],
    },
    "cultural_destruction": {
        "type": "cultural_destruction", "severity": 0.8, "live": False,
        "headline": "World Heritage site reported damaged in active conflict zone.",
        "source_count": 0, "articles": [],
    },
    "heritage_at_risk": {
        "type": "heritage_at_risk", "severity": 0.6, "live": False,
        "headline": "Multiple World Heritage sites flagged for emergency UNESCO inscription.",
        "source_count": 0, "articles": [],
    },
    "military_escalation": {
        "type": "military_escalation", "severity": 0.75, "live": False,
        "headline": "Troop concentrations reported on contested border.",
        "source_count": 0, "articles": [],
    },
    "war_outbreak": {
        "type": "war_outbreak", "severity": 0.95, "live": False,
        "headline": "Active hostilities reported; international response convening.",
        "source_count": 0, "articles": [],
    },
    "sanctions": {
        "type": "sanctions", "severity": 0.5, "live": False,
        "headline": "Coordinated sanctions package announced targeting financial sector.",
        "source_count": 0, "articles": [],
    },
}


def _crisis_fallback(crisis_type: str, reason: str = "static_fallback") -> Dict[str, Any]:
    base = CRISIS_FALLBACKS.get(
        crisis_type,
        {"type": crisis_type, "severity": 0.5, "live": False, "headline": None,
         "source_count": 0, "articles": []},
    )
    return {**base, "fallback_reason": reason}


def get_live_crisis(crisis_type: str) -> Dict[str, Any]:
    """GDELT-backed crisis headline. Cached 60s, fails soft to static fallback."""
    cache_key = f"crisis::{crisis_type}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    query = CRISIS_KEYWORDS.get(crisis_type, crisis_type.replace("_", " "))
    try:
        r = requests.get(
            GDELT_API,
            params={
                "query": query,
                "mode": "artlist",
                "maxrecords": 5,
                "format": "json",
                "timespan": "6h",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        articles = (r.json() or {}).get("articles") or []
    except Exception as exc:
        result = _crisis_fallback(crisis_type, f"gdelt_error: {type(exc).__name__}")
        _store(cache_key, result)
        return result

    if not articles:
        result = _crisis_fallback(crisis_type, "gdelt_empty")
        _store(cache_key, result)
        return result

    result = {
        "type": crisis_type,
        "live": True,
        "severity": 0.5 + min(0.4, len(articles) * 0.05),  # heuristic intensity
        "headline": articles[0].get("title"),
        "source_count": len(articles),
        "articles": [
            {"title": a.get("title"), "url": a.get("url"), "domain": a.get("domain")}
            for a in articles[:3]
        ],
        "fetched_at": time.time(),
    }
    _store(cache_key, result)
    return result


# ── P2: GDELT per-country event headlines (for dynamic persona injection) ───

COUNTRY_GDELT_QUERIES: Dict[str, str] = {
    "USA":  "United States foreign policy military diplomacy sanctions",
    "CHN":  "China foreign policy trade territorial South China Sea",
    "RUS":  "Russia military energy sanctions Ukraine war",
    "IND":  "India foreign policy strategic autonomy BRICS",
    "DPRK": "North Korea nuclear missile sanctions",
    "SAU":  "Saudi Arabia OPEC oil diplomacy Yemen",
    "UNESCO": "UNESCO heritage cultural protection convention",
}

COUNTRY_EVENT_FALLBACKS: Dict[str, List[str]] = {
    "USA":  ["State Department reaffirms alliance commitments in Indo-Pacific."],
    "CHN":  ["Beijing announces new BRI infrastructure tranche."],
    "RUS":  ["Moscow flags energy supply contingencies amid sanctions."],
    "IND":  ["Delhi reasserts strategic autonomy at multilateral forum."],
    "DPRK": ["Pyongyang reports successful weapons systems test."],
    "SAU":  ["Riyadh signals OPEC+ output coordination."],
    "UNESCO": ["UNESCO Director-General convenes emergency heritage session."],
}


def get_country_events(agent_id: str) -> List[str]:
    """Return last-24h GDELT headlines for an agent's country. Caps at 3."""
    cache_key = f"events::{agent_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    query = COUNTRY_GDELT_QUERIES.get(agent_id, agent_id)
    try:
        r = requests.get(
            GDELT_API,
            params={
                "query": query,
                "mode": "artlist",
                "maxrecords": 3,
                "format": "json",
                "timespan": "24h",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        articles = (r.json() or {}).get("articles") or []
        events = [str(a.get("title", "")).strip() for a in articles[:3] if a.get("title")]
        if not events:
            events = list(COUNTRY_EVENT_FALLBACKS.get(agent_id, []))
    except Exception:
        events = list(COUNTRY_EVENT_FALLBACKS.get(agent_id, []))

    _store(cache_key, events)
    return events


# ── P2: World Bank P&L baselines ─────────────────────────────────────────────

WB_INDICATORS: Dict[str, str] = {
    "gdp":      "NY.GDP.MKTP.CD",   # GDP (current US$)
    "military": "MS.MIL.XPND.CD",   # Military expenditure (current US$)
    "welfare":  "SI.POV.DDAY",      # Poverty headcount ratio at $2.15/day (% of pop)
}

WB_COUNTRIES: Dict[str, str] = {
    "USA": "US", "CHN": "CN", "RUS": "RU", "IND": "IN", "DPRK": "KP", "SAU": "SA",
}

# 2023 World Bank snapshot — used when API is unavailable or returns nulls.
# GDP/military in USD, welfare = % of population below $2.15/day (PPP).
WB_FALLBACKS: Dict[str, Dict[str, float]] = {
    "USA":  {"gdp": 27.36e12, "military": 916e9,  "welfare": 1.0},
    "CHN":  {"gdp": 17.79e12, "military": 225e9,  "welfare": 0.1},
    "RUS":  {"gdp": 1.86e12,  "military": 109e9,  "welfare": 0.5},
    "IND":  {"gdp": 3.55e12,  "military": 84e9,   "welfare": 12.3},
    "DPRK": {"gdp": 30e9,     "military": 4e9,    "welfare": 42.0},
    "SAU":  {"gdp": 1.07e12,  "military": 75e9,   "welfare": 0.1},
}


def _wb_fetch_one(country_code: str, indicator: str) -> Optional[float]:
    """Single World Bank API call. Returns the most recent value or None."""
    url = WB_API_TPL.format(code=country_code, indicator=indicator)
    try:
        r = requests.get(
            url,
            params={"format": "json", "mrv": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # WB shape: [meta, [{value: ..., date: ...}, ...]]
        if isinstance(data, list) and len(data) >= 2 and data[1]:
            v = data[1][0].get("value")
            if v is not None:
                return float(v)
    except Exception:
        return None
    return None


def get_wb_baseline(agent_id: str) -> Dict[str, float]:
    """Return {gdp, military, welfare} for an agent. Cached 60s. Falls back per-key."""
    cache_key = f"wb::{agent_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    code = WB_COUNTRIES.get(agent_id, "US")
    fallback = WB_FALLBACKS.get(agent_id, {"gdp": 1e12, "military": 1e10, "welfare": 50.0})
    out: Dict[str, float] = {}
    for key, indicator in WB_INDICATORS.items():
        v = _wb_fetch_one(code, indicator)
        out[key] = v if v is not None else fallback.get(key, 0.0)

    _store(cache_key, out)
    return out


# ── P4: GDELT tone-based public sentiment per country ───────────────────────

# Sentiment label thresholds (GDELT tone is roughly in [-10, +10] in practice
# though theoretical range is [-100, +100]). Bands chosen empirically from
# typical news coverage; positive coverage clusters near 0 to +3.
SENTIMENT_BANDS = [
    (-100, -7,  "very_negative", "#dc2626"),
    (-7,   -3,  "negative",      "#ef4444"),
    (-3,    3,  "neutral",       "#94a3b8"),
    ( 3,    7,  "positive",      "#22c55e"),
    ( 7,  100,  "very_positive", "#16a34a"),
]


def _label_for_tone(tone: float) -> tuple[str, str]:
    """Map a GDELT tone score to (label, hex_color)."""
    for lo, hi, label, color in SENTIMENT_BANDS:
        if lo <= tone < hi:
            return label, color
    return "neutral", "#94a3b8"


SENTIMENT_FALLBACKS: Dict[str, Dict[str, Any]] = {
    # Plausible but neutral defaults — used when GDELT is unreachable.
    # tone in [-10, +10] roughly; sample_size = articles aggregated.
    "USA":  {"tone": 0.5,  "sample_size": 0, "live": False},
    "CHN":  {"tone": -0.5, "sample_size": 0, "live": False},
    "RUS":  {"tone": -2.5, "sample_size": 0, "live": False},
    "IND":  {"tone": 1.0,  "sample_size": 0, "live": False},
    "DPRK": {"tone": -3.5, "sample_size": 0, "live": False},
    "SAU":  {"tone": 0.0,  "sample_size": 0, "live": False},
    "UNESCO": {"tone": 1.5, "sample_size": 0, "live": False},
}


def get_country_sentiment(agent_id: str) -> Dict[str, Any]:
    """GDELT tonechart-derived public sentiment for an agent's country.

    Returns: {tone, tone_normalized, label, color, sample_size, live, fallback_reason?}
      - tone: average GDELT tone score (~ [-10, +10])
      - tone_normalized: tone / 10, clamped to [-1, 1] for the persona prompt
      - label: very_negative | negative | neutral | positive | very_positive
      - color: hex string for the frontend chip
      - sample_size: number of GDELT bins aggregated
      - live: True if the call hit GDELT successfully and returned tone bins
    """
    cache_key = f"sentiment::{agent_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    fallback = SENTIMENT_FALLBACKS.get(agent_id, {"tone": 0.0, "sample_size": 0, "live": False})

    def _build(tone: float, sample: int, live: bool, reason: Optional[str] = None) -> Dict[str, Any]:
        clamped_tone = max(-10.0, min(10.0, tone))
        normalized = max(-1.0, min(1.0, tone / 10.0))
        label, color = _label_for_tone(clamped_tone)
        out = {
            "agent_id":        agent_id,
            "tone":            round(clamped_tone, 2),
            "tone_normalized": round(normalized, 3),
            "label":           label,
            "color":           color,
            "sample_size":     sample,
            "live":            live,
        }
        if reason:
            out["fallback_reason"] = reason
        return out

    query = COUNTRY_GDELT_QUERIES.get(agent_id, agent_id)
    try:
        r = requests.get(
            GDELT_API,
            params={
                "query":    query,
                "mode":     "tonechart",
                "format":   "json",
                "timespan": "24h",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json() or {}
        bins = data.get("tonechart") or []
    except Exception as exc:
        result = _build(fallback["tone"], 0, False, f"gdelt_error: {type(exc).__name__}")
        _store(cache_key, result)
        return result

    if not bins:
        result = _build(fallback["tone"], 0, False, "gdelt_empty")
        _store(cache_key, result)
        return result

    total_count = 0
    weighted_sum = 0.0
    for entry in bins:
        try:
            bin_val = float(entry.get("bin", 0))
            count = int(entry.get("count", 0))
        except (TypeError, ValueError):
            continue
        weighted_sum += bin_val * count
        total_count += count

    if total_count <= 0:
        result = _build(fallback["tone"], 0, False, "gdelt_zero_count")
        _store(cache_key, result)
        return result

    avg_tone = weighted_sum / total_count
    result = _build(avg_tone, total_count, True)
    _store(cache_key, result)
    return result


def get_all_sentiments(agent_ids: list[str] | None = None) -> Dict[str, Dict[str, Any]]:
    """Snapshot of all 7 agents' sentiments (or a custom subset). For /sentiment route.

    Fans out to a thread pool so 7 GDELT calls run in parallel — total wall clock
    is ~max(per-call) instead of ~sum(per-call). Every per-call still has its
    own 60s cache so this is cheap after the first warm-up.
    """
    from concurrent.futures import ThreadPoolExecutor

    ids = agent_ids or ["USA", "CHN", "RUS", "IND", "DPRK", "SAU", "UNESCO"]
    out: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=len(ids)) as pool:
        results = list(pool.map(get_country_sentiment, ids))
    for aid, res in zip(ids, results):
        out[aid] = res
    return out


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("crisis(natural_disaster):", get_live_crisis("natural_disaster"))
    print("events(USA):", get_country_events("USA"))
    print("wb(IND):", get_wb_baseline("IND"))
    print()
    print("=== sentiment per agent ===")
    for aid in ["USA", "CHN", "RUS", "IND", "DPRK", "SAU", "UNESCO"]:
        s = get_country_sentiment(aid)
        live_tag = "LIVE" if s["live"] else "fallback"
        print(f"  [{live_tag:8s}] {aid:6s} tone={s['tone']:+.2f}  label={s['label']:14s}  n={s['sample_size']}")
