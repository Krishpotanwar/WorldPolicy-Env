"""
server.py — WorldPolicy-Env V6.1 OpenEnv-compliant FastAPI backend.

The base app is built by `openenv.core.env_server.http_server.create_app`, which
gives us the standard OpenEnv contract for free:

    POST /reset    POST /step    GET /state    GET /schema    GET /health    WS /ws
    GET  /docs    (FastAPI auto-docs)

On top of that we keep every pre-existing route from the V6.1 demo:

    GET  /groq-status              (renamed from /health to avoid OpenEnv collision)
    GET  /persona/{agent_id}
    GET  /relationship-matrix
    GET  /un-authority/{crisis_type}
    GET  /vote-outcome/{round_id}
    GET  /stream/debate            (SSE)
    GET  /stream/country-pnl       (SSE)
    GET  /stream/company-pnl       (SSE)
    POST /live-debate              -> { round_id }

And we add new plan endpoints:

    POST /grader                   composite scoring across a finished episode
    GET  /live-crisis/{type}       GDELT live headline (cached + fallback)
    GET  /tasks                    catalogue of 3 graduated tasks

Plus the SPA routes (must stay AFTER all API routes due to /{fname:path} catch-all):

    GET  /                         WorldPolicy V6.1.html
    GET  /{fname:path}             whitelisted static (.css .jsx .js .json .md ...)

Run:
    python server.py            # binds 0.0.0.0:7860 (HF Spaces convention)
    uvicorn server:app          # equivalent
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from dotenv import load_dotenv
from fastapi import HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse

from openenv.core.env_server.http_server import create_app

# Load local .env before importing modules that read env at import time.
# override=True ensures stale exported shell vars don't shadow .env edits.
load_dotenv(override=True)

from debate_orchestrator import DebateOrchestrator, UNMediator
from environment import WorldPolicyEnvironment
from graders import grade_episode
from models import WorldPolicyAction, WorldPolicyObservation
from persona_loader import PersonaLoader
from tasks import list_tasks, TASKS
from crisis_types import ALLOWED_CRISIS_TYPES as _ALLOWED_CRISIS

# Optional: live-data layer (added in P1). Guarded so server still boots if missing.
try:
    from live_data import get_live_crisis  # noqa: F401
    _LIVE_DATA_OK = True
except Exception:
    _LIVE_DATA_OK = False

# Optional: yfinance market layer (P3). Soft import — server boots cleanly if
# yfinance is missing; the company ticker strip + /market-data both fall through
# to the static seed in that case.
try:
    from market_data import get_market_snapshot, get_company_prices
    _MARKET_DATA_OK = True
except Exception:
    _MARKET_DATA_OK = False

ROOT = Path(__file__).parent.resolve()
PERSONAS_DIR = ROOT / "personas"
INDEX_HTML = ROOT / "WorldPolicy V6.1.html"

AGENT_IDS = {"USA", "CHN", "RUS", "IND", "DPRK", "SAU", "UN"}

# V6: Input validation allowlists
ALLOWED_CRISIS_TYPES = _ALLOWED_CRISIS
MAX_DESCRIPTION_LEN = 500
MAX_ACTION_LEN = 100

# V2: CORS origins from env, default restrictive
_cors_origins = os.environ.get("WP_CORS_ORIGINS", "*").split(",")

# ── App ──────────────────────────────────────────────────────────────────
# OpenEnv builds the FastAPI app for us. max_concurrent_envs=4 matches the
# standard GRPO 4-rollout pattern so the validator can fan out cleanly.

app = create_app(
    WorldPolicyEnvironment,
    WorldPolicyAction,
    WorldPolicyObservation,
    env_name="worldpolicy_env",
    max_concurrent_envs=int(os.environ.get("WP_MAX_CONCURRENT_ENVS", 4)),
)
app.title = "WorldPolicy-Env V6.1 Backend"
app.version = "1.0.0"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Singletons ───────────────────────────────────────────────────────────

_loader = PersonaLoader()
_orchestrator = DebateOrchestrator()
_mediator = UNMediator()

# round_id -> {"vote_tally": {...}, "crisis_type": ..., "utterances": [...]}
_round_cache: dict[str, dict] = {}
_recent_rounds: deque[str] = deque(maxlen=32)

# ── Helpers ──────────────────────────────────────────────────────────────

def _sse(payload: dict, event: str | None = None) -> str:
    """Format a single SSE frame."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(payload)}\n\n"


