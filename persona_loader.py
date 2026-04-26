"""
persona_loader.py — WorldPolicy-Env V6.1
Loads agent persona files and injects them into LLM system prompts.

Usage:
    from persona_loader import PersonaLoader
    loader = PersonaLoader()
    system_prompt = loader.build_system_prompt("USA", world_state, mappo_action, relationship_row, grudge_memory)
"""

import json
from pathlib import Path

PERSONAS_DIR = Path(__file__).parent / "personas"
DATA_DIR = Path(__file__).parent / "data"


class PersonaLoader:
    def __init__(self):
        self._cache: dict[str, str] = {}
        self._relationships: dict = {}
        self._authority: dict = {}
        self._load_relationships()
        self._load_authority()

    def _load_relationships(self):
        rel_path = DATA_DIR / "relationships.json"
        if rel_path.exists():
            with open(rel_path) as f:
                data = json.load(f)
                self._relationships = data.get("matrix", {})
                self._grudge_memory = data.get("grudge_memory", {})
        else:
            self._relationships = {}
            self._grudge_memory = {}

    def _load_authority(self):
        auth_path = DATA_DIR / "un_authority.json"
        if auth_path.exists():
            with open(auth_path) as f:
                data = json.load(f)
                self._authority = {a["id"]: a for a in data.get("articles", [])}
                self._crisis_map = data.get("crisis_to_articles", {})
        else:
            self._authority = {}
            self._crisis_map = {}

    def load_persona(self, agent_id: str) -> str:
        """Load and cache a persona markdown file."""
        if agent_id in self._cache:
            return self._cache[agent_id]

        persona_path = PERSONAS_DIR / f"{agent_id}.md"
        if not persona_path.exists():
            raise FileNotFoundError(f"Persona file not found: {persona_path}")

        text = persona_path.read_text(encoding="utf-8")
        self._cache[agent_id] = text
        return text

    def get_relationship_row(self, agent_id: str) -> dict[str, float]:
        """Get the relationship scores for an agent toward all others."""
        return self._relationships.get(agent_id, {})

    def get_grudge_memory(self, agent_id: str, limit: int = 10) -> list[dict]:
        """Get the last N grudge memory entries for an agent."""
        agent_grudges = self._grudge_memory.get(agent_id, {})
        all_grudges = []
        for target, events in agent_grudges.items():
            for event in events:
                all_grudges.append({**event, "against": target})
        # Sort by step descending, take last N
        all_grudges.sort(key=lambda x: x.get("step", 0), reverse=True)
        return all_grudges[:limit]

    def get_authority_articles(self, crisis_type: str, limit: int = 3) -> list[dict]:
        """Get relevant UN authority articles for a crisis type."""
        article_ids = self._crisis_map.get(crisis_type, [])[:limit]
        return [self._authority[aid] for aid in article_ids if aid in self._authority]

    def build_system_prompt(
        self,
        agent_id: str,
        world_state: dict,
        mappo_proposed_action: str,
        crisis_type: str,
        crisis_description: str,
        involvement_level: str = "involved",
        live_events: list[str] | None = None,
        public_sentiment: dict | None = None,
    ) -> str:
        """
        Build the full system prompt for an agent's LLM call.

        Args:
            agent_id: One of USA, CHN, RUS, IND, DPRK, SAU, UN
            world_state: Current world state snapshot dict
            mappo_proposed_action: The action MAPPO proposed (e.g. 'AID_DISPATCH_COORDINATED')
            crisis_type: Crisis domain (e.g. 'natural_disaster', 'heritage_at_risk')
            crisis_description: Short human-readable description of the crisis
            involvement_level: 'involved' | 'peripheral' | 'uninvolved'

        Returns:
            Full system prompt string for Groq API call
        """
        persona_text = self.load_persona(agent_id)
        rel_row = self.get_relationship_row(agent_id)
        grudges = self.get_grudge_memory(agent_id)

        is_un = agent_id == "UN"
        authority_articles = []
        if is_un:
            authority_articles = self.get_authority_articles(crisis_type)

        # Format relationship row
        rel_lines = "\n".join(
            f"  {target}: {score:+.2f} ({'ALLY' if score > 0.3 else 'ADVERSARY' if score < -0.3 else 'NEUTRAL'})"
            for target, score in rel_row.items()
            if target != agent_id
        )

        # Format grudge memory
        if grudges:
            grudge_lines = "\n".join(
                f"  - {g['against']} OPPOSED you in debate '{g['crisis']}' (step {g['step']})"
                for g in grudges[:5]
            )
            grudge_section = f"GRUDGE MEMORY (reference these patterns in speech when relevant):\n{grudge_lines}"
        else:
            grudge_section = "GRUDGE MEMORY: No prior conflicts recorded."

        # UN authority section
        if is_un and authority_articles:
            authority_lines = "\n".join(
                f"  [{a['id']}] {a['short_cite']}\n    → \"{a['text'][:200]}...\""
                for a in authority_articles
            )
            authority_section = f"""
AUTHORITY CORPUS (cite at least one article in your response):
{authority_lines}

MANDATE REMINDER: You are NON-VOTING. Your stance must be 'mediate' or 'neutral'.
You MUST cite at least one article from the above list using: "Under [short_cite], I invoke..."
"""
        else:
            authority_section = ""

        # P2 — Dynamic persona injection: inject last-24h GDELT headlines per country.
        # Lets DPRK's tone shift when there's actually a nuclear test in the news, etc.
        # Falls through quietly if no events provided (canned debate path).
        if live_events:
            event_lines = "\n".join(f"  - {e}" for e in live_events[:3])
            live_context_section = (
                "=== LIVE CONTEXT (last 24h headlines for your country) ===\n"
                f"{event_lines}\n"
                "Adjust your stance and rhetoric only if these events are directly relevant.\n\n"
            )
        else:
            live_context_section = ""

        # P4 — Public sentiment injection: GDELT tonechart-derived score for the
        # agent's country in the last 24h. Lets agents who are persona-sensitive to
        # public mood (USA / IND / SAU especially) modulate rhetoric. UN and
        # DPRK personas are largely indifferent to this signal but the data is here
        # in case it matters.
        if public_sentiment and public_sentiment.get("live") is not None:
            tone = public_sentiment.get("tone", 0.0)
            label = public_sentiment.get("label", "neutral")
            n = public_sentiment.get("sample_size", 0)
            live_tag = "live" if public_sentiment.get("live") else "fallback estimate"
            sentiment_section = (
                "=== PUBLIC SENTIMENT (last 24h, GDELT tone — about your country) ===\n"
                f"  tone={tone:+.2f}  label={label}  sample_n={n}  ({live_tag})\n"
                "If your persona is sensitive to public mood, account for this; otherwise hold to your principles.\n\n"
            )
        else:
            sentiment_section = ""

        prompt = f"""You are the {agent_id} delegate in the WorldPolicy-Env V6.1 multi-agent debate simulation.

=== YOUR PERSONA ===
{persona_text}

{live_context_section}{sentiment_section}=== CURRENT CRISIS ===
Type: {crisis_type}
Description: {crisis_description}
Your involvement level: {involvement_level}

=== MAPPO PROPOSED ACTION ===
The trained MAPPO policy has proposed: {mappo_proposed_action}
You must respond to this proposal with your stance and reasoning.

=== YOUR RELATIONSHIP MATRIX (current values) ===
{rel_lines}

=== {grudge_section} ===

{authority_section}
=== WORLD STATE SNAPSHOT ===
Step: {world_state.get('step', 0)}
Global welfare index: {world_state.get('welfare_index', 0.5):.2f}
Active crises: {', '.join(world_state.get('active_crises', [crisis_type]))}

=== RESPONSE FORMAT (JSON) ===
Respond with a JSON object in exactly this format:
{{
  "text": "<your speech, 2-4 sentences, in your persona's voice>",
  "stance": "<one of: support | oppose | modify | neutral | mediate>",
  "mentioned_countries": ["<list of country codes mentioned in your speech>"],
  "authority_citation": "<for UN only: the short_cite string of the article cited, or null>"
}}

RULES:
- Stay in character. Use your vocabulary preferences.
- Reference your relationship matrix: be warmer toward allies, colder toward adversaries.
- Reference grudge memory where relevant (max 1 grudge reference per speech).
- {"As UN, you are NON-VOTING — use stance 'mediate'. Cite a real article." if is_un else "Your stance must be one of: support, oppose, modify, neutral."}
- Keep speech 2-4 sentences. Do not break character.
- Return ONLY the JSON object. No markdown, no explanation.
"""
        return prompt

    def update_relationship(
        self,
        from_agent: str,
        to_agent: str,
        stance: str,
        delta_override: float | None = None,
    ):
        """
        Update relationship matrix based on a stance event.
        oppose → -0.05, support → +0.03, modify → 0, neutral/mediate → 0
        """
        if from_agent not in self._relationships:
            self._relationships[from_agent] = {}

        current = self._relationships[from_agent].get(to_agent, 0.0)

        if delta_override is not None:
            delta = delta_override
        elif stance == "oppose":
            delta = -0.05
        elif stance == "support":
            delta = 0.03
        else:
            delta = 0.0

        new_val = max(-1.0, min(1.0, current + delta))
        self._relationships[from_agent][to_agent] = new_val

    def save_relationships(self):
        """Persist updated relationship matrix back to disk.

        V5 FIX: Uses atomic write (tmp file + os.replace) to prevent
        corruption from concurrent writes or mid-write crashes.
        """
        import os
        import tempfile

        rel_path = DATA_DIR / "relationships.json"
        with open(rel_path) as f:
            data = json.load(f)

        data["matrix"] = self._relationships
        data["grudge_memory"] = self._grudge_memory

        # Atomic write: write to temp in same directory, then rename
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, rel_path)  # atomic on POSIX
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


if __name__ == "__main__":
    # Quick test
    loader = PersonaLoader()
    print("Loaded personas:", [p.stem for p in PERSONAS_DIR.glob("*.md")])
    print("\nUSA → RUS relationship:", loader.get_relationship_row("USA").get("RUS"))
    print("UN authority for natural_disaster:", [
        a["short_cite"] for a in loader.get_authority_articles("natural_disaster")
    ])
    print("\nBuilding USA system prompt...")
    prompt = loader.build_system_prompt(
        agent_id="USA",
        world_state={"step": 40, "welfare_index": 0.42, "active_crises": ["natural_disaster"]},
        mappo_proposed_action="AID_DISPATCH_COORDINATED",
        crisis_type="natural_disaster",
        crisis_description="Severe cyclone makes landfall in South Asia, UNESCO heritage sites at risk.",
        involvement_level="involved",
    )
    print(f"Prompt length: {len(prompt)} chars")
    print("✓ persona_loader.py self-test passed")
