"""
debate_orchestrator.py — WorldPolicy-Env V6.1
Orchestrates multi-agent LLM debates using Groq (Llama 3.3-70b).

Usage:
    orchestrator = DebateOrchestrator()
    async for utterance in orchestrator.run_debate_round(crisis, mappo_action, involvement):
        print(utterance)

Environment variables required:
    GROQ_API_KEY — your Groq API key
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Literal

VALID_STANCES = {"support", "oppose", "modify", "neutral", "mediate"}
MAX_UTTERANCE_TEXT_LEN = 1000

try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  groq package not installed. Run: pip install groq")

from persona_loader import PersonaLoader

# P2 — optional dynamic persona injection. live_data is a soft dependency: if the
# module is missing, we fall back to no per-country event injection silently.
# P4 — same module also provides per-country sentiment (GDELT tonechart).
try:
    from live_data import get_country_events, get_country_sentiment
    _LIVE_EVENTS_OK = True
except Exception:
    _LIVE_EVENTS_OK = False
    def get_country_events(agent_id: str) -> list[str]:  # type: ignore
        return []
    def get_country_sentiment(agent_id: str) -> dict:  # type: ignore
        return {}

# ── Constants ──────────────────────────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 15.0
MAX_TOKENS_PER_AGENT = 300
DEBATE_RATE_LIMIT_STEPS = 8  # 1 debate round per N simulation steps

DATA_DIR = Path(__file__).parent / "data"
AUDIT_LOG = Path(__file__).parent / "debate_audit.jsonl"
AUDIT_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB rotate threshold


def _append_audit(record: dict) -> None:
    """Append audit record with size-based rotation (5MB → .1, drop older)."""
    try:
        if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size > AUDIT_LOG_MAX_BYTES:
            backup = AUDIT_LOG.with_suffix(".jsonl.1")
            if backup.exists():
                backup.unlink()
            AUDIT_LOG.rename(backup)
    except OSError:
        pass  # best-effort rotation; never block debate round
    with open(AUDIT_LOG, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(record) + "\n")


StanceType = Literal["support", "oppose", "modify", "neutral", "mediate"]

# ── Fallback canned debates ────────────────────────────────────────────────────

CANNED_DEBATES: dict[str, list[dict]] = {
    "natural_disaster": [
        {"speaker": "IND", "stance": "modify", "text": "India exercises strategic autonomy in accepting bilateral aid. We welcome assistance from all partners but insist on sovereign control of distribution within our exclusive economic zone.", "mentioned_countries": ["USA", "CHN"], "authority_citation": None},
        {"speaker": "USA", "stance": "support", "text": "The United States is prepared to commit carrier group assets for rapid humanitarian deployment. Our partners in this chamber can count on our resources and our resolve.", "mentioned_countries": ["IND"], "authority_citation": None},
        {"speaker": "CHN", "stance": "modify", "text": "This aid must not be tied to political conditions or military presence. China supports humanitarian assistance through UN mechanisms only. The AIIB stands ready to contribute development financing.", "mentioned_countries": ["USA", "IND"], "authority_citation": None},
        {"speaker": "RUS", "stance": "oppose", "text": "Russia cannot support operations that position NATO naval assets in the Indian Ocean under humanitarian pretexts. Our counter-proposal routes aid through BRICS channels — no military component.", "mentioned_countries": ["USA", "CHN", "IND"], "authority_citation": None},
        {"speaker": "SAU", "stance": "support", "text": "The Kingdom is prepared to commit $2 billion from our sovereign wealth fund, contingent on energy infrastructure receiving priority. We propose a joint civilian-flagged framework.", "mentioned_countries": ["IND", "USA"], "authority_citation": None},
        {"speaker": "DPRK", "stance": "oppose", "text": "The imperialist powers use disasters to extend military reach. We reject any framework that normalizes foreign naval presence near sovereign waters.", "mentioned_countries": ["USA"], "authority_citation": None},
        {"speaker": "UNESCO", "stance": "mediate", "text": "Under WHC-1972 Art.11.4 — Emergency Inscription, Heritage in Danger, I am requesting emergency inscription of the Sundarbans Mangrove System. I urge all parties to establish a 48-hour cultural protection corridor. The Secretariat will deploy a monitoring mission within 72 hours.", "mentioned_countries": ["IND"], "authority_citation": "WHC-1972 Art.11.4 — Emergency Inscription, Heritage in Danger"},
    ],
    "arms_race": [
        {"speaker": "USA", "stance": "oppose", "text": "The United States calls for immediate restraint. An arms race benefits no one at this table except those who manufacture weapons. Our partners expect leadership, and we will provide it.", "mentioned_countries": ["RUS", "CHN"], "authority_citation": None},
        {"speaker": "CHN", "stance": "modify", "text": "China proposes a multilateral de-escalation framework. Unilateral demands will not produce stability. We call for an emergency Security Council session before any further military movements.", "mentioned_countries": ["USA", "RUS"], "authority_citation": None},
        {"speaker": "RUS", "stance": "support", "text": "Russia's military posture is defensive. We note that NATO expansion is the root cause of this spiral. We support de-escalation only when our legitimate security interests are recognized.", "mentioned_countries": ["USA"], "authority_citation": None},
        {"speaker": "UNESCO", "stance": "mediate", "text": "Under Hague-1954 Art.4 — Respect for Cultural Property in Conflict, I invoke the obligation of all parties to protect civilian cultural sites. Military installations near heritage zones require immediate verification of compliance.", "mentioned_countries": [], "authority_citation": "Hague-1954 Art.4 — Respect for Cultural Property in Conflict"},
    ],
    "trade_war": [
        {"speaker": "CHN", "stance": "oppose", "text": "China firmly opposes unilateral economic coercion. These sanctions violate WTO principles and damage the multilateral trading system that all nations depend upon.", "mentioned_countries": ["USA"], "authority_citation": None},
        {"speaker": "USA", "stance": "support", "text": "These are targeted, lawful measures in response to documented violations of international trade rules. Our partners stand with us. This is not coercion — this is accountability.", "mentioned_countries": ["CHN"], "authority_citation": None},
        {"speaker": "IND", "stance": "neutral", "text": "India calls for restraint and dialogue. We are deeply concerned by the supply chain disruption affecting our manufacturers. We urge both parties to return to the negotiating table.", "mentioned_countries": ["USA", "CHN"], "authority_citation": None},
        {"speaker": "SAU", "stance": "modify", "text": "The Kingdom proposes an energy stabilization framework that decouples commodity markets from the bilateral dispute. All parties benefit from stable energy prices regardless of political disagreements.", "mentioned_countries": ["USA", "CHN"], "authority_citation": None},
    ],
    "cultural_destruction": [
        {"speaker": "UNESCO", "stance": "mediate", "text": "Under UNSC-Res-2347 — Heritage Destruction as War Crime, I note that deliberate destruction of cultural sites constitutes a war crime under international law. The Secretariat has documented 3 verified incidents. I am requesting Security Council action.", "mentioned_countries": [], "authority_citation": "UNSC-Res-2347 — Heritage Destruction as War Crime"},
        {"speaker": "USA", "stance": "support", "text": "The United States fully supports UNESCO's assessment. Deliberate cultural destruction is a war crime and we will not stand idly by while humanity's heritage is weaponized.", "mentioned_countries": [], "authority_citation": None},
        {"speaker": "RUS", "stance": "modify", "text": "Russia supports heritage protection in principle. However, we require independent verification before any accusations are formalized. We propose a joint monitoring mission under OSCE, not NATO.", "mentioned_countries": ["USA"], "authority_citation": None},
    ],
    "heritage_at_risk": [
        {"speaker": "UNESCO", "stance": "mediate", "text": "Under WHC-1972 Art.11 — List of World Heritage in Danger, I am initiating emergency procedures for three sites in the affected zone. I urge all parties to fund the UNESCO Emergency Cultural Response Fund immediately.", "mentioned_countries": [], "authority_citation": "WHC-1972 Art.11 — List of World Heritage in Danger"},
        {"speaker": "IND", "stance": "support", "text": "India is the host nation for two of the three sites in danger. We fully support UNESCO's emergency procedures and will commit national resources to site protection immediately.", "mentioned_countries": [], "authority_citation": None},
        {"speaker": "USA", "stance": "support", "text": "The United States supports the UNESCO emergency fund and will contribute $50 million in immediate response financing. Heritage preservation is a shared responsibility of the international community.", "mentioned_countries": ["IND"], "authority_citation": None},
    ],
}

# ── Utterance model ────────────────────────────────────────────────────────────

def make_utterance(agent_id: str, raw: dict, step: int, agents_config: list[dict]) -> dict:
    """Convert raw LLM JSON response to a DebateUtterance dict."""
    agent = next((a for a in agents_config if a["id"] == agent_id), None)
    tint = agent.get("tint", "#ffffff") if agent else "#ffffff"
    name = agent.get("name", agent_id) if agent else agent_id
    return {
        "step": step,
        "speakerId": agent_id,
        "speakerName": name,
        "speakerTint": tint,
        "text": raw.get("text", ""),
        "stance": raw.get("stance", "neutral"),
        "mentionedCountries": raw.get("mentioned_countries", []),
        "authorityCitation": raw.get("authority_citation"),
        "isAuthoritative": raw.get("authority_citation") is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pnlDeltas": {},  # computed server-side after utterance
    }

# ── Orchestrator ───────────────────────────────────────────────────────────────

class DebateOrchestrator:
    AGENTS_CONFIG = [
        {"id": "USA",    "name": "United States",  "tint": "#3b82f6"},
        {"id": "CHN",    "name": "China",           "tint": "#ef4444"},
        {"id": "RUS",    "name": "Russia",          "tint": "#8b5cf6"},
        {"id": "IND",    "name": "India",           "tint": "#f59e0b"},
        {"id": "DPRK",   "name": "North Korea",     "tint": "#ef4444"},
        {"id": "SAU",    "name": "Saudi Arabia",    "tint": "#22c55e"},
        {"id": "UNESCO", "name": "UNESCO",          "tint": "#14b8a6"},
    ]

    def __init__(self):
        self.loader = PersonaLoader()
        self._round_counter = 0
        self._last_debate_step = -DEBATE_RATE_LIMIT_STEPS  # allow first debate immediately
        api_key = os.environ.get("GROQ_API_KEY", "")
        self._groq_client = AsyncGroq(api_key=api_key) if GROQ_AVAILABLE and api_key else None
        self._use_live = bool(self._groq_client)
        print(f"DebateOrchestrator initialized. Live Groq: {self._use_live}")

    def can_run_debate(self, current_step: int) -> bool:
        """Rate limit: max 1 debate per DEBATE_RATE_LIMIT_STEPS simulation steps."""
        return (current_step - self._last_debate_step) >= DEBATE_RATE_LIMIT_STEPS

    async def _call_groq(self, system_prompt: str, agent_id: str) -> dict:
        """Call Groq API for a single agent utterance."""
        if not self._groq_client:
            raise RuntimeError("Groq client not initialized")

        start = time.time()
        response = await self._groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=MAX_TOKENS_PER_AGENT,
            temperature=0.85,
            response_format={"type": "json_object"},
            timeout=GROQ_TIMEOUT,
        )
        elapsed = time.time() - start
        raw_text = response.choices[0].message.content

        # V4: Validate and sanitize LLM response
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            parsed = {
                "text": f"{agent_id} pauses, considering the proposal.",
                "stance": "neutral",
                "mentioned_countries": [],
                "authority_citation": None,
            }

        # V4: Enforce schema — only allow known keys
        sanitized = {
            "text": str(parsed.get("text", ""))[:MAX_UTTERANCE_TEXT_LEN],
            "stance": parsed.get("stance", "neutral") if parsed.get("stance") in VALID_STANCES else "neutral",
            "mentioned_countries": [
                c for c in parsed.get("mentioned_countries", [])
                if isinstance(c, str) and len(c) <= 10
            ][:10],
            "authority_citation": str(parsed.get("authority_citation", ""))[:200] if parsed.get("authority_citation") else None,
        }
        sanitized["_latency_ms"] = int(elapsed * 1000)
        sanitized["_model"] = GROQ_MODEL
        return sanitized

    def _get_canned(self, crisis_type: str, agent_order: list[str]) -> list[dict]:
        """Return canned debate utterances for a crisis type."""
        base = CANNED_DEBATES.get(crisis_type, CANNED_DEBATES["natural_disaster"])
        # Reorder to match requested agent_order (skip agents not in canned set)
        ordered = []
        for agent_id in agent_order:
            match = next((u for u in base if u["speaker"] == agent_id), None)
            if match:
                ordered.append(match)
        # Fill remaining from base not yet included
        for u in base:
            if u["speaker"] not in agent_order:
                ordered.append(u)
        return ordered

    async def run_debate_round(
        self,
        crisis_type: str,
        crisis_description: str,
        mappo_action: str,
        world_state: dict,
        involvement: dict,
        force_canned: bool = False,
    ) -> AsyncIterator[dict]:
        """
        Yields DebateUtterance dicts one by one as agents speak.

        Args:
            crisis_type: e.g. 'natural_disaster', 'arms_race'
            crisis_description: human-readable description
            mappo_action: e.g. 'AID_DISPATCH_COORDINATED'
            world_state: current world state snapshot
            involvement: {'involved': [...], 'peripheral': [...], 'uninvolved': [...]}
            force_canned: bypass live Groq path and always use canned script

        Yields:
            DebateUtterance dicts
        """
        self._round_counter += 1
        round_id = f"round_{self._round_counter:04d}"
        current_step = world_state.get("step", 0)
        self._last_debate_step = current_step

        # Determine speaker order: involved first, then peripheral, skip uninvolved (not UNESCO)
        involved = involvement.get("involved", [])
        peripheral = involvement.get("peripheral", [])
        speaker_order = [a for a in involved if a != "UNESCO"] + \
                        [a for a in peripheral if a != "UNESCO"] + \
                        ["UNESCO"]

        use_live = self._use_live and not force_canned
        round_utterances = []

        if use_live:
            # ── LIVE GROQ PATH ──────────────────────────────────────────────
            # P2: pre-fetch each agent's last-24h GDELT headlines (cached 60s,
            # auto-falls back to static seeds if GDELT unreachable) and inject into
            # their persona prompt. Cheap because cache + parallel HTTP.
            tasks = {}
            for agent_id in speaker_order:
                inv_level = "involved" if agent_id in involved else "peripheral"
                live_events = get_country_events(agent_id) if _LIVE_EVENTS_OK else []
                sentiment = get_country_sentiment(agent_id) if _LIVE_EVENTS_OK else None
                prompt = self.loader.build_system_prompt(
                    agent_id=agent_id,
                    world_state=world_state,
                    mappo_proposed_action=mappo_action,
                    crisis_type=crisis_type,
                    crisis_description=crisis_description,
                    involvement_level=inv_level,
                    live_events=live_events,
                    public_sentiment=sentiment,
                )
                tasks[agent_id] = asyncio.create_task(self._call_groq(prompt, agent_id))

            # Yield utterances as they complete
            for agent_id in speaker_order:
                try:
                    raw = await asyncio.wait_for(tasks[agent_id], timeout=GROQ_TIMEOUT + 2)
                except Exception as e:
                    print(f"⚠️  Groq failed for {agent_id}: {e}. Falling back to canned.")
                    canned = self._get_canned(crisis_type, [agent_id])
                    raw = canned[0] if canned else {
                        "text": f"{agent_id} remains silent.",
                        "stance": "neutral",
                        "mentioned_countries": [],
                        "authority_citation": None,
                    }

                utterance = make_utterance(agent_id, raw, current_step, self.AGENTS_CONFIG)
                utterance["roundId"] = round_id
                utterance["_live"] = True
                round_utterances.append(utterance)

                # Update relationship matrix based on stance
                for mentioned in raw.get("mentioned_countries", []):
                    self.loader.update_relationship(agent_id, mentioned, raw.get("stance", "neutral"))

                yield utterance
                await asyncio.sleep(0.1)  # slight delay for frontend streaming effect

        else:
            # ── CANNED FALLBACK PATH ────────────────────────────────────────
            canned = self._get_canned(crisis_type, speaker_order)
            for raw in canned:
                agent_id = raw["speaker"]
                utterance = make_utterance(agent_id, raw, current_step, self.AGENTS_CONFIG)
                utterance["roundId"] = round_id
                utterance["_live"] = False
                round_utterances.append(utterance)
                yield utterance
                await asyncio.sleep(0.8)  # match frontend debate-sim.jsx tick speed

        # ── Audit log ──────────────────────────────────────────────────────
        vote_tally = self._compute_vote_tally(round_utterances)
        audit_record = {
            "round_id": round_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "crisis_type": crisis_type,
            "mappo_action": mappo_action,
            "simulation_step": current_step,
            "live": use_live,
            "utterances": [
                {"speaker": u["speakerId"], "stance": u["stance"], "text": u["text"][:100] + "..."}
                for u in round_utterances
            ],
            "vote_tally": vote_tally,
        }
        _append_audit(audit_record)

        # Persist updated relationships
        self.loader.save_relationships()

    async def run_multi_round_debate(
        self,
        crisis_type: str,
        crisis_description: str,
        mappo_action: str,
        world_state: dict,
        involvement: dict,
        force_canned: bool = False,
        max_rounds: int = 3,
    ) -> AsyncIterator[dict]:
        """
        Yields SSE-shaped event dicts for a full multi-round debate.

        Event types yielded (keyed by _event):
            round_start  — round metadata + involvement
            utterance    — standard DebateUtterance dict
            round_end    — round vote tally
            debate_end   — final tally + rhetoric alert
        """
        max_rounds = max(1, min(max_rounds, 5))
        all_utterances: list[dict] = []
        final_tally = None
        current_involvement = dict(involvement)
        final_round = 0

        for round_num in range(1, max_rounds + 1):
            final_round = round_num
            crisis_country = self._infer_crisis_country(crisis_type)

            yield {
                "_event": "round_start",
                "round_number": round_num,
                "max_rounds": max_rounds,
                "crisis_type": crisis_type,
                "crisis_country": crisis_country,
                "involvement": current_involvement,
                "heritage_at_risk": self._get_heritage_at_risk(crisis_type),
            }

            round_utterances: list[dict] = []
            if round_num == 1:
                speaker_order = self._build_speaker_order(current_involvement)
            else:
                speaker_order = self._build_rebuttal_order(current_involvement, all_utterances)

            use_live = self._use_live and not force_canned
            current_step = world_state.get("step", 0) + round_num - 1
            self._round_counter += 1
            round_id = f"round_{self._round_counter:04d}"

            if use_live:
                tasks: dict[str, asyncio.Task] = {}
                prior_context = self._summarize_prior_utterances(all_utterances, round_num)
                for agent_id in speaker_order:
                    inv_level = self._get_involvement_level(agent_id, current_involvement)
                    live_events = get_country_events(agent_id) if _LIVE_EVENTS_OK else []
                    sentiment = get_country_sentiment(agent_id) if _LIVE_EVENTS_OK else None
                    prompt = self.loader.build_system_prompt(
                        agent_id=agent_id,
                        world_state={**world_state, "step": current_step, "prior_debate": prior_context},
                        mappo_proposed_action=mappo_action,
                        crisis_type=crisis_type,
                        crisis_description=crisis_description,
                        involvement_level=inv_level,
                        live_events=live_events,
                        public_sentiment=sentiment,
                    )
                    tasks[agent_id] = asyncio.create_task(self._call_groq(prompt, agent_id))

                for agent_id in speaker_order:
                    try:
                        raw = await asyncio.wait_for(tasks[agent_id], timeout=GROQ_TIMEOUT + 2)
                    except Exception as e:
                        print(f"⚠️  Groq failed for {agent_id} round {round_num}: {e}")
                        canned = self._get_canned(crisis_type, [agent_id])
                        raw = canned[0] if canned else {
                            "text": f"{agent_id} reserves their position.",
                            "stance": "neutral", "mentioned_countries": [], "authority_citation": None,
                        }

                    utterance = make_utterance(agent_id, raw, current_step, self.AGENTS_CONFIG)
                    utterance["roundId"] = round_id
                    utterance["roundNumber"] = round_num
                    utterance["_live"] = True
                    round_utterances.append(utterance)

                    for mentioned in raw.get("mentioned_countries", []):
                        self.loader.update_relationship(agent_id, mentioned, raw.get("stance", "neutral"))

                    yield {"_event": "utterance", **utterance}
                    await asyncio.sleep(0.1)
            else:
                canned = self._get_canned(crisis_type, speaker_order)
                for raw in canned:
                    agent_id = raw["speaker"]
                    utterance = make_utterance(agent_id, raw, current_step, self.AGENTS_CONFIG)
                    utterance["roundId"] = round_id
                    utterance["roundNumber"] = round_num
                    utterance["_live"] = False
                    round_utterances.append(utterance)
                    yield {"_event": "utterance", **utterance}
                    await asyncio.sleep(0.8)

            all_utterances.extend(round_utterances)
            round_tally = self._compute_vote_tally(round_utterances)
            final_tally = round_tally

            yield {
                "_event": "round_end",
                "round_number": round_num,
                "round_id": round_id,
                "vote_tally": round_tally,
            }

            current_involvement = self._promote_mentioned_nations(current_involvement, round_utterances)

            if not self._should_continue_debate(round_tally, round_num, max_rounds):
                break

            await asyncio.sleep(0.3)

        _append_audit({
            "type": "multi_round_debate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "crisis_type": crisis_type,
            "total_rounds": final_round,
            "final_tally": final_tally,
            "total_utterances": len(all_utterances),
        })
        self.loader.save_relationships()

        rhetoric_alert = self.detect_rhetoric_cold_war(all_utterances, "USA", "RUS") or \
                         self.detect_rhetoric_cold_war(all_utterances, "USA", "CHN")

        yield {
            "_event": "debate_end",
            "vote_tally": final_tally,
            "total_rounds": final_round,
            "rhetoric_alert": rhetoric_alert,
        }

    # ── Multi-round helpers ──────────────────────────────────────────────

    def _build_speaker_order(self, involvement: dict) -> list[str]:
        involved = involvement.get("involved", [])
        peripheral = involvement.get("peripheral", [])
        return [a for a in involved if a != "UNESCO"] + \
               [a for a in peripheral if a != "UNESCO"] + \
               ["UNESCO"]

    def _build_rebuttal_order(self, involvement: dict, prior_utterances: list[dict]) -> list[str]:
        """Rebuttal rounds: oppose/modify speakers first, then others, then UNESCO."""
        rebuttal_speakers: list[str] = []
        seen: set[str] = set()
        for u in reversed(prior_utterances):
            sid = u["speakerId"]
            if sid == "UNESCO" or sid in seen:
                continue
            if u["stance"] in ("oppose", "modify"):
                rebuttal_speakers.append(sid)
                seen.add(sid)

        all_agents = self._build_speaker_order(involvement)
        remaining = [a for a in all_agents if a not in seen and a != "UNESCO"]
        return rebuttal_speakers + remaining + ["UNESCO"]

    def _get_involvement_level(self, agent_id: str, involvement: dict) -> str:
        if agent_id in involvement.get("involved", []):
            return "involved"
        if agent_id in involvement.get("peripheral", []):
            return "peripheral"
        return "uninvolved"

    def _summarize_prior_utterances(self, utterances: list[dict], current_round: int) -> str:
        if not utterances:
            return ""
        lines = []
        for u in utterances[-10:]:
            lines.append(f"[{u['speakerId']}] ({u['stance'].upper()}): {u['text'][:120]}...")
        return f"Prior debate (last {len(lines)} statements before round {current_round}):\n" + "\n".join(lines)

    def _should_continue_debate(self, tally: dict, round_num: int, max_rounds: int) -> bool:
        if round_num >= max_rounds:
            return False
        oppose = tally.get("oppose", 0)
        support = tally.get("support", 0)
        modify = tally.get("modify", 0)
        if oppose == 0 and modify == 0:
            return False
        if oppose > support:
            return True
        if modify >= 2:
            return True
        return False

    def _promote_mentioned_nations(self, involvement: dict, utterances: list[dict]) -> dict:
        """Promote nations between involvement tiers based on debate mentions."""
        mention_counts: dict[str, int] = {}
        for u in utterances:
            for m in u.get("mentionedCountries", []):
                mention_counts[m] = mention_counts.get(m, 0) + 1

        involved = list(involvement.get("involved", []))
        peripheral = list(involvement.get("peripheral", []))
        uninvolved = list(involvement.get("uninvolved", []))

        for agent_id, count in mention_counts.items():
            if agent_id in uninvolved and count >= 2:
                uninvolved.remove(agent_id)
                peripheral.append(agent_id)
            elif agent_id in peripheral:
                agent_stance = None
                for u in utterances:
                    if u["speakerId"] == agent_id:
                        agent_stance = u["stance"]
                        break
                if agent_stance in ("oppose", "support") and count >= 2:
                    peripheral.remove(agent_id)
                    involved.append(agent_id)

        return {"involved": involved, "peripheral": peripheral, "uninvolved": uninvolved}

    def _infer_crisis_country(self, crisis_type: str) -> str | None:
        crisis_country_map = {
            "natural_disaster": "IND",
            "arms_race": "DPRK",
            "trade_war": "CHN",
            "cultural_destruction": "IND",
            "heritage_at_risk": "IND",
        }
        return crisis_country_map.get(crisis_type)

    def _get_heritage_at_risk(self, crisis_type: str) -> list[dict]:
        if crisis_type not in ("natural_disaster", "cultural_destruction", "heritage_at_risk"):
            return []
        return [
            {"countryId": "IND", "siteName": "Sundarbans Mangrove System", "riskScore": 0.82},
            {"countryId": "IND", "siteName": "Mahabodhi Temple Complex", "riskScore": 0.45},
            {"countryId": "IND", "siteName": "Kaziranga National Park", "riskScore": 0.31},
        ]

    def _compute_vote_tally(self, utterances: list[dict]) -> dict:
        """Compute vote tally from utterances (UNESCO excluded from vote)."""
        tally = {"support": 0, "oppose": 0, "modify": 0, "neutral": 0}
        for u in utterances:
            if u["speakerId"] == "UNESCO":
                continue  # UNESCO is non-voting
            stance = u.get("stance", "neutral")
            if stance in tally:
                tally[stance] += 1
        tally["passed"] = tally["support"] > tally["oppose"]
        tally["total_voters"] = sum(tally[k] for k in ["support", "oppose", "modify", "neutral"])
        return tally

    def detect_rhetoric_cold_war(
        self,
        utterances: list[dict],
        agent_a: str,
        agent_b: str,
        threshold: int = 4,
    ) -> dict | None:
        """
        Detect if two agents have exchanged N consecutive OPPOSE stances.
        Returns alert dict if detected, None otherwise.
        """
        consecutive = 0
        for u in utterances:
            if u["speakerId"] in [agent_a, agent_b] and u["stance"] == "oppose":
                # Check if the other agent is mentioned
                if any(other in u.get("mentionedCountries", []) for other in [agent_a, agent_b] if other != u["speakerId"]):
                    consecutive += 1
                    if consecutive >= threshold:
                        rel_ab = self.loader.get_relationship_row(agent_a).get(agent_b, 0.0)
                        rel_ba = self.loader.get_relationship_row(agent_b).get(agent_a, 0.0)
                        index = abs(rel_ab - rel_ba) / 2 + (consecutive - threshold) * 0.1
                        return {
                            "agents": [agent_a, agent_b],
                            "count": consecutive,
                            "topic": "bilateral stance polarization",
                            "index": round(min(1.0, index), 2),
                        }
            else:
                consecutive = 0
        return None


# ── UNESCO Mediator Helper ─────────────────────────────────────────────────────

class UNESCOMediator:
    """Selects relevant authority articles for UNESCO utterances."""

    def __init__(self):
        self.loader = PersonaLoader()

    def get_articles_for_crisis(self, crisis_type: str, limit: int = 3) -> list[dict]:
        return self.loader.get_authority_articles(crisis_type, limit=limit)

    def build_authority_scope_strings(self, crisis_type: str) -> list[str]:
        articles = self.get_articles_for_crisis(crisis_type)
        return [a["short_cite"] for a in articles]

    def is_within_mandate(self, crisis_type: str) -> bool:
        within_mandate_domains = {"heritage", "education", "culture", "bioethics"}
        articles = self.get_articles_for_crisis(crisis_type)
        if not articles:
            return False
        domains = {a.get("domain", "") for a in articles}
        return bool(domains & within_mandate_domains)


# ── Main (test) ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    async def test():
        orchestrator = DebateOrchestrator()
        involvement = {
            "involved": ["USA", "IND", "SAU"],
            "peripheral": ["CHN", "RUS", "UNESCO"],
            "uninvolved": ["DPRK"],
        }

        print("Running multi-round canned debate for natural_disaster...")
        async for event in orchestrator.run_multi_round_debate(
            crisis_type="natural_disaster",
            crisis_description="Severe cyclone hits Bay of Bengal; UNESCO heritage sites at risk.",
            mappo_action="AID_DISPATCH_COORDINATED",
            world_state={"step": 40, "welfare_index": 0.42, "active_crises": ["natural_disaster"]},
            involvement=involvement,
            force_canned=True,
            max_rounds=2,
        ):
            etype = event.get("_event", "utterance")
            if etype == "round_start":
                print(f"\n── ROUND {event['round_number']}/{event['max_rounds']} ──")
            elif etype == "utterance":
                print(f"  [{event['speakerId']}] [{event['stance'].upper()}] {event['text'][:80]}...")
            elif etype == "round_end":
                print(f"  ── round {event['round_number']} tally: {event['vote_tally']}")
            elif etype == "debate_end":
                print(f"\n✓ DEBATE END — total rounds: {event['total_rounds']}")
                print(f"  Final tally: {event['vote_tally']}")
                if event.get("rhetoric_alert"):
                    print(f"  ⚠ Rhetoric alert: {event['rhetoric_alert']}")

        print(f"\n✓ debate_orchestrator.py self-test passed")
        print(f"Audit log written to: {AUDIT_LOG}")

    asyncio.run(test())
