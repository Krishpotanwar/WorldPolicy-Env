"""
graders.py — WorldPolicy-Env V6.1 MOGSR (Multi-Objective Geopolitical Stability Reward).

The 4-layer reward stack:
    R_final = R_immediate + γ·V(s') + λ·A_counterfactual + β·R_robust

where R_immediate is a crisis-adaptive weighted sum of 5 normalized objectives:
    Security, Diplomacy, Coalition, Economic, Humanitarian
plus hard constraint penalties (nuclear escalation, charter violations, etc.).

The pitch (per plan): "Our agents are not rewarded for passing resolutions; they
are rewarded for improving global system stability under multi-objective geopolitical
constraints." This is what makes the reward research-credible vs +1/-1.

Usage:
    grader = CrisisResolutionGrader()
    raw_score = grader.score(round_result, crisis_type="natural_disaster")  # in [-1, 2]

The environment's step() also normalizes the cumulative episode reward to [0, 1] for
the /grader endpoint via the DisasterMan formula:
    normalized = (tanh(cumul_reward / max_steps * 2) + 1) / 2
"""

from __future__ import annotations

import copy
import itertools
import math
from typing import Any, Dict, List

# ── Crisis-adaptive weight tables ─────────────────────────────────────────────
# S=Security, D=Diplomacy, C=Coalition, E=Economic, H=Humanitarian; rows sum to 1.0
# (penalties are added on top, so weights govern only the positive multi-objective term)

CRISIS_WEIGHTS: Dict[str, Dict[str, float]] = {
    "war_outbreak":         {"S": 0.45, "D": 0.25, "C": 0.10, "E": 0.10, "H": 0.20},
    "arms_race":            {"S": 0.45, "D": 0.20, "C": 0.15, "E": 0.05, "H": 0.15},
    "military_escalation":  {"S": 0.40, "D": 0.25, "C": 0.15, "E": 0.05, "H": 0.15},
    "trade_war":            {"S": 0.10, "D": 0.20, "C": 0.15, "E": 0.40, "H": 0.15},
    "natural_disaster":     {"S": 0.10, "D": 0.20, "C": 0.15, "E": 0.10, "H": 0.45},
    "cultural_destruction": {"S": 0.05, "D": 0.20, "C": 0.10, "E": 0.10, "H": 0.55},
    "heritage_at_risk":     {"S": 0.05, "D": 0.20, "C": 0.10, "E": 0.10, "H": 0.55},
    "sanctions":            {"S": 0.15, "D": 0.30, "C": 0.15, "E": 0.30, "H": 0.10},
    "DEFAULT":              {"S": 0.30, "D": 0.20, "C": 0.15, "E": 0.20, "H": 0.15},
}

# Hard penalty table — applied as an additive negative; keys must match
# constraint_violations strings emitted by the orchestrator/environment.
HARD_PENALTIES: Dict[str, float] = {
    "nuclear_escalation":   -1.0,   # catastrophic — episode terminates
    "illegal_aggression":   -0.5,
    "contradictory_policy": -0.2,   # agent flips a prior stance without justification
    "coalition_collapse":   -0.3,   # formed coalition broke in same round
    "un_charter_violation": -0.4,   # UN flagged action as mandate breach
}

GAMMA = 0.95   # long-horizon value discount
LAMBDA = 0.30  # counterfactual advantage weight
BETA = 0.10    # shock-robustness weight


# ── Per-objective scorers (each returns a value in [0, 1]) ────────────────────

def _security_score(r: Dict[str, Any]) -> float:
    """S: penalize escalation, reward de-escalation and ceasefire signals."""
    delta_conflict = float(r.get("conflict_delta", 0.0))           # >0 = more conflict
    pr_escalation = float(r.get("pr_escalation", 0.0))             # [0,1]
    pr_ceasefire = float(r.get("pr_ceasefire", 0.0))               # [0,1]
    spillover_risk = float(r.get("spillover_risk", 0.0))           # [0,1]
    raw = -delta_conflict - pr_escalation + pr_ceasefire - spillover_risk * 0.5
    return max(0.0, min(1.0, (raw + 2.0) / 4.0))


def _diplomacy_score(r: Dict[str, Any]) -> float:
    """D: efficiency of resolution — fast peaceful outcomes rewarded most."""
    success = float(r.get("resolution_success", r.get("vote_passed", False)))
    steps_taken = max(1, int(r.get("negotiation_steps", 1)))
    max_steps = max(1, int(r.get("max_negotiation_steps", 5)))
    efficiency = success * (1.0 - (steps_taken - 1) / max_steps)
    return max(0.0, min(1.0, efficiency))


