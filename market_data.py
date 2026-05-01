"""
market_data.py — WorldPolicy-Env V6.1 P3 yfinance market layer.

Live equity / index prices for the company P&L ticker strip + country indices.
Same shape as live_data.py: 60s cache, per-ticker static fallback, never raises.

Two entry points:
  - get_company_prices()   → list of dicts shaped exactly like the frontend's
                             CompanyPnLStrip COMPANIES constant. Drop-in replacement.
  - get_country_indices()  → per-agent country market index snapshot
                             (S&P / Hang Seng / Nifty / Tadawul / etc.)
  - get_market_snapshot()  → both above in one call (used by /market-data route).

Plan note Q3: Russian market symbols are disabled because yfinance no longer
has a reliable accessible MOEX/ADR proxy. Russia and DPRK use static fallback.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# yfinance is a soft dependency — module imports cleanly even if missing so that
# the env / SPA still boot. Live calls then return the static fallback set.
try:
    import yfinance as yf
    _YF_OK = True
except Exception:
    _YF_OK = False

CACHE_TTL = 60   # seconds
HTTP_TIMEOUT_HINT = 5.0  # yfinance manages its own HTTP, this is a soft guideline
_cache: Dict[str, Dict[str, Any]] = {}


def _cached(key: str) -> Optional[Any]:
    rec = _cache.get(key)
    if rec and time.time() - rec["ts"] < CACHE_TTL:
        return rec["data"]
    return None


def _store(key: str, data: Any) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


# ── Company tickers (drives CompanyPnLStrip; symbols match the existing UI) ──

# Each entry: ui_symbol → {yf_symbol, name, countryId, currency, fallback_price, fallback_pct}
# - ui_symbol is what the frontend renders (matches pnl.jsx COMPANIES symbol field).
# - yf_symbol is what yfinance hits. None for fictional tickers (KOMID).
# - fallback_* are used when yf returns nothing (sanctions, market closed, fictional).
COMPANY_TICKERS: Dict[str, Dict[str, Any]] = {
    "AAPL":  {"yf": "AAPL",         "name": "Apple",      "countryId": "USA",  "currency": "$",
              "fallback_price": 189.32, "fallback_pct": 0.8},
    "BYDDY": {"yf": "BYDDY",        "name": "BYD",        "countryId": "CHN",  "currency": "$",
              "fallback_price": 214.10, "fallback_pct": -1.2},
    "GAZP":  {"yf": None,            "name": "Gazprom",    "countryId": "RUS",  "currency": "₽",
              "fallback_price": 142.00, "fallback_pct": -2.1},   # No reliable yfinance MOEX/ADR proxy
    "RELI":  {"yf": "RELIANCE.NS",  "name": "Reliance",   "countryId": "IND",  "currency": "₹",
              "fallback_price": 2847.50, "fallback_pct": 0.4},
    "KOMID": {"yf": None,           "name": "KOMID Corp", "countryId": "DPRK", "currency": "₩",
              "fallback_price": 88.00, "fallback_pct": -0.5},   # no accessible market
    "2222":  {"yf": "2222.SR",      "name": "Aramco",     "countryId": "SAU",  "currency": "﷼",
              "fallback_price": 32.40, "fallback_pct": 1.3},
}

# Country-level indices (per plan line 1139–1146).
COUNTRY_INDEX_TICKERS: Dict[str, Optional[str]] = {
    "USA":  "^GSPC",      # S&P 500
    "CHN":  "^HSI",       # Hang Seng Index
    "RUS":  None,          # No reliable yfinance MOEX/ADR proxy
    "IND":  "^NSEI",      # Nifty 50
    "DPRK": None,         # No accessible market
    "SAU":  "2222.SR",    # Aramco as Tadawul proxy (^TASI not always available)
}


# ── Single-ticker fetcher with bulletproof fallback ──────────────────────────

def _fetch_one(yf_symbol: Optional[str]) -> Dict[str, Any]:
    """Try yfinance fast_info → history fallback → return None per field on fail.

    Returns: {"price": float|None, "previous_close": float|None,
              "change_pct": float|None, "live": bool}
    """
    if not yf_symbol or not _YF_OK:
        return {"price": None, "previous_close": None, "change_pct": None, "live": False}

    try:
        t = yf.Ticker(yf_symbol)
        # Path 1: fast_info (cheapest)
        try:
            fi = t.fast_info
            last = float(fi.get("last_price") or fi.get("lastPrice") or 0) or None
            prev = float(fi.get("previous_close") or fi.get("previousClose") or 0) or None
            if last and prev:
                pct = (last - prev) / prev * 100.0
                return {"price": last, "previous_close": prev, "change_pct": pct, "live": True}
        except Exception:
            pass

        # Path 2: history (slower but more reliable)
        hist = t.history(period="2d", auto_adjust=False)
        if hist is not None and len(hist) >= 1:
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last
            pct = (last - prev) / prev * 100.0 if prev else None
            return {"price": last, "previous_close": prev, "change_pct": pct, "live": True}
    except Exception:
        pass
    return {"price": None, "previous_close": None, "change_pct": None, "live": False}


# ── Public: company prices (frontend strip) ──────────────────────────────────

def get_company_prices() -> List[Dict[str, Any]]:
    """Return the same shape the frontend CompanyPnLStrip expects.

    [{symbol, name, countryId, currency, price, pct, live}, ...]
    Live where possible; falls back to the scripted static seed per-ticker.
    """
    cached = _cached("companies")
    if cached is not None:
        return cached

    out: List[Dict[str, Any]] = []
    for ui_symbol, meta in COMPANY_TICKERS.items():
        live = _fetch_one(meta["yf"])
        if live["price"] is not None and live["change_pct"] is not None:
            out.append({
                "symbol":    ui_symbol,
                "name":      meta["name"],
                "countryId": meta["countryId"],
                "currency":  meta["currency"],
                "price":     round(live["price"], 2),
                "pct":       round(live["change_pct"], 2),
                "live":      True,
            })
        else:
            out.append({
                "symbol":    ui_symbol,
                "name":      meta["name"],
                "countryId": meta["countryId"],
                "currency":  meta["currency"],
                "price":     meta["fallback_price"],
                "pct":       meta["fallback_pct"],
                "live":      False,
            })
    _store("companies", out)
    return out


# ── Public: country indices (per-agent market posture) ───────────────────────

def get_country_indices() -> Dict[str, Dict[str, Any]]:
    cached = _cached("indices")
    if cached is not None:
        return cached

    out: Dict[str, Dict[str, Any]] = {}
    for country, ticker in COUNTRY_INDEX_TICKERS.items():
        live = _fetch_one(ticker)
        out[country] = {
            "ticker":     ticker,
            "price":      round(live["price"], 2) if live["price"] is not None else None,
            "change_pct": round(live["change_pct"], 2) if live["change_pct"] is not None else None,
            "live":       live["live"],
        }
    _store("indices", out)
    return out


# ── Public: combined snapshot (used by the /market-data route) ───────────────

def get_market_snapshot() -> Dict[str, Any]:
    companies = get_company_prices()
    indices = get_country_indices()
    any_live = any(c.get("live") for c in companies) or any(i.get("live") for i in indices.values())
    return {
        "companies":  companies,
        "indices":    indices,
        "live":       bool(any_live),
        "yf_loaded":  _YF_OK,
        "fetched_at": time.time(),
        "cache_ttl":  CACHE_TTL,
    }


if __name__ == "__main__":
    snap = get_market_snapshot()
    print(f"yf_loaded={snap['yf_loaded']}  any_live={snap['live']}")
    for c in snap["companies"]:
        live_tag = "LIVE" if c["live"] else "fallback"
        print(f"  [{live_tag:8s}] {c['symbol']:6s} ({c['countryId']}): "
              f"{c['currency']}{c['price']:>10}  {c['pct']:+.2f}%")
    print()
    for country, idx in snap["indices"].items():
        live_tag = "LIVE" if idx["live"] else "fallback"
        print(f"  [{live_tag:8s}] {country:5s}: {idx['ticker']!s:12s}  "
              f"price={idx['price']}  pct={idx['change_pct']}")