def _store_round(round_id: str, crisis_type: str, utterances: list[dict], tally: dict):
    _round_cache[round_id] = {
        "round_id": round_id,
        "crisis_type": crisis_type,
        "vote_tally": tally,
        "utterances": utterances,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }
    _recent_rounds.append(round_id)
    if len(_round_cache) > _recent_rounds.maxlen:
        stale = set(_round_cache.keys()) - set(_recent_rounds)
        for sid in stale:
            _round_cache.pop(sid, None)


# ── Routes ──────────────────────────────────────────────────────────────
# Note: /health is owned by OpenEnv (created by create_app). Our pre-existing
# liveness payload moved to /groq-status to avoid the collision while preserving
# the SPA's amber/teal LED behaviour.

@app.get("/groq-status")
def groq_status():
    backend = getattr(_orchestrator, "_backend", "none")
    return {
        "status": "ok",
        "debate_backend": backend,
        "live_debate_enabled": bool(getattr(_orchestrator, "_use_live", False)),
        "live_groq": backend == "groq",
        "live_trained_model": backend == "mappo",
        "live_data_layer": _LIVE_DATA_OK,
        "market_data_layer": _MARKET_DATA_OK,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/market-data")
def market_data():
    """P3: live yfinance market snapshot. Companies + country indices + cache info.

    Returns the same shape as `market_data.get_market_snapshot()`:
        {companies: [{symbol, name, countryId, currency, price, pct, live}, ...],
         indices:   {AGENT_ID: {ticker, price, change_pct, live}, ...},
         live: bool, yf_loaded: bool, fetched_at: float, cache_ttl: int}
    """
    if not _MARKET_DATA_OK:
        return {
            "companies": [],
            "indices": {},
            "live": False,
            "yf_loaded": False,
            "fetched_at": datetime.now(timezone.utc).timestamp(),
            "cache_ttl": 0,
            "error": "market_data module unavailable",
        }
    return get_market_snapshot()


@app.get("/tasks")
def get_tasks():
    """Catalogue of the 3 graduated tasks (consumed by inference.py + UI)."""
    return {"tasks": list_tasks()}


@app.post("/grader")
def grader(body: dict):
    """Composite scoring across a finished episode.

    Body shape:
        { "session_id": str | null, "task": "task_1" | "task_2" | "task_3",
          "rounds": [ {round_result dicts as emitted in step()'s metadata.round} ] }

    Returns: { task, raw_score, avg_per_round, normalized, step_count, target_range }
    """
    task = str(body.get("task") or "task_1")
    rounds = body.get("rounds") or []
    if not isinstance(rounds, list):
        raise HTTPException(400, "rounds must be a list of round_result dicts")
    result = grade_episode(rounds, task=task)
    # Attach the task's target reward range so callers can gate reward-hacking checks
    from tasks import get_task as _get_task
    cfg = _get_task(task)
    result["target_range"] = list(cfg.get("target_reward_range", (0.4, 0.8)))
    result["session_id"] = body.get("session_id")
    return result


@app.get("/live-crisis/{crisis_type}")
def live_crisis(crisis_type: str):
    """GDELT-backed live crisis headline. Falls back to static if live layer absent."""
    if crisis_type not in ALLOWED_CRISIS_TYPES:
        raise HTTPException(400, f"unknown crisis_type; allowed: {sorted(ALLOWED_CRISIS_TYPES)}")
    if not _LIVE_DATA_OK:
        return {"type": crisis_type, "live": False, "headline": None, "fallback_reason": "live_data module missing"}
    from live_data import get_live_crisis as _gc
    return _gc(crisis_type)


@app.get("/country-sentiment/{agent_id}")
def country_sentiment(agent_id: str):
    """P4: GDELT tonechart-derived public sentiment for one agent's country."""
    aid = agent_id.upper()
    if aid not in AGENT_IDS:
        raise HTTPException(404, f"unknown agent '{aid}'")
    if not _LIVE_DATA_OK:
        return {"agent_id": aid, "tone": 0.0, "label": "neutral", "live": False,
                "color": "#94a3b8", "sample_size": 0, "fallback_reason": "live_data module missing"}
    from live_data import get_country_sentiment as _gcs
    return _gcs(aid)


@app.get("/sentiment")
def sentiment_snapshot():
    """P4: snapshot of all 7 agents' sentiments. Frontend hits this on mount + every 60s."""
    if not _LIVE_DATA_OK:
        return {"sentiments": {}, "live": False, "error": "live_data module unavailable"}
    from live_data import get_all_sentiments as _all
    snap = _all()
    any_live = any(v.get("live") for v in snap.values())
    return {"sentiments": snap, "live": bool(any_live)}


@app.get("/persona/{agent_id}", response_class=PlainTextResponse)
def get_persona(agent_id: str):
    agent_id = agent_id.upper()
    if agent_id not in AGENT_IDS:
        raise HTTPException(404, f"unknown agent '{agent_id}'")
    try:
        return _loader.load_persona(agent_id)
    except FileNotFoundError:
        raise HTTPException(404, f"persona file missing for {agent_id}")


@app.get("/relationship-matrix")
def get_matrix():
    return {
        "matrix": _loader._relationships,
        "grudge_memory": _loader._grudge_memory,
    }


@app.get("/un-authority/{crisis_type}")
def get_authority(crisis_type: str, limit: int = Query(3, ge=1, le=10)):
    if crisis_type not in ALLOWED_CRISIS_TYPES:
        raise HTTPException(400, f"unknown crisis type '{crisis_type}'; allowed: {sorted(ALLOWED_CRISIS_TYPES)}")
    articles = _mediator.get_articles_for_crisis(crisis_type, limit=limit)
    if not articles:
        raise HTTPException(404, f"no authority articles for crisis '{crisis_type}'")
    return {
        "crisis_type": crisis_type,
        "within_mandate": _mediator.is_within_mandate(crisis_type),
        "articles": articles,
    }


@app.get("/vote-outcome/{round_id}")
def get_vote(round_id: str):
    record = _round_cache.get(round_id)
    if not record:
        raise HTTPException(404, f"round_id '{round_id}' not cached")
    return record


# ── Streaming debate ────────────────────────────────────────────────────

_ALL_AGENTS = ["USA", "CHN", "RUS", "IND", "DPRK", "SAU", "UN"]

_DEFAULT_INVOLVEMENT = {
    "involved": ["USA", "CHN", "RUS", "IND", "DPRK", "SAU"],
    "peripheral": ["UN"],
    "uninvolved": [],
}


def _derive_involvement(crisis_type: str) -> dict:
    """Derive involvement tiers from task config. All sovereign agents speak;
    primary_agents go first, rest follow, UN always last."""
    for task_cfg in TASKS.values():
        if task_cfg.get("crisis_type") == crisis_type:
            active = task_cfg["active_agents"]
            primary = task_cfg.get("primary_agents", [])
            sovereign = [a for a in active if a != "UN"]
            involved = [a for a in sovereign if a in primary]
            peripheral = [a for a in sovereign if a not in primary] + ["UN"]
            uninvolved = [a for a in _ALL_AGENTS if a not in active]
            return {"involved": involved, "peripheral": peripheral, "uninvolved": uninvolved}
    return dict(_DEFAULT_INVOLVEMENT)


async def _debate_event_stream(
    crisis_type: str,
    crisis_description: str,
    mappo_action: str,
    force_canned: bool,
    max_rounds: int,
) -> AsyncIterator[str]:
    # Prefer real-time crisis headline when available so debate context is live.
    try:
        live = get_live_crisis(crisis_type) if _LIVE_DATA_OK else None
        live_headline = (live or {}).get("headline") if isinstance(live, dict) else None
        if live_headline:
            crisis_description = str(live_headline)[:MAX_DESCRIPTION_LEN]
    except Exception:
        pass

    involvement = _derive_involvement(crisis_type)
    task_cfg = next((t for t in TASKS.values() if t.get("crisis_type") == crisis_type), None)
    max_steps = task_cfg["max_steps"] if task_cfg else 10
    world_state = {
        "step": max_steps // 2,
        "welfare_index": 0.50,
        "active_crises": [crisis_type],
        "crisis_description": crisis_description,
    }

    try:
        async for event in _orchestrator.run_multi_round_debate(
            crisis_type=crisis_type,
            crisis_description=crisis_description,
            mappo_action=mappo_action,
            world_state=world_state,
            involvement=involvement,
            force_canned=force_canned,
            max_rounds=max_rounds,
        ):
            etype = event.pop("_event", "utterance")
            yield _sse(event, event=etype)
    except Exception as exc:
        yield _sse({"error": str(exc)}, event="error_event")


@app.get("/stream/debate")
async def stream_debate(
    crisis_type: str = Query("natural_disaster"),
    crisis_description: str = Query("Severe cyclone hits Bay of Bengal; UNESCO heritage sites at risk."),
    mappo_action: str = Query("AID_DISPATCH_COORDINATED"),
    force_canned: bool = Query(True),
    max_rounds: int = Query(3, ge=1, le=3),
):
    if crisis_type not in ALLOWED_CRISIS_TYPES:
        raise HTTPException(400, f"unknown crisis_type; allowed: {sorted(ALLOWED_CRISIS_TYPES)}")
    crisis_description = crisis_description[:MAX_DESCRIPTION_LEN]
    mappo_action = mappo_action[:MAX_ACTION_LEN]

    return StreamingResponse(
        _debate_event_stream(crisis_type, crisis_description, mappo_action, force_canned, max_rounds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/live-debate")
async def live_debate(
    crisis_type: str = Query("natural_disaster"),
    crisis_description: str = Query("Severe cyclone hits Bay of Bengal; UNESCO heritage sites at risk."),
    mappo_action: str = Query("AID_DISPATCH_COORDINATED"),
    max_rounds: int = Query(3, ge=1, le=3),
):
    """Kick off a live Groq debate (or canned if no key). Returns metadata to subscribe to /stream/debate."""
    if crisis_type not in ALLOWED_CRISIS_TYPES:
        raise HTTPException(400, f"unknown crisis_type; allowed: {sorted(ALLOWED_CRISIS_TYPES)}")
    crisis_description = crisis_description[:MAX_DESCRIPTION_LEN]
    mappo_action = mappo_action[:MAX_ACTION_LEN]

    if not _orchestrator._use_live:
        return JSONResponse(
            {"live": False, "reason": "No live debate backend configured (set HF_TOKEN for trained model or switch backend). /stream/debate will serve canned.",
             "subscribe": f"/stream/debate?force_canned=true&max_rounds={max_rounds}&crisis_type={crisis_type}"},
            status_code=200,
        )
    return {
        "live": True,
        "subscribe": f"/stream/debate?force_canned=false&max_rounds={max_rounds}&crisis_type={crisis_type}",
    }


# ── Country / Company P&L streams ───────────────────────────────────────

_SCRIPTED_COUNTRY_TICKS = [
    {"at": 2, "countryId": "USA", "deltas": {"gdp": -0.02, "welfare": -0.01}},
    {"at": 5, "countryId": "CHN", "deltas": {"gdp": -0.01, "influence": 0.015}},
    {"at": 8, "countryId": "RUS", "deltas": {"gdp": 0.005, "military": 0.03}},
    {"at": 11, "countryId": "IND", "deltas": {"gdp": 0.02, "welfare": 0.018}},
    {"at": 17, "countryId": "SAU", "deltas": {"gdp": -0.015, "energy": 0.02}},
    {"at": 20, "countryId": "UN", "deltas": {"heritage": 0.04}},
    {"at": 25, "countryId": "USA", "deltas": {"gdp": -0.01, "influence": -0.02}},
    {"at": 34, "countryId": "IND", "deltas": {"gdp": 0.03, "influence": 0.025}},
    {"at": 45, "countryId": "IND", "deltas": {"welfare": 0.04, "heritage": 0.02}},
]

_SCRIPTED_COMPANY_TICKS = [
    {"at": 5, "symbol": "AAPL", "price": 189.32, "pct": 0.8},
    {"at": 5, "symbol": "BYDDY", "price": 215.40, "pct": -0.6},
    {"at": 12, "symbol": "GAZP", "price": 139.20, "pct": -3.8},
    {"at": 12, "symbol": "RELI", "price": 2860.00, "pct": 0.9},
    {"at": 20, "symbol": "2222", "price": 33.10, "pct": 2.2},
    {"at": 30, "symbol": "GAZP", "price": 136.00, "pct": -5.1},
    {"at": 30, "symbol": "KOMID", "price": 86.50, "pct": -2.2},
    {"at": 40, "symbol": "AAPL", "price": 190.50, "pct": 1.4},
    {"at": 40, "symbol": "2222", "price": 33.80, "pct": 3.5},
]


async def _pnl_stream(entries: list[dict], tick_ms: int = 800) -> AsyncIterator[str]:
    step = 0
    max_step = max(e["at"] for e in entries) + 2
    while step <= max_step:
        step += 1
        emitted = [e for e in entries if e["at"] == step]
        for ev in emitted:
            payload = {**ev, "step": step, "ts": datetime.now(timezone.utc).isoformat()}
            yield _sse(payload, event="pnl_tick")
        await asyncio.sleep(tick_ms / 1000)
    yield _sse({"step": step, "done": True}, event="pnl_end")


@app.get("/stream/country-pnl")
async def stream_country_pnl(tick_ms: int = Query(800, ge=50, le=5000)):
    return StreamingResponse(
        _pnl_stream(_SCRIPTED_COUNTRY_TICKS, tick_ms),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _build_company_ticks_with_live() -> list[dict]:
    """P3: keep the scripted *cadence* of _SCRIPTED_COMPANY_TICKS but overwrite
    each tick's `price` + `pct` with the live yfinance snapshot when available.

    Result: the existing SSE stream the SPA already consumes ships LIVE prices
    on a deterministic schedule. Falls back to the scripted constants if the
    market layer is missing or returned no live data for that symbol.
    """
    if not _MARKET_DATA_OK:
        return [{**t, "_demo": True, "live": False} for t in _SCRIPTED_COMPANY_TICKS]
    try:
        live = {c["symbol"]: c for c in get_company_prices() or []}
    except Exception:
        return [{**t, "_demo": True, "live": False} for t in _SCRIPTED_COMPANY_TICKS]
    out = []
    for tick in _SCRIPTED_COMPANY_TICKS:
        sym = tick["symbol"]
        live_row = live.get(sym, {})
        merged = {**tick}
        if live_row.get("live"):
            merged["price"] = live_row["price"]
            merged["pct"]   = live_row["pct"]
            merged["live"]  = True
            merged["_demo"] = False
        else:
            merged["live"]  = False
            merged["_demo"] = True
        out.append(merged)
    return out


@app.get("/stream/company-pnl")
async def stream_company_pnl(tick_ms: int = Query(800, ge=50, le=5000)):
    return StreamingResponse(
        _pnl_stream(_build_company_ticks_with_live(), tick_ms),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Static frontend (same-origin serve for HF Spaces single-container) ──

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
def root_index():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML, media_type="text/html")
    raise HTTPException(404, "index HTML missing")


_STATIC_WHITELIST = {".css", ".jsx", ".js", ".json", ".md", ".png", ".jpg", ".svg", ".ico"}

_MEDIA_TYPES = {
    ".jsx": "text/babel",
    ".js":  "application/javascript",
    ".css": "text/css",
    ".md":  "text/markdown",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


@app.api_route("/{fname:path}", methods=["GET", "HEAD"], include_in_schema=False)
def serve_static(fname: str):
    """Serve project root files (CSS, JSX, personas/*) behind an extension whitelist.

    V1 FIX: Uses Path.resolve() + is_relative_to() to prevent path traversal.
    Rejects symlinks pointing outside ROOT.
    """
    if not fname or fname.startswith("/"):
        raise HTTPException(400, "invalid path")

    # V1: Resolve to real path and verify containment
    target = (ROOT / fname).resolve()
    if not target.is_relative_to(ROOT):
        raise HTTPException(403, "access denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "not found")
    if target.suffix.lower() not in _STATIC_WHITELIST:
        raise HTTPException(403, f"type not served: {target.suffix}")

    media = _MEDIA_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(target, media_type=media)


# ── CLI entry ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
