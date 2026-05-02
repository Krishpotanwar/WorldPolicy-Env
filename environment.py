"""
environment.py — WorldPolicy-Env V6.1 OpenEnv environment.

WorldPolicyEnvironment wraps DebateOrchestrator + MOGSRGrader + StabilityScorer
behind the OpenEnv `Environment` interface. One instance per WebSocket session
(create_app handles factory instantiation), so per-session state lives on
`self._task_state` / `self._state` — no `session_id` query-string dance needed.

Per the real SDK contract:
    reset(seed=None, episode_id=None, **kwargs) -> Observation
    step(action) -> Observation         # reward + done are FIELDS on the Observation
    @property state -> State

Concurrency: SUPPORTS_CONCURRENT_SESSIONS = True. Each WS client gets its own
WorldPolicyEnvironment instance, each with its own DebateOrchestrator. The shared
PersonaLoader is process-singleton (read-mostly; relationships.json writes use the
atomic save introduced in `3_antigravityLOG.md` LOG-019 V5).

The reset() / step() flow:
    reset(): pick task → fetch live crisis (with fallback) → load WB P&L baselines
             (with fallback) → snapshot relationship matrix → seed initial obs.
    step():  run one debate round through the orchestrator → derive feature deltas
             → compute null-action stability for counterfactual baseline → call
             MOGSRGrader → return updated Observation with reward + done.
"""

from __future__ import annotations

import asyncio
import math
import uuid
from typing import Any, Dict, List, Optional

from openenv.core.env_server.interfaces import Environment

from debate_orchestrator import DebateOrchestrator
from graders import (
    TASK_GRADERS,
    CrisisResolutionGrader,
    HARD_PENALTIES,
    normalize_episode_reward,
)
from models import (
    VALID_ACTION_TYPES,
    VALID_AGENT_IDS,
    WorldPolicyAction,
    WorldPolicyObservation,
    WorldPolicyState,
)
from persona_loader import PersonaLoader
from pytorch_scorer import score_stability
from tasks import get_task

# Lazy live-data imports — these may fail at import time on some HF Spaces builds
# if `requests` is missing for some reason; we guard so env still boots.
try:
    from live_data import (  # type: ignore
        get_country_events,
        get_live_crisis,
        get_wb_baseline,
    )
    _LIVE_DATA_OK = True
except Exception as _exc:  # pragma: no cover
    _LIVE_DATA_OK = False
    _LIVE_DATA_ERR = str(_exc)
    def get_live_crisis(crisis_type: str) -> Dict[str, Any]:  # type: ignore
        return {"type": crisis_type, "live": False, "headline": None, "fallback_reason": _LIVE_DATA_ERR}
    def get_wb_baseline(agent_id: str) -> Dict[str, float]:  # type: ignore
        return {"gdp": 1e12, "military": 1e10, "welfare": 50.0}
    def get_country_events(agent_id: str) -> List[str]:  # type: ignore
        return []


AGENT_IDS_NON_UN = ["USA", "CHN", "RUS", "IND", "DPRK", "SAU"]
DEFAULT_TASK = "task_1"


# ── Environment ───────────────────────────────────────────────────────────────

