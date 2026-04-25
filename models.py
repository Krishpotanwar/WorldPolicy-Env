"""
models.py — WorldPolicy-Env V6.1 OpenEnv data models.

Action / Observation / State subclasses for the OpenEnv-compliant geopolitical RL
environment. These are imported by environment.py, client.py, server.py, and inference.py.

The base classes (Action, Observation, State) come from openenv-core. Per SDK source:
- Action.metadata is a free-form dict.
- Observation.{done,reward,metadata} are inherited; subclasses add domain fields.
- State.{episode_id,step_count} are inherited; we extend with task + max_steps + total_reward.

Pydantic v2 with extra="forbid" on Action/Observation (SDK config), extra="allow" on State.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field

# ── Allowlists (mirrored in graders.py + inference.py) ────────────────────────

VALID_ACTION_TYPES = {
    "propose_resolution",
    "form_coalition",
    "veto",
    "abstain",
    "invoke_article",
    "sanction",
}
VALID_AGENT_IDS = {"USA", "CHN", "RUS", "IND", "DPRK", "SAU", "UNESCO"}


# ── Action ────────────────────────────────────────────────────────────────────

class WorldPolicyAction(Action):
    """A single diplomatic action taken by one agent in a debate round.

    The action drives the LLM speech generation in DebateOrchestrator and the
    reward calculation in MOGSRGrader. `description` is fed into the system prompt
    as the agent's policy justification.
    """

    agent_id: str = Field(
        ...,
        description="One of USA, CHN, RUS, IND, DPRK, SAU, UNESCO",
        max_length=10,
    )
    action_type: str = Field(
        ...,
        description="propose_resolution | form_coalition | veto | abstain | invoke_article | sanction",
        max_length=32,
    )
    target: Optional[str] = Field(
        default=None,
        description="Target agent_id (None for self-directed actions like abstain)",
        max_length=10,
    )
    description: str = Field(
        default="",
        description="Policy justification fed to LLM for speech generation",
        max_length=500,  # cap prevents reward hacking via long descriptions
    )


# ── Observation ───────────────────────────────────────────────────────────────

class WorldPolicyObservation(Observation):
    """World snapshot after a step (or initial state after reset).

    Inherits done, reward, metadata from Observation. Adds the geopolitical
    state agents need to plan their next move.
    """

    country_pnl: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Per-country economic state: {agent_id: {gdp, military, welfare, ...}}",
    )
    relationship_matrix: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Bilateral trust scores in [-1.0, 1.0]: {agent_id: {agent_id: float}}",
    )
    current_crisis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Active crisis: {type, headline, severity, source, ...}",
    )
    debate_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Last N utterances (capped to 6 in environment.py)",
    )
    active_agent: str = Field(
        default="USA",
        description="Whose turn it is to act in the next step",
    )
    step_count: int = Field(
        default=0,
        ge=0,
        description="Steps taken in this episode (mirrors State.step_count)",
    )
    stability_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="PyTorch StabilityScorer estimate of current world stability",
    )
    last_round_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Slim per-step round info that survives OpenEnv wire serialization "
            "(metadata is stripped). Keys: vote_passed, vote_tally, coalition_members, "
            "constraint_violations, current_stability, null_action_stability, "
            "crisis_type, normalized_so_far, cumulative_reward."
        ),
    )
    max_steps: int = Field(
        default=5,
        ge=1,
        description="Episode horizon for the current task — exposed as a domain field "
                    "because OpenEnv strips Observation.metadata on the wire.",
    )
    task: str = Field(
        default="task_1",
        description="Task ID for the current episode (mirrors State.task on the wire).",
    )


# ── State ─────────────────────────────────────────────────────────────────────

class WorldPolicyState(State):
    """Full server-side episode state (richer than Observation; not transmitted to client by default).

    OpenEnv exposes State via GET /state for inspection. Our server includes
    task config and accumulated reward so grader endpoint can recompute.
    """

    task: str = Field(default="task_1", description="Task ID from tasks.py")
    max_steps: int = Field(default=5, ge=1, description="Max steps for this episode")
    total_reward: float = Field(default=0.0, description="Cumulative episode reward")
    done: bool = Field(default=False, description="Episode terminated")
    crisis_type: str = Field(default="natural_disaster")
    rounds: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="All round_result dicts emitted by the orchestrator (used by /grader)",
    )