def _coalition_score(r: Dict[str, Any]) -> float:
    """C: dynamic coherence from live relationship matrix (not hardcoded alliances)."""
    coalition = set(r.get("coalition_members", []))
    rel_matrix: Dict[str, Dict[str, float]] = r.get("relationship_matrix", {})
    if len(coalition) < 2:
        return 0.0
    size_score = min(len(coalition) / 6.0, 1.0)
    pairs = list(itertools.combinations(coalition, 2))
    trust_vals = []
    for a, b in pairs:
        trust = rel_matrix.get(a, {}).get(b, rel_matrix.get(b, {}).get(a, 0.0))
        trust_vals.append((trust + 1.0) / 2.0)
    trust_coherence = sum(trust_vals) / max(len(trust_vals), 1)
    durability = float(r.get("coalition_durability", 0.7))   # orchestrator-tracked stability
    return max(0.0, min(1.0, size_score * trust_coherence * durability))


def _economic_score(r: Dict[str, Any]) -> float:
    """E: welfare-based resilience, penalized by shocks and sanctions costs."""
    growth = float(r.get("gdp_growth_rate", 0.0))
    inflation_shock = float(r.get("inflation_shock", 0.0))
    trade_disruption = float(r.get("trade_disruption", 0.0))
    sanctions_cost = float(r.get("sanctions_cost", 0.0))
    raw = growth - inflation_shock - trade_disruption * 0.5 - sanctions_cost * 0.3
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))


def _humanitarian_score(r: Dict[str, Any]) -> float:
    """H: civilian protection + UN mandate adherence."""
    civilian_harm = float(r.get("civilian_harm_index", 0.0))
    refugee_risk = float(r.get("refugee_displacement_risk", 0.0))
    law_compliance = float(r.get("law_compliance_score", 0.5))
    raw = -civilian_harm - refugee_risk * 0.7 + law_compliance * 1.3
    return max(0.0, min(1.0, (raw + 1.7) / 3.0))


def _compute_penalties(r: Dict[str, Any]) -> float:
    """Sum hard-constraint penalties; default per-violation -0.1 if not in table."""
    total = 0.0
    for v in r.get("constraint_violations", []):
        total += HARD_PENALTIES.get(v, -0.1)
    return total


def _future_value(r: Dict[str, Any]) -> float:
    """V(s'): heuristic next-state stability estimate (long-horizon strategic value)."""
    rel_matrix = r.get("next_relationship_matrix", r.get("relationship_matrix", {}))
    if not rel_matrix:
        return 0.5
    all_scores = [v for row in rel_matrix.values() for v in row.values()]
    avg_trust = sum(all_scores) / max(len(all_scores), 1)
    trust_norm = (avg_trust + 1.0) / 2.0
    crisis_resolved = bool(r.get("crisis_resolved", False))
    stability = trust_norm * (1.2 if crisis_resolved else 0.8)
    return max(0.0, min(1.0, stability))


def _counterfactual_advantage(r: Dict[str, Any]) -> float:
    """A = Outcome(action) - Outcome(null_action). Rewards improvement over baseline."""
    baseline = float(r.get("null_action_stability", r.get("prev_stability", 0.5)))
    current = float(r.get("current_stability", 0.5))
    return current - baseline   # signed; can be negative if action made things worse


def _robustness_reward(r: Dict[str, Any]) -> float:
    """R_robust: shock-perturbation performance bonus (defaults to 0 if not measured)."""
    return float(r.get("shock_robustness_score", 0.0))


# ── MOGSR base grader ─────────────────────────────────────────────────────────

class MOGSRGrader:
    """4-layer Multi-Objective Geopolitical Stability Reward grader.

    score(round_result, crisis_type) returns float in [-1.0, 2.0]. Hard
    nuclear-escalation violations short-circuit to immediate-only scoring with
    catastrophic penalty applied — episode should terminate.
    """

    def score(self, round_result: Dict[str, Any], crisis_type: str = "DEFAULT") -> float:
        w = CRISIS_WEIGHTS.get(crisis_type, CRISIS_WEIGHTS["DEFAULT"])

        # Layer 1 — immediate multi-objective
        S = _security_score(round_result)
        D = _diplomacy_score(round_result)
        C = _coalition_score(round_result)
        E = _economic_score(round_result)
        H = _humanitarian_score(round_result)
        P = _compute_penalties(round_result)
        R_immediate = w["S"]*S + w["D"]*D + w["C"]*C + w["E"]*E + w["H"]*H + P

        # Layer 2 — long-horizon strategic value
        R_longterm = GAMMA * _future_value(round_result)

        # Layer 3 — counterfactual advantage over null action
        A = _counterfactual_advantage(round_result)

        # Layer 4 — shock robustness
        R_robust = _robustness_reward(round_result)

        R_final = R_immediate + R_longterm + LAMBDA * A + BETA * R_robust

        # Hard catastrophe override
        if "nuclear_escalation" in round_result.get("constraint_violations", []):
            return max(-1.0, R_immediate + P)

        return max(-1.0, min(2.0, R_final))