class WorldPolicyEnvironment(Environment):
    """OpenEnv-compliant geopolitical RL environment.

    One instance per WebSocket session (create_app factory mode).
    All per-episode mutable state lives on the instance; nothing is global.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    # ── lifecycle ────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__()
        self._loader = PersonaLoader()
        self._orchestrator = DebateOrchestrator()
        # `task_state` is a free-form dict tracking the current episode.
        self._task_state: Dict[str, Any] = {}
        self._state = WorldPolicyState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            task=DEFAULT_TASK,
            max_steps=5,
            total_reward=0.0,
            done=False,
        )
        self._grader = CrisisResolutionGrader()

    # ── reset ────────────────────────────────────────────────────────────────

    # Crisis pool for procedural generation (seed-driven variety)
    _CRISIS_POOL = [
        "natural_disaster", "trade_war", "arms_race", "military_escalation",
        "war_outbreak", "cultural_destruction", "sanctions", "bloc_formation",
        "regime_change", "heritage_at_risk",
    ]
    # Severity levels affect initial relationship matrix warmth
    _SEVERITY_REL_BIAS = {
        "low": 0.15, "medium": 0.0, "high": -0.15, "critical": -0.30,
    }

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task: str = DEFAULT_TASK,
        crisis_type: Optional[str] = None,
        severity: Optional[str] = None,
        **kwargs: Any,
    ) -> WorldPolicyObservation:
        """Start a new episode.

        Args:
            seed: integer seed for procedural episode generation. Same seed +
                  task → same crisis_type and severity → reproducible episodes.
            episode_id: optional caller-supplied ID; UUID minted otherwise.
            task: one of task_1 / task_2 / task_3.
            crisis_type: override crisis type (ignores seed if set).
            severity: one of low / medium / high / critical — biases relationship
                      matrix and civilian harm signals.
        """
        task_cfg = get_task(task)

        # Procedural generation: seed selects crisis type + severity
        if crisis_type is None:
            if seed is not None:
                crisis_type = self._CRISIS_POOL[seed % len(self._CRISIS_POOL)]
            else:
                crisis_type = task_cfg["crisis_type"]

        if severity is None:
            severities = ["low", "medium", "high", "critical"]
            if seed is not None:
                severity = severities[(seed // len(self._CRISIS_POOL)) % len(severities)]
            else:
                severity = "medium"

        crisis = get_live_crisis(crisis_type)

        # Per-country P&L baselines — World Bank (with fallback).
        country_pnl: Dict[str, Dict[str, float]] = {}
        for aid in AGENT_IDS_NON_UN:
            country_pnl[aid] = get_wb_baseline(aid)
        # UN is heritage-only; carries a flat seed.
        country_pnl["UN"] = {"heritage": 1.0, "influence": 0.5}

        # Relationship matrix snapshot — persistent across sessions, mutated by step()
        rel_matrix = {a: dict(self._loader.get_relationship_row(a)) for a in self._loader._relationships}
        if not rel_matrix:
            rel_matrix = {
                a: {b: 0.0 for b in AGENT_IDS_NON_UN + ["UN"] if b != a}
                for a in AGENT_IDS_NON_UN + ["UN"]
            }

        # Apply severity bias: high severity = colder relationships = harder episode
        rel_bias = self._SEVERITY_REL_BIAS.get(severity, 0.0)
        if rel_bias != 0.0:
            rel_matrix = {
                a: {b: max(-1.0, min(1.0, v + rel_bias)) for b, v in row.items()}
                for a, row in rel_matrix.items()
            }

        # Initial stability via PyTorch scorer
        prev_stability = score_stability(country_pnl, rel_matrix)

        # Reset task state
        self._task_state = {
            "task": task,
            "task_cfg": task_cfg,
            "crisis_type": crisis_type,
            "severity": severity,
            "crisis": crisis,
            "country_pnl": country_pnl,
            "relationship_matrix": rel_matrix,
            "debate_history": [],
            "active_agent": task_cfg["active_agents"][0],
            "prev_stability": prev_stability,
            "rounds": [],
            "coalition_members": set(),
        }

        # Reset OpenEnv state
        eid = episode_id or str(uuid.uuid4())
        self._state = WorldPolicyState(
            episode_id=eid,
            step_count=0,
            task=task,
            max_steps=int(task_cfg["max_steps"]),
            total_reward=0.0,
            done=False,
            crisis_type=crisis_type,
            rounds=[],
        )

        return WorldPolicyObservation(
            done=False,
            reward=0.0,
            country_pnl=country_pnl,
            relationship_matrix=rel_matrix,
            current_crisis=crisis,
            debate_history=[],
            active_agent=self._task_state["active_agent"],
            step_count=0,
            stability_score=prev_stability,
            max_steps=self._state.max_steps,
            task=task,
            metadata={
                "task": task,
                "max_steps": self._state.max_steps,
                "target_reward_range": task_cfg.get("target_reward_range", [0.4, 0.8]),
                "live_data_layer": _LIVE_DATA_OK,
                "episode_id": eid,
            },
        )

    # ── step ─────────────────────────────────────────────────────────────────

    def step(
        self,
        action: WorldPolicyAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> WorldPolicyObservation:
        """Execute one diplomatic action; returns the resulting Observation."""
        # Defensive: if reset() wasn't called, do an emergency reset.
        if not self._task_state:
            self.reset()

        if self._state.done:
            # Sticky-done: re-emit the last observation with done=True, reward=0.
            return self._observation(reward=0.0, done=True, info={"error": "episode already done"})

        # Validate action
        if action.action_type not in VALID_ACTION_TYPES:
            # Reward-hacking guard: invalid action types get small penalty + advance step
            self._state.step_count += 1
            self._state.total_reward += -0.1
            done = self._state.step_count >= self._state.max_steps
            self._state.done = done
            return self._observation(
                reward=-0.1, done=done,
                info={"error": f"invalid action_type '{action.action_type}'", "valid": sorted(VALID_ACTION_TYPES)},
            )

        if action.agent_id not in VALID_AGENT_IDS:
            self._state.step_count += 1
            self._state.total_reward += -0.1
            done = self._state.step_count >= self._state.max_steps
            self._state.done = done
            return self._observation(
                reward=-0.1, done=done,
                info={"error": f"invalid agent_id '{action.agent_id}'"},
            )

        # ── Run one debate round driven by this action ──────────────────────
        round_result = self._run_round(action)

        # ── Compute counterfactual baseline (null action: abstain by same agent) ─
        null_action = WorldPolicyAction(
            agent_id=action.agent_id,
            action_type="abstain",
            target=None,
            description="counterfactual baseline (no policy action)",
        )
        # Don't actually mutate state — synthesize a hypothetical round from current snapshot
        null_round = self._synthesize_null_round(null_action)
        round_result["null_action_stability"] = float(null_round["current_stability"])
        round_result["prev_stability"] = float(self._task_state["prev_stability"])

        # ── MOGSR scoring ───────────────────────────────────────────────────
        task_id = self._state.task
        grader_cls = TASK_GRADERS.get(task_id, CrisisResolutionGrader)
        grader = grader_cls()
        reward = float(grader.score(round_result, crisis_type=round_result.get("crisis_type", "DEFAULT")))

        # ── Persist mutations ───────────────────────────────────────────────
        self._task_state["country_pnl"] = round_result["pnl_after"]
        self._task_state["relationship_matrix"] = round_result["rel_after"]
        self._task_state["debate_history"].extend(round_result.get("utterances", []))
        self._task_state["prev_stability"] = float(round_result["current_stability"])
        self._task_state["coalition_members"] = set(round_result.get("coalition_members", []))
        self._task_state["rounds"].append(round_result)
        self._task_state["active_agent"] = self._next_agent(action.agent_id)

        self._state.step_count += 1
        self._state.total_reward += reward
        self._state.rounds = self._task_state["rounds"]

        # Termination conditions
        hit_max = self._state.step_count >= self._state.max_steps
        crisis_resolved = bool(round_result.get("crisis_resolved", False))
        catastrophe = "nuclear_escalation" in round_result.get("constraint_violations", [])
        done = hit_max or crisis_resolved or catastrophe
        self._state.done = done

        return self._observation(
            reward=reward,
            done=done,
            info={
                "round": {
                    "vote_passed": round_result.get("vote_passed"),
                    "vote_tally": round_result.get("vote_tally"),
                    "coalition_members": list(round_result.get("coalition_members", [])),
                    "constraint_violations": round_result.get("constraint_violations", []),
                    "current_stability": round_result["current_stability"],
                    "null_action_stability": round_result["null_action_stability"],
                    "crisis_type": round_result.get("crisis_type"),
                },
                "step": self._state.step_count,
                "max_steps": self._state.max_steps,
                "cumulative_reward": self._state.total_reward,
                "normalized_so_far": normalize_episode_reward(
                    self._state.total_reward, self._state.max_steps,
                ),
            },
        )

    @property
    def state(self) -> WorldPolicyState:
        return self._state

    # ── helpers ──────────────────────────────────────────────────────────────

    def _observation(
        self,
        reward: float,
        done: bool,
        info: Optional[Dict[str, Any]] = None,
    ) -> WorldPolicyObservation:
        s = self._task_state
        # OpenEnv strips Observation.metadata on the wire, so the meaningful
        # per-step bits (round summary, cumulative reward, normalized score) are
        # promoted onto a domain field that survives serialization.
        info = info or {}
        last_round = info.get("round")
        summary = None
        if last_round is not None:
            summary = {
                **last_round,
                "step": self._state.step_count,
                "max_steps": self._state.max_steps,
                "cumulative_reward": float(self._state.total_reward),
                "normalized_so_far": float(info.get("normalized_so_far", 0.0)),
            }
        return WorldPolicyObservation(
            done=done,
            reward=reward,
            country_pnl=s.get("country_pnl", {}),
            relationship_matrix=s.get("relationship_matrix", {}),
            current_crisis=s.get("crisis", {}),
            debate_history=s.get("debate_history", [])[-6:],
            active_agent=s.get("active_agent", "USA"),
            step_count=self._state.step_count,
            stability_score=float(s.get("prev_stability", 0.5)),
            last_round_summary=summary,
            max_steps=self._state.max_steps,
            task=self._state.task,
            metadata=info,  # kept for in-process callers; OpenEnv may drop it on wire
        )

    def _next_agent(self, last: str) -> str:
        active = self._task_state["task_cfg"]["active_agents"]
        if last in active:
            i = active.index(last)
            return active[(i + 1) % len(active)]
        return active[0]

    def _run_round(self, action: WorldPolicyAction) -> Dict[str, Any]:
        """Run one debate round through the orchestrator and synthesize round_result.

        The orchestrator is async; this is sync code so we drive it with asyncio.run
        on a fresh event loop OR loop.run_until_complete if one already exists.
        """
        crisis_type = self._task_state["crisis_type"]
        active_agents = list(self._task_state["task_cfg"]["active_agents"])
        involved = [a for a in active_agents if a != "UN"][:3]
        peripheral = [a for a in active_agents if a not in involved]
        if "UN" not in involved + peripheral and "UN" in active_agents:
            peripheral.append("UN")
        uninvolved = [a for a in (AGENT_IDS_NON_UN + ["UN"]) if a not in active_agents]

        # Drive the async orchestrator
        coro = self._collect_utterances(
            crisis_type=crisis_type,
            crisis_description=self._task_state["crisis"].get("headline")
                or f"{crisis_type.replace('_', ' ').title()} demands council action.",
            mappo_action=f"{action.action_type.upper()}::{action.target or 'self'}::{action.description[:80]}",
            world_state={
                "step": self._state.step_count,
                "welfare_index": self._task_state["prev_stability"],
                "active_crises": [crisis_type],
                "policy_action": action.action_type,
                "policy_target": action.target,
            },
            involvement={"involved": involved, "peripheral": peripheral, "uninvolved": uninvolved},
        )
        utterances = self._sync_run(coro)

        # Compute vote tally + derived signals
        vote_tally = self._orchestrator._compute_vote_tally(utterances)
        vote_passed = bool(vote_tally.get("passed"))

        coalition_members = self._derive_coalition(utterances, action)
        coalition_durability = self._coalition_durability(coalition_members)

        # Apply a tiny synthetic effect on country_pnl + relationships (orchestrator
        # already mutates relationships during live calls; for canned/synth we apply a
        # heuristic delta so the reward layer sees motion).
        pnl_after = self._apply_pnl_deltas(action, vote_passed)
        rel_after = {a: dict(self._loader.get_relationship_row(a)) for a in self._loader._relationships}

        # PyTorch stability after the action
        current_stability = score_stability(pnl_after, rel_after)

        # Constraint violations
        violations: List[str] = []
        if action.action_type == "sanction" and action.target == "UN":
            violations.append("un_charter_violation")
        if crisis_type == "arms_race" and action.action_type == "veto" and action.target == "UN":
            violations.append("contradictory_policy")
        # Hard escalation trigger from task_3
        trig = self._task_state["task_cfg"].get("escalation_trigger")
        if trig and self._state.step_count + 1 == trig["step"] and action.action_type != "form_coalition":
            # If no coalition formed by escalation step → DPRK triggers nuclear
            if not coalition_members:
                violations.append(trig.get("action", "nuclear_escalation"))

        return {
            "round_id": f"round_{self._state.step_count + 1:04d}",
            "crisis_type": crisis_type,
            "vote_passed": vote_passed,
            "vote_tally": vote_tally,
            "utterances": utterances,
            "coalition_members": list(coalition_members),
            "coalition_durability": coalition_durability,
            "constraint_violations": violations,
            "pnl_after": pnl_after,
            "rel_after": rel_after,
            "relationship_matrix": self._task_state["relationship_matrix"],
            "next_relationship_matrix": rel_after,
            "current_stability": current_stability,
            "crisis_resolved": vote_passed and not violations,
            # ── Grader signals wired from actual state ──────────────────────
            # conflict_delta: positive = stability dropped = more conflict
            "conflict_delta": float(self._task_state["prev_stability"] - current_stability),
            "negotiation_steps": self._state.step_count + 1,
            "max_negotiation_steps": self._state.max_steps,
            # law_compliance: authoritative UN citation = higher compliance
            "law_compliance_score": (
                0.95 if any(u.get("isAuthoritative") for u in utterances) else
                0.7 if vote_passed else 0.4
            ),
            # civilian_harm: crisis type + violations drive severity
            "civilian_harm_index": self._compute_civilian_harm(crisis_type, vote_passed, violations),
            # refugee risk: war/arms crises displace people; resolved crises reduce risk
            "refugee_displacement_risk": self._compute_refugee_risk(crisis_type, vote_passed, violations),
            # economic signals from actual PnL deltas
            "gdp_growth_rate": self._compute_gdp_delta(pnl_after),
            "inflation_shock": max(0.0, self._compute_gdp_delta(pnl_after) * -0.5),
            # trade disruption: sanctions cause disruption, coalition reduces it
            "trade_disruption": 0.4 if action.action_type == "sanction" else (0.05 if coalition_members else 0.2),
            "sanctions_cost": 0.25 if action.action_type == "sanction" else 0.0,
            # escalation signals from stability change + violations
            "pr_ceasefire": 0.75 if vote_passed and crisis_type in {"arms_race", "war_outbreak", "military_escalation"} else 0.25,
            "pr_escalation": min(1.0, 0.5 + len(violations) * 0.2 + max(0.0, self._task_state["prev_stability"] - current_stability)),
            "spillover_risk": 0.6 if violations else (0.15 if vote_passed else 0.35),
            # anti-gaming tracking
            "action_type": action.action_type,
        }

    def _synthesize_null_round(self, null_action: WorldPolicyAction) -> Dict[str, Any]:
        """Lightweight counterfactual: estimate stability if the agent had abstained.

        We don't actually run the LLM (would double cost). Instead we compute the
        stability score on the unchanged P&L + relationship snapshot.
        """
        pnl = self._task_state["country_pnl"]
        rel = self._task_state["relationship_matrix"]
        return {"current_stability": score_stability(pnl, rel)}

    async def _collect_utterances(
        self,
        crisis_type: str,
        crisis_description: str,
        mappo_action: str,
        world_state: Dict[str, Any],
        involvement: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        async for u in self._orchestrator.run_debate_round(
            crisis_type=crisis_type,
            crisis_description=crisis_description,
            mappo_action=mappo_action,
            world_state=world_state,
            involvement=involvement,
            force_canned=False,   # use live if Groq key set, else canned
        ):
            out.append(u)
        return out

    def _sync_run(self, coro):
        """Run a coroutine synchronously; safe whether or not an event loop is active."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context (e.g. step_async) — caller should use
                # step_async; here we fall back to a thread-local new loop.
                return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=60)
        except RuntimeError:
            pass
        return asyncio.run(coro)

    def _derive_coalition(
        self,
        utterances: List[Dict[str, Any]],
        action: WorldPolicyAction,
    ) -> set[str]:
        """A coalition forms when 2+ non-UN agents support the same proposal."""
        if action.action_type != "form_coalition" and action.action_type != "propose_resolution":
            return set()
        supporters: set[str] = set()
        for u in utterances:
            if u.get("speakerId") == "UN":
                continue
            if u.get("stance") == "support":
                supporters.add(u["speakerId"])
        if len(supporters) >= 2:
            return supporters
        return set()

    def _coalition_durability(self, members: set[str]) -> float:
        """Average pairwise trust among members → [0,1] durability proxy."""
        if len(members) < 2:
            return 0.0
        rels = self._task_state["relationship_matrix"]
        pairs = []
        members_list = list(members)
        for i, a in enumerate(members_list):
            for b in members_list[i + 1:]:
                t = rels.get(a, {}).get(b, rels.get(b, {}).get(a, 0.0))
                pairs.append((t + 1.0) / 2.0)
        return sum(pairs) / max(len(pairs), 1)

    # Civilian harm by crisis type (base rates)
    _CIVILIAN_HARM_BASE = {
        "war_outbreak": 0.70, "military_escalation": 0.55, "arms_race": 0.30,
        "natural_disaster": 0.50, "trade_war": 0.10, "sanctions": 0.20,
        "cultural_destruction": 0.40, "heritage_at_risk": 0.25,
        "bloc_formation": 0.05, "regime_change": 0.45,
    }
    _REFUGEE_RISK_BASE = {
        "war_outbreak": 0.80, "military_escalation": 0.60, "arms_race": 0.25,
        "natural_disaster": 0.55, "trade_war": 0.05, "sanctions": 0.15,
        "cultural_destruction": 0.35, "heritage_at_risk": 0.20,
        "bloc_formation": 0.03, "regime_change": 0.50,
    }

    def _compute_civilian_harm(self, crisis_type: str, vote_passed: bool, violations: list) -> float:
        base = self._CIVILIAN_HARM_BASE.get(crisis_type, 0.25)
        if vote_passed:
            base *= 0.35
        base += len(violations) * 0.10
        return max(0.0, min(1.0, base))

    def _compute_refugee_risk(self, crisis_type: str, vote_passed: bool, violations: list) -> float:
        base = self._REFUGEE_RISK_BASE.get(crisis_type, 0.20)
        if vote_passed:
            base *= 0.30
        base += len(violations) * 0.12
        return max(0.0, min(1.0, base))

    def _compute_gdp_delta(self, pnl_after: Dict[str, Dict[str, float]]) -> float:
        prev_pnl = self._task_state["country_pnl"]
        deltas = []
        for aid in AGENT_IDS_NON_UN:
            prev_gdp = prev_pnl.get(aid, {}).get("gdp", 1e12)
            curr_gdp = pnl_after.get(aid, {}).get("gdp", prev_gdp)
            if prev_gdp > 0:
                deltas.append((curr_gdp - prev_gdp) / prev_gdp)
        return sum(deltas) / max(len(deltas), 1) if deltas else 0.0

    def _apply_pnl_deltas(
        self,
        action: WorldPolicyAction,
        vote_passed: bool,
    ) -> Dict[str, Dict[str, float]]:
        """Apply small deterministic deltas to per-country P&L.

        These are cosmetic for the reward layer (real economic modelling is out of
        scope) but keep `current_stability` from staying flat across the episode.
        """
        pnl = {a: dict(v) for a, v in self._task_state["country_pnl"].items()}
        gdp_factor = 1.005 if vote_passed else 0.995
        for aid, row in pnl.items():
            if "gdp" in row:
                row["gdp"] = row["gdp"] * gdp_factor
        # Acting agent gets a bigger swing
        if action.agent_id in pnl and "gdp" in pnl[action.agent_id]:
            pnl[action.agent_id]["gdp"] *= (1.01 if vote_passed else 0.99)
        return pnl


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    env = WorldPolicyEnvironment()
    obs = env.reset(task="task_1")
    print(f"reset: active={obs.active_agent} stability={obs.stability_score:.3f} "
          f"crisis_live={obs.current_crisis.get('live', False)}")
    action = WorldPolicyAction(
        agent_id="USA",
        action_type="propose_resolution",
        target="IND",
        description="Coordinate aid dispatch under UN mandate.",
    )
    obs2 = env.step(action)
    print(f"step1: reward={obs2.reward:.3f} done={obs2.done} step_count={obs2.step_count}")
    print(f"  vote_passed={obs2.metadata.get('round', {}).get('vote_passed')}")
    print(f"  coalition={obs2.metadata.get('round', {}).get('coalition_members')}")
    print(f"  stability={obs2.stability_score:.3f}")
    print(f"state: episode={env.state.episode_id} step={env.state.step_count} "
          f"total_reward={env.state.total_reward:.3f} done={env.state.done}")
