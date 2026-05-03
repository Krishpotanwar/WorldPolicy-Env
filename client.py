"""
client.py — WorldPolicy-Env V6.1 OpenEnv client.

The async EnvClient subclass that OpenEnv validators and training scripts use to
talk to the server. Inherits the WebSocket transport from openenv-core. We only
need to teach it how to:
  - serialize WorldPolicyAction → JSON payload
  - parse JSON observation payload → WorldPolicyObservation + StepResult
  - parse JSON state payload → WorldPolicyState

Sync usage (used by inference.py):
    client = WorldPolicyClient(base_url="http://localhost:7860").sync()
    result = client.reset(task="task_1")
    result = client.step(WorldPolicyAction(agent_id="USA", action_type="propose_resolution"))

Docker usage (used by training notebooks):
    client = WorldPolicyClient.from_docker_image("worldpolicy_env:latest")
"""

from __future__ import annotations

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from models import WorldPolicyAction, WorldPolicyObservation, WorldPolicyState


class WorldPolicyClient(EnvClient[WorldPolicyAction, WorldPolicyObservation, WorldPolicyState]):
    """Persistent-WebSocket client for the WorldPolicy environment.

    Example:
        >>> with WorldPolicyClient(base_url="http://localhost:7860") as c:
        ...     r = c.reset()
        ...     print(r.observation.active_agent, r.observation.stability_score)
        ...     act = WorldPolicyAction(agent_id="USA", action_type="form_coalition",
        ...                              target="IND", description="Joint aid framework.")
        ...     r = c.step(act)
        ...     print(r.reward, r.done)
    """

    def _step_payload(self, action: WorldPolicyAction) -> Dict:
        # Pydantic dump (excludes None defaults like `target` if not set; explicit
        # exclude_none=False keeps target=None for downstream parsing clarity).
        return action.model_dump()

    def _parse_result(self, payload: Dict) -> StepResult[WorldPolicyObservation]:
        obs_data = payload.get("observation", {}) or {}
        obs = WorldPolicyObservation(
            done=payload.get("done", obs_data.get("done", False)),
            reward=payload.get("reward", obs_data.get("reward")),
            metadata=obs_data.get("metadata", {}),
            country_pnl=obs_data.get("country_pnl", {}),
            relationship_matrix=obs_data.get("relationship_matrix", {}),
            current_crisis=obs_data.get("current_crisis", {}),
            debate_history=obs_data.get("debate_history", []),
            active_agent=obs_data.get("active_agent", "USA"),
            step_count=obs_data.get("step_count", 0),
            stability_score=obs_data.get("stability_score", 0.5),
            last_round_summary=obs_data.get("last_round_summary"),
            max_steps=obs_data.get("max_steps", 5),
            task=obs_data.get("task", "task_1"),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> WorldPolicyState:
        return WorldPolicyState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task=payload.get("task", "task_1"),
            max_steps=payload.get("max_steps", 5),
            total_reward=payload.get("total_reward", 0.0),
            done=payload.get("done", False),
            crisis_type=payload.get("crisis_type", "natural_disaster"),
            rounds=payload.get("rounds", []),
        )
