"""
crisis_types.py — Single source of truth for the 13 crisis types used across
server.py, live_data.py, debate_orchestrator.py, and tasks.py.

Every crisis type lives here with its display name, GDELT keywords, and
default description. Other modules import CRISIS_REGISTRY and ALLOWED_CRISIS_TYPES.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet

CRISIS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "natural_disaster": {
        "display": "Natural Disaster",
        "gdelt_keywords": "cyclone earthquake tsunami flood disaster humanitarian",
        "default_description": "Severe natural disaster triggers mass displacement and infrastructure collapse.",
    },
    "arms_race": {
        "display": "Arms Race",
        "gdelt_keywords": "nuclear weapons arms race military buildup missile",
        "default_description": "Accelerating arms buildup across multiple regions raises nuclear escalation risk.",
    },
    "trade_war": {
        "display": "Trade War",
        "gdelt_keywords": "trade war tariffs sanctions economic coercion",
        "default_description": "Escalating tariff barriers and retaliatory sanctions disrupt global supply chains.",
    },
    "cultural_destruction": {
        "display": "Cultural Destruction",
        "gdelt_keywords": "heritage UNESCO destruction cultural artifact",
        "default_description": "Deliberate destruction of cultural sites constitutes a potential war crime.",
    },
    "heritage_at_risk": {
        "display": "Heritage at Risk",
        "gdelt_keywords": "world heritage site endangered cultural risk",
        "default_description": "Multiple World Heritage sites face imminent danger from conflict or disaster.",
    },
    "education_collapse": {
        "display": "Education Collapse",
        "gdelt_keywords": "education crisis school closure literacy dropout",
        "default_description": "Mass school closures and educational infrastructure collapse threaten a generation.",
    },
    "military_escalation": {
        "display": "Military Escalation",
        "gdelt_keywords": "military escalation troops border conflict",
        "default_description": "Military buildup near contested borders risks triggering mutual defense obligations.",
    },
    "war_outbreak": {
        "display": "War Outbreak",
        "gdelt_keywords": "war outbreak invasion military attack",
        "default_description": "Armed conflict has erupted, causing civilian casualties and displacement.",
    },
    "sanctions": {
        "display": "Sanctions Regime",
        "gdelt_keywords": "economic sanctions embargo financial",
        "default_description": "Broad economic sanctions impact civilian populations and global trade flows.",
    },
    "gdp_shock": {
        "display": "GDP Shock",
        "gdelt_keywords": "economic crisis recession GDP decline financial collapse",
        "default_description": "A sudden GDP contraction triggers liquidity crisis and threatens global depression.",
    },
    "bloc_formation": {
        "display": "Bloc Formation",
        "gdelt_keywords": "alliance bloc formation geopolitical alignment multipolar",
        "default_description": "Rival geopolitical blocs are forming, fragmenting the international order.",
    },
    "alliance_rupture": {
        "display": "Alliance Rupture",
        "gdelt_keywords": "alliance fracture NATO withdrawal security pact breakdown",
        "default_description": "A major security alliance has fractured, creating strategic uncertainty.",
    },
    "regime_change": {
        "display": "Regime Change",
        "gdelt_keywords": "regime change coup government transition political upheaval",
        "default_description": "Political upheaval raises questions of sovereignty and governance continuity.",
    },
}

ALLOWED_CRISIS_TYPES: FrozenSet[str] = frozenset(CRISIS_REGISTRY.keys())

CRISIS_KEYWORDS: Dict[str, str] = {
    k: v["gdelt_keywords"] for k, v in CRISIS_REGISTRY.items()
}


def get_crisis_display(crisis_type: str) -> str:
    entry = CRISIS_REGISTRY.get(crisis_type)
    return entry["display"] if entry else crisis_type.replace("_", " ").title()


def get_crisis_description(crisis_type: str) -> str:
    entry = CRISIS_REGISTRY.get(crisis_type)
    return entry["default_description"] if entry else f"{crisis_type.replace('_', ' ').title()} demands council action."