# ── Per-task wrappers (referenced by openenv.yaml's task.grader field) ────────

class CrisisResolutionGrader(MOGSRGrader):
    """Default task grader — uses all 5 objectives with crisis-adaptive weights."""

    def score(self, round_result: Dict[str, Any], crisis_type: str | None = None) -> float:  # type: ignore[override]
        ct = crisis_type or round_result.get("crisis_type", "DEFAULT")
        return super().score(round_result, crisis_type=ct)


class CoalitionGrader(MOGSRGrader):
    """Coalition-formation task — upweights C and D; downweights S/E/H proportionally."""

    def score(self, round_result: Dict[str, Any], crisis_type: str | None = None) -> float:  # type: ignore[override]
        ct = crisis_type or round_result.get("crisis_type", "DEFAULT")
        base = CRISIS_WEIGHTS.get(ct, CRISIS_WEIGHTS["DEFAULT"]).copy()
        new_C, new_D = 0.40, 0.30
        # Downweight others proportionally to preserve sum ≈ 1.0
        leftover = 1.0 - new_C - new_D
        old_others_sum = base["S"] + base["E"] + base["H"]
        if old_others_sum > 0:
            scale = leftover / old_others_sum
            base = {"S": base["S"]*scale, "D": new_D, "C": new_C,
                    "E": base["E"]*scale, "H": base["H"]*scale}
        else:
            base = {"S": leftover/3, "D": new_D, "C": new_C, "E": leftover/3, "H": leftover/3}

        # Inject the ad-hoc weight table just for this scoring call
        sentinel = "_coalition_tmp"
        CRISIS_WEIGHTS[sentinel] = base
        try:
            return super().score(round_result, crisis_type=sentinel)
        finally:
            CRISIS_WEIGHTS.pop(sentinel, None)


class DiplomacyGrader(MOGSRGrader):
    """Diplomacy task — derives resolution_success from stance_change efficiency."""

    def score(self, round_result: Dict[str, Any], crisis_type: str | None = None) -> float:  # type: ignore[override]
        ct = crisis_type or round_result.get("crisis_type", "DEFAULT")
        r = copy.deepcopy(round_result)
        initial_opp = int(r.get("initial_opposition_count", 0))
        if initial_opp == 0:
            r.setdefault("resolution_success", True)
        else:
            stance_changes = int(r.get("stance_changes", 0))
            r["resolution_success"] = (stance_changes / initial_opp) >= 0.5
        return super().score(r, crisis_type=ct)


# ── Catalogue used by /grader endpoint ────────────────────────────────────────

TASK_GRADERS: Dict[str, type[MOGSRGrader]] = {
    "task_1": CrisisResolutionGrader,
    "task_2": CoalitionGrader,
    "task_3": CrisisResolutionGrader,   # arms-race uses default 5-objective shape
    "crisis_resolution": CrisisResolutionGrader,
    "coalition_formation": CoalitionGrader,
    "diplomatic_negotiation": DiplomacyGrader,
}


def normalize_episode_reward(cumulative: float, max_steps: int) -> float:
    """DisasterMan compression formula → [0, 1]."""
    if max_steps <= 0:
        return 0.5
    return (math.tanh(cumulative / max_steps * 2.0) + 1.0) / 2.0


def grade_episode(rounds: List[Dict[str, Any]], task: str = "task_1") -> Dict[str, Any]:
    """Score a finished episode across all rounds. Used by /grader endpoint."""
    from collections import Counter
    cls = TASK_GRADERS.get(task, CrisisResolutionGrader)
    grader = cls()
    if not rounds:
        return {"task": task, "raw_score": 0.0, "normalized": 0.5, "step_count": 0}
    raw = sum(grader.score(r, crisis_type=r.get("crisis_type", "DEFAULT")) for r in rounds)
    avg = raw / len(rounds)

    # Anti-gaming: penalize if same action_type used in > 60% of steps
    action_types = [r.get("action_type", "") for r in rounds if r.get("action_type")]
    diversity_penalty = 0.0
    if len(action_types) >= 3:
        most_common_count = Counter(action_types).most_common(1)[0][1]
        if most_common_count / len(action_types) > 0.6:
            diversity_penalty = -0.3
            raw += diversity_penalty

    normalized = normalize_episode_reward(raw, max(len(rounds), 1))
    return {
        "task": task,
        "raw_score": round(raw, 4),
        "avg_per_round": round(avg, 4),
        "normalized": round(normalized, 4),
        "step_count": len(rounds),
        "diversity_penalty": round(diversity_penalty, 4),
    }
