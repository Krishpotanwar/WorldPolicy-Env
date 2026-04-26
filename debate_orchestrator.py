"""
debate_orchestrator.py — WorldPolicy-Env V6.1
Orchestrates multi-agent debates with trained model-first backend selection.

Usage:
    orchestrator = DebateOrchestrator()
    async for utterance in orchestrator.run_debate_round(crisis, mappo_action, involvement):
        print(utterance)

Environment variables (live debate):
    WP_DEBATE_BACKEND — optional; one of: mappo | groq | auto (default: mappo)
        mappo: use trained HF model only
        groq : use Groq only
        auto : prefer mappo, fall back to groq
    GROQ_API_KEY — optional; required when backend uses Groq
    HF_TOKEN — optional; required when backend uses trained HF model
"""

import asyncio
import json
import os
import re
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

try:
    from openai import AsyncOpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# HF OpenAI-compatible routing endpoint.
_HF_API_BASE = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
_HF_MODEL    = os.environ.get("MODEL_NAME", "krishpotanwar/worldpolicy-grpo-3b")
_HF_FALLBACK_MODEL = os.environ.get("MODEL_NAME_FALLBACK", "meta-llama/Llama-3.1-8B-Instruct")
_HF_TOKEN    = os.environ.get("HF_TOKEN", "")
_BACKEND_MODE = os.environ.get("WP_DEBATE_BACKEND", "mappo").strip().lower()


def _hf_base_candidates(base_url: str) -> list[str]:
    """Ordered candidate base URLs for HF OpenAI-compatible chat APIs."""
    raw = (base_url or "").strip()
    if not raw:
        return []
    candidates = [raw]
    if "api-inference.huggingface.co" in raw and "router.huggingface.co" not in raw:
        candidates.append("https://router.huggingface.co/v1")
    if not raw.rstrip("/").endswith("/v1"):
        candidates.append(raw.rstrip("/") + "/v1")
    deduped = []
    for c in candidates:
        if c not in deduped:
            deduped.append(c)
    return deduped

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

def _u(speaker, stance, text, mentioned=None, citation=None):
    return {"speaker": speaker, "stance": stance, "text": text,
            "mentioned_countries": mentioned or [], "authority_citation": citation}

CANNED_DEBATES: dict[str, list[dict]] = {
    "natural_disaster": [
        _u("IND", "modify", "India exercises strategic autonomy in accepting bilateral aid. We welcome assistance from all partners but insist on sovereign control of distribution.", ["USA", "CHN"]),
        _u("USA", "support", "The United States is prepared to commit carrier group assets for rapid humanitarian deployment. Our partners can count on our resources and our resolve.", ["IND"]),
        _u("CHN", "modify", "This aid must not be tied to political conditions or military presence. China supports humanitarian assistance through UN mechanisms only. The AIIB stands ready.", ["USA", "IND"]),
        _u("RUS", "oppose", "Russia cannot support operations that position NATO naval assets in the Indian Ocean under humanitarian pretexts. Our counter-proposal routes aid through BRICS channels.", ["USA", "CHN", "IND"]),
        _u("SAU", "support", "The Kingdom commits $2 billion from our sovereign wealth fund, contingent on energy infrastructure receiving priority.", ["IND", "USA"]),
        _u("DPRK", "oppose", "The imperialist powers use disasters to extend military reach. We reject any framework normalizing foreign naval presence near sovereign waters.", ["USA"]),
        _u("UN", "mediate", "Under WHC-1972 Art.11.4, I request emergency inscription of the Sundarbans Mangrove System. All parties must establish a 48-hour cultural protection corridor.", ["IND"], "WHC-1972 Art.11.4 — Emergency Inscription, Heritage in Danger"),
    ],
    "arms_race": [
        _u("USA", "oppose", "The United States calls for immediate restraint. An arms race benefits no one at this table. Our partners expect leadership, and we will provide it.", ["RUS", "CHN"]),
        _u("CHN", "modify", "China proposes a multilateral de-escalation framework. We call for an emergency Security Council session before any further military movements.", ["USA", "RUS"]),
        _u("RUS", "support", "Russia's military posture is defensive. NATO expansion is the root cause of this spiral. We support de-escalation only when our security interests are recognized.", ["USA"]),
        _u("IND", "neutral", "India urges all parties to step back from the brink. We have no interest in choosing sides in a great-power arms race that threatens regional stability.", ["USA", "RUS", "CHN"]),
        _u("DPRK", "support", "The DPRK's sovereign right to self-defense is non-negotiable. We will not disarm while hostile powers maintain forward-deployed nuclear assets on our borders.", ["USA"]),
        _u("SAU", "modify", "The Kingdom calls for a regional security compact. Arms procurement destabilizes energy markets; we propose linking de-escalation milestones to energy cooperation.", ["USA", "RUS"]),
        _u("UN", "mediate", "Under Hague-1954 Art.4, I invoke the obligation of all parties to protect civilian cultural sites. Military installations near heritage zones require immediate compliance verification.", [], "Hague-1954 Art.4 — Respect for Cultural Property in Conflict"),
    ],
    "trade_war": [
        _u("CHN", "oppose", "China firmly opposes unilateral economic coercion. These tariffs violate WTO principles and damage the multilateral trading system all nations depend upon.", ["USA"]),
        _u("USA", "support", "These are targeted, lawful measures in response to documented violations of international trade rules. This is not coercion — this is accountability.", ["CHN"]),
        _u("IND", "neutral", "India calls for restraint. We are deeply concerned by supply chain disruption affecting our manufacturers. We urge both parties back to the negotiating table.", ["USA", "CHN"]),
        _u("SAU", "modify", "The Kingdom proposes an energy stabilization framework decoupling commodity markets from the bilateral dispute. Stable energy prices benefit all parties.", ["USA", "CHN"]),
        _u("RUS", "oppose", "Russia views weaponization of trade as a threat to global economic sovereignty. We stand ready to offer alternative supply chains to affected nations.", ["USA", "CHN"]),
        _u("DPRK", "oppose", "Economic warfare is imperialism by another name. The DPRK has survived decades of sanctions; we advise all nations to build self-reliance.", ["USA"]),
        _u("UN", "mediate", "Under the 2005 Convention on Cultural Expressions, trade restrictions must not impede the free flow of cultural goods and educational materials across borders.", [], "UNESCO 2005 Convention — Protection of Cultural Expressions"),
    ],
    "cultural_destruction": [
        _u("UN", "mediate", "Under UNSC-Res-2347, deliberate destruction of cultural sites constitutes a war crime. The Secretariat has documented 3 verified incidents. I request Security Council action.", [], "UNSC-Res-2347 — Heritage Destruction as War Crime"),
        _u("USA", "support", "The United States fully supports the UN's assessment. Cultural destruction is a war crime and we will not stand idly by while heritage is weaponized."),
        _u("RUS", "modify", "Russia supports heritage protection in principle. However, we require independent verification before accusations are formalized. We propose a joint OSCE monitoring mission.", ["USA"]),
        _u("CHN", "modify", "China insists that cultural protection must not become a pretext for military intervention. We support monitoring through the UN General Assembly framework, not the Security Council.", ["USA", "RUS"]),
        _u("IND", "support", "India, as custodian of one of the world's oldest civilizations, condemns all deliberate destruction of cultural heritage. We pledge technical restoration expertise."),
        _u("SAU", "support", "The Kingdom has invested heavily in heritage preservation domestically. We offer $100 million to the UN Emergency Cultural Fund and call on all parties to do likewise."),
        _u("DPRK", "oppose", "We reject the selective application of cultural protection norms. Where was this outrage when sanctions destroyed our cultural institutions?", ["USA"]),
    ],
    "heritage_at_risk": [
        _u("UN", "mediate", "Under WHC-1972 Art.11, I am initiating emergency procedures for three sites in the affected zone. I urge all parties to fund the Emergency Cultural Response Fund.", [], "WHC-1972 Art.11 — List of World Heritage in Danger"),
        _u("IND", "support", "India hosts two of the three sites in danger. We fully support the UN's emergency procedures and commit national resources to site protection immediately."),
        _u("USA", "support", "The United States supports the UN emergency fund and will contribute $50 million in immediate response financing.", ["IND"]),
        _u("CHN", "support", "China recognizes the urgency. We propose deploying our heritage restoration teams alongside UN monitors. Cultural heritage transcends political differences.", ["IND"]),
        _u("RUS", "modify", "Russia supports heritage protection but questions the scope. Emergency measures must be proportionate and time-limited, not open-ended mandates.", ["IND"]),
        _u("SAU", "support", "The Kingdom pledges $75 million and logistical support for heritage evacuation. Our experience with Mada'in Saleh preservation can inform the response."),
        _u("DPRK", "neutral", "The DPRK notes its own heritage sites receive no international protection. We will abstain unless protections are applied universally.", ["USA"]),
    ],
    "gdp_shock": [
        _u("USA", "support", "The United States proposes coordinated central bank action and emergency trade facilitation. We cannot let a liquidity crisis cascade into a global depression.", ["CHN"]),
        _u("CHN", "modify", "China advocates for structural reform alongside emergency measures. Stimulus without reform repeats the mistakes of 2008. We propose an AIIB-led infrastructure investment package.", ["USA"]),
        _u("IND", "modify", "India's growth trajectory is directly threatened. We call for IMF emergency lending with relaxed conditionality and a moratorium on debt repayment for developing nations.", ["USA", "CHN"]),
        _u("RUS", "oppose", "Russia opposes bailing out speculative economies at the expense of commodity-producing nations. Energy price floors must be part of any stabilization agreement.", ["USA"]),
        _u("SAU", "support", "The Kingdom is prepared to stabilize oil prices through OPEC+ production adjustments. We propose linking energy market stability to the broader recovery framework.", ["RUS"]),
        _u("DPRK", "oppose", "Global financial systems serve imperialist interests. The DPRK has insulated itself from these shocks through self-reliance. We reject externally imposed austerity.", ["USA"]),
        _u("UN", "mediate", "Under the 2015 Recommendation on Museums, economic shocks must not lead to defunding of cultural institutions. I urge emergency cultural sector stabilization.", [], "UNESCO 2015 Recommendation — Protection and Promotion of Museums"),
    ],
    "education_collapse": [
        _u("IND", "support", "India faces the greatest impact — 400 million students affected. We call for emergency digital infrastructure investment and teacher training programs.", ["USA", "CHN"]),
        _u("USA", "support", "The United States commits $2 billion to global education recovery. We propose public-private partnerships leveraging our technology sector.", ["IND"]),
        _u("CHN", "modify", "China supports educational investment but insists on technological sovereignty. No nation should depend on foreign platforms for educating their citizens.", ["USA"]),
        _u("RUS", "modify", "Russia proposes that educational recovery must respect cultural diversity. We reject any standardized Western curriculum imposed under emergency pretexts.", ["USA"]),
        _u("SAU", "support", "The Kingdom pledges $500 million through the Islamic Development Bank for educational infrastructure in affected regions.", ["IND"]),
        _u("DPRK", "oppose", "The DPRK's education system is self-sufficient. We reject foreign educational intervention as cultural imperialism disguised as aid.", ["USA"]),
        _u("UN", "mediate", "Under the 1960 Convention against Discrimination in Education, I declare an education emergency. All parties must guarantee uninterrupted access to quality education.", [], "UNESCO 1960 Convention — Against Discrimination in Education"),
    ],
    "bloc_formation": [
        _u("USA", "oppose", "The formation of rival blocs threatens the rules-based international order. The United States calls on all parties to recommit to multilateral institutions.", ["CHN", "RUS"]),
        _u("CHN", "support", "China supports the right of sovereign nations to form strategic partnerships. BRICS+ is a natural evolution of the multipolar world, not a threat.", ["USA", "RUS"]),
        _u("RUS", "support", "Russia welcomes the diversification of global governance. The era of Western unipolarity is over. New frameworks better represent global interests.", ["USA"]),
        _u("IND", "neutral", "India maintains strategic autonomy. We participate in multiple frameworks — Quad, BRICS, G20 — without accepting exclusionary bloc logic.", ["USA", "CHN", "RUS"]),
        _u("SAU", "modify", "The Kingdom seeks balanced relationships with all blocs. We propose an energy coordination mechanism that transcends bloc boundaries.", ["USA", "CHN"]),
        _u("DPRK", "support", "The DPRK supports any formation that challenges Western hegemony. Self-determination requires breaking free from imperialist alliance structures.", ["USA"]),
        _u("UN", "mediate", "Under the UNESCO Constitution preamble, intellectual solidarity must transcend political division. I urge all blocs to maintain cultural exchange agreements.", [], "UNESCO Constitution — Intellectual and Moral Solidarity"),
    ],
    "alliance_rupture": [
        _u("USA", "oppose", "Alliance fractures embolden adversaries. The United States calls for immediate consultations to repair the damage before strategic competitors exploit the gap.", ["RUS", "CHN"]),
        _u("RUS", "support", "Russia views this rupture as a natural correction. Alliances built on coercion rather than mutual interest are inherently unstable.", ["USA"]),
        _u("CHN", "modify", "China proposes that all parties use this moment to build a new, more inclusive security architecture not dominated by any single power.", ["USA", "RUS"]),
        _u("IND", "neutral", "India notes that alliance politics have historically ignored developing-world concerns. Any new arrangement must include equitable burden-sharing.", ["USA"]),
        _u("SAU", "modify", "The Kingdom is reassessing its own security partnerships. We propose a Gulf security framework with explicit energy security guarantees.", ["USA"]),
        _u("DPRK", "support", "The collapse of imperialist alliances vindicates the DPRK's path of self-reliance. We urge all nations to reject alliance dependency.", ["USA"]),
        _u("UN", "mediate", "Under the 1945 UNESCO Constitution, cooperation in education, science, and culture must continue regardless of military alliance shifts.", [], "UNESCO Constitution Art.1 — Purposes and Functions"),
    ],
    "regime_change": [
        _u("USA", "support", "The United States supports democratic transitions that reflect the will of the people. We offer technical assistance for free and fair elections.", ["RUS", "CHN"]),
        _u("RUS", "oppose", "Russia categorically opposes external interference in sovereign governance. So-called democratic transitions are often destabilization campaigns.", ["USA"]),
        _u("CHN", "oppose", "China reaffirms the principle of non-interference in internal affairs. Each nation must choose its own governance path without external pressure.", ["USA"]),
        _u("IND", "modify", "India supports democratic governance but opposes imposed transitions. We urge all parties to allow organic political evolution and provide humanitarian aid only.", ["USA", "RUS"]),
        _u("SAU", "modify", "The Kingdom emphasizes stability. Regime transitions without institutional continuity create power vacuums that extremist groups exploit.", ["USA"]),
        _u("DPRK", "oppose", "The DPRK condemns regime change as the ultimate violation of sovereignty. We will defend our system against any external threat.", ["USA"]),
        _u("UN", "mediate", "Under the Universal Declaration on Cultural Diversity Art.4, democratic governance must protect cultural rights. I urge all parties to safeguard cultural institutions during transitions.", [], "UNESCO Universal Declaration on Cultural Diversity Art.4"),
    ],
    "military_escalation": [
        _u("USA", "oppose", "The United States demands an immediate ceasefire. Further escalation risks triggering mutual defense obligations across multiple alliances.", ["RUS", "CHN"]),
        _u("RUS", "support", "Russia's military actions are a proportionate response to provocations. We are prepared to de-escalate only when our red lines are respected.", ["USA"]),
        _u("CHN", "modify", "China calls for an emergency ceasefire and direct negotiations. Military solutions create more problems than they solve. We propose Beijing as a neutral venue.", ["USA", "RUS"]),
        _u("IND", "neutral", "India urges maximum restraint. Any military escalation in this region directly threatens our security and economic interests.", ["USA", "RUS"]),
        _u("SAU", "modify", "The Kingdom proposes an energy security corridor agreement as a confidence-building measure. Economic interdependence is the strongest deterrent.", ["USA", "RUS"]),
        _u("DPRK", "support", "The DPRK stands in solidarity with nations defending their sovereignty against imperialist aggression. Military readiness is a sovereign right.", ["USA"]),
        _u("UN", "mediate", "Under Hague-1954 Protocol I, all parties in armed conflict must protect cultural property. I invoke the enhanced protection regime for 12 heritage sites in the conflict zone.", [], "Hague-1954 Protocol I — Protection of Cultural Property in Armed Conflict"),
    ],
    "war_outbreak": [
        _u("USA", "oppose", "The United States calls for an immediate cessation of hostilities. We are activating our diplomatic channels and placing forces on heightened alert as a deterrent.", ["RUS"]),
        _u("RUS", "support", "Russia is acting within its legal right of collective defense. We call on the council to recognize the provocations that led to this point.", ["USA"]),
        _u("CHN", "modify", "China insists on an immediate ceasefire and comprehensive peace talks. War destabilizes the global economy and supply chains that all nations depend on.", ["USA", "RUS"]),
        _u("IND", "neutral", "India calls for restraint from all parties. We are prepared to offer diplomatic mediation but will not be drawn into external conflicts.", ["USA", "RUS"]),
        _u("SAU", "modify", "The Kingdom calls for an emergency OPEC+ session to stabilize energy markets. War-driven oil price spikes harm the global economy indiscriminately.", ["USA", "RUS"]),
        _u("DPRK", "support", "The DPRK notes that Western powers have started far more wars than they have prevented. We stand with nations defending their sovereignty.", ["USA"]),
        _u("UN", "mediate", "Under the 1954 Hague Convention and both Protocols, I invoke emergency cultural protection measures. All combatants must create exclusion zones around heritage sites.", [], "Hague-1954 Convention — Protection of Cultural Property; Second Protocol Art.6"),
    ],
    "sanctions": [
        _u("USA", "support", "These sanctions target specific entities responsible for documented violations. They are precise, proportionate, and consistent with international law.", ["RUS", "CHN"]),
        _u("RUS", "oppose", "Russia rejects unilateral sanctions as economic warfare. These measures hurt civilian populations, not governments. We demand immediate lifting.", ["USA"]),
        _u("CHN", "oppose", "China opposes sanctions imposed outside the UN Security Council framework. Unilateral economic coercion violates the sovereignty of targeted nations.", ["USA"]),
        _u("IND", "modify", "India acknowledges concerns but notes that broad sanctions disrupt our trade relationships. We call for targeted measures that minimize civilian harm.", ["USA", "RUS"]),
        _u("SAU", "modify", "The Kingdom proposes a humanitarian exemption corridor ensuring essential goods — food, medicine, energy — are excluded from any sanctions regime.", ["USA"]),
        _u("DPRK", "oppose", "The DPRK has endured the most severe sanctions on earth for decades. Sanctions are siege warfare against civilian populations.", ["USA"]),
        _u("UN", "mediate", "Under the 1970 Convention on Cultural Property, sanctions must not impede the transfer of cultural materials for preservation and education.", [], "UNESCO 1970 Convention — Means of Prohibiting Illicit Import/Export of Cultural Property"),
    ],
}

def _rebuttal_set(r2, r3):
    return {2: r2, 3: r3}

CANNED_REBUTTALS: dict[str, dict[int, list[dict]]] = {
    "natural_disaster": _rebuttal_set(
        [_u("USA", "modify", "We hear Russia's concerns. The US will place carrier assets under a joint civilian-flagged coordination center — but withdrawal is not an option when lives are at stake.", ["RUS", "IND"]),
         _u("RUS", "oppose", "A joint center is a step forward, but we require equal representation and veto authority. BRICS financing must be the primary channel.", ["USA", "CHN", "IND"]),
         _u("IND", "support", "India welcomes civilian-flagged operations. We will host the coordination center in Chennai.", ["USA", "RUS"]),
         _u("CHN", "modify", "AIIB development financing should complement, not compete with, bilateral aid. We propose a dual-track approach.", ["USA", "IND", "RUS"]),
         _u("SAU", "support", "The Kingdom increases our commitment to $3.5 billion with energy infrastructure priority.", ["IND"]),
         _u("DPRK", "oppose", "This 'coordination center' is rebranded military occupation. The DPRK will not legitimize it.", ["USA"]),
         _u("UN", "mediate", "The Secretariat notes convergence. I propose a mandatory 72-hour cultural impact assessment before heavy machinery enters the heritage buffer zone.", ["IND"], "WHC-1972 Operational Guidelines Para.177")],
        [_u("IND", "support", "India formally accepts the civilian framework. Sign the memorandum within 24 hours — the cyclone season does not wait.", ["USA", "RUS", "CHN"]),
         _u("RUS", "modify", "Russia signs with one reservation: extension beyond 90 days requires a new Security Council mandate.", ["USA", "IND"]),
         _u("USA", "support", "The 90-day sunset clause is reasonable. Full transparency reporting every 30 days. We call the vote.", ["RUS", "IND"]),
         _u("CHN", "support", "China supports the amended resolution. $1.2 billion through AIIB for long-term reconstruction.", ["RUS", "IND", "USA"]),
         _u("SAU", "support", "The Kingdom votes in favor. Energy reconstruction investment will coordinate with the civilian framework.", ["IND"]),
         _u("DPRK", "oppose", "90 days, 900 days — a sunset clause means nothing when the sun never sets on imperialist ambitions.", ["USA"]),
         _u("UN", "mediate", "The Secretariat welcomes this resolution. Emergency inscription is active, monitoring deploys in 48 hours.", ["IND"], "WHC-1972 Art.11.4")],
    ),
    "arms_race": _rebuttal_set(
        [_u("USA", "modify", "The US proposes a mutual verification framework — both sides reduce forward deployments simultaneously, monitored by IAEA.", ["RUS", "CHN"]),
         _u("RUS", "modify", "Mutual verification is acceptable only if NATO's eastern expansion is frozen. We propose a 500km demilitarized buffer zone.", ["USA"]),
         _u("CHN", "support", "China supports the verification framework. We propose extending it to include missile defense systems and space-based assets.", ["USA", "RUS"]),
         _u("IND", "modify", "India insists that any arms control framework must address the asymmetry between nuclear and non-nuclear states.", ["USA", "RUS", "CHN"]),
         _u("DPRK", "oppose", "Verification frameworks are intelligence-gathering operations. The DPRK will not open its facilities to hostile inspectors.", ["USA"]),
         _u("SAU", "support", "The Kingdom endorses the verification framework and offers to host negotiations in Riyadh as a neutral venue.", ["USA", "RUS"]),
         _u("UN", "mediate", "I note progress toward de-escalation. The Secretariat will document cultural sites within the proposed buffer zone for protected status.", [], "Hague-1954 Art.4")],
        [_u("RUS", "support", "Russia accepts the verification framework with the buffer zone provision. We propose a 6-month implementation timeline.", ["USA"]),
         _u("USA", "support", "The United States agrees to the 6-month timeline. We begin mutual drawdowns within 30 days of signing.", ["RUS"]),
         _u("CHN", "support", "China will co-sponsor the resolution and contribute technical monitors to the verification team.", ["USA", "RUS"]),
         _u("IND", "support", "India welcomes the consensus and will participate in the monitoring framework as a non-aligned observer.", ["USA", "RUS", "CHN"]),
         _u("DPRK", "oppose", "The DPRK will not be bound by agreements between powers that threaten our existence.", ["USA"]),
         _u("SAU", "support", "The Kingdom reaffirms its support. De-escalation stabilizes energy markets — a win for all parties.", ["USA", "RUS"]),
         _u("UN", "mediate", "This chamber has demonstrated that dialogue can prevail. The Secretariat will monitor cultural heritage compliance throughout implementation.", [], "Hague-1954 Second Protocol Art.6")],
    ),
    "trade_war": _rebuttal_set(
        [_u("CHN", "modify", "China is prepared to make targeted concessions on intellectual property enforcement if the US rolls back tariffs on consumer goods.", ["USA"]),
         _u("USA", "modify", "Targeted concessions on IP are a starting point. We propose a phased tariff reduction tied to verifiable compliance milestones.", ["CHN"]),
         _u("IND", "support", "India supports the phased approach. We offer to mediate technical discussions on supply chain diversification.", ["USA", "CHN"]),
         _u("RUS", "modify", "Russia proposes alternative trade corridors that reduce dependency on any single bilateral relationship.", ["USA", "CHN"]),
         _u("SAU", "support", "The Kingdom supports any framework that stabilizes global commodity markets. Energy must be excluded from tariff escalation.", ["USA", "CHN"]),
         _u("DPRK", "oppose", "Phased concessions are phased surrender. Economic sovereignty cannot be negotiated away in instalments.", ["USA"]),
         _u("UN", "mediate", "Trade disputes must not impede cultural exchange. I urge exemptions for educational and cultural materials.", [], "UNESCO 2005 Convention Art.16")],
        [_u("USA", "support", "The United States accepts the phased framework. We commit to rolling back 50% of tariffs in the first phase.", ["CHN"]),
         _u("CHN", "support", "China reciprocates with enhanced IP enforcement and opens three additional sectors to foreign investment.", ["USA"]),
         _u("IND", "support", "India commends both parties. We propose hosting a follow-up summit in New Delhi to formalize the agreement.", ["USA", "CHN"]),
         _u("RUS", "support", "Russia supports the resolution. Stable trade benefits commodity exporters and importers alike.", ["USA", "CHN"]),
         _u("SAU", "support", "The Kingdom welcomes the de-escalation. We confirm energy market stabilization measures.", ["USA", "CHN"]),
         _u("DPRK", "oppose", "The DPRK notes this agreement benefits the powerful at the expense of smaller economies.", ["USA", "CHN"]),
         _u("UN", "mediate", "The Secretariat welcomes this resolution. Cultural cooperation agreements should be signed alongside trade deals.", [], "UNESCO 2005 Convention Art.20")],
    ),
    "cultural_destruction": _rebuttal_set(
        [_u("USA", "support", "The US proposes a rapid-deployment cultural protection force under UN command with logistical support from willing nations.", ["RUS"]),
         _u("RUS", "modify", "A protection force is acceptable only under strict UN mandate — not NATO command renamed. Russia demands joint oversight.", ["USA"]),
         _u("CHN", "support", "China supports the protection force concept. We offer satellite imagery and AI documentation technology.", ["USA", "RUS"]),
         _u("IND", "support", "India commits archaeological restoration teams and 3D digital preservation equipment.", ["USA"]),
         _u("SAU", "support", "The Kingdom pledges an additional $200 million for the emergency cultural protection fund."),
         _u("DPRK", "oppose", "Protection forces are occupation forces. Cultural sites have survived millennia without foreign soldiers guarding them.", ["USA"]),
         _u("UN", "mediate", "I welcome the convergence. The protection force will operate under the Blue Shield framework with strict neutrality provisions.", [], "UNSC-Res-2347 Para.17")],
        [_u("RUS", "support", "Russia accepts the Blue Shield framework with joint oversight. We will contribute monitors and logistical assets.", ["USA"]),
         _u("USA", "support", "The United States signs on to the Blue Shield deployment. Joint oversight addresses all parties' concerns.", ["RUS"]),
         _u("CHN", "support", "China fully endorses the resolution. Our technology contribution is ready for immediate deployment.", ["USA", "RUS"]),
         _u("IND", "support", "India's restoration teams will deploy within 72 hours of the resolution passing."),
         _u("SAU", "support", "The Kingdom votes in favor and increases its pledge to $300 million."),
         _u("DPRK", "oppose", "The DPRK abstains. We will not legitimize external cultural mandates but will not block the resolution."),
         _u("UN", "mediate", "This is a historic moment. The Blue Shield rapid deployment is activated. All parties will be held to their commitments.", [], "UNSC-Res-2347; Blue Shield Protocol")],
    ),
    "heritage_at_risk": _rebuttal_set(
        [_u("IND", "support", "India is establishing a 50km cultural protection perimeter around the endangered sites. International assistance is welcome within this framework."),
         _u("USA", "support", "The US increases its pledge to $100 million and offers USAID logistics for site evacuation.", ["IND"]),
         _u("CHN", "support", "China deploys drone survey teams for damage assessment. Data will be shared openly with all parties.", ["IND"]),
         _u("RUS", "modify", "Russia supports the emergency measures but insists on a 6-month review of the Danger List placement.", ["IND"]),
         _u("SAU", "support", "The Kingdom matches the US contribution. $100 million for immediate heritage stabilization.", ["IND", "USA"]),
         _u("DPRK", "neutral", "The DPRK will not obstruct but reiterates that universal application is the only just standard."),
         _u("UN", "mediate", "I note broad consensus. The emergency inscription is formalized. Monitoring teams deploy within 48 hours.", ["IND"], "WHC-1972 Art.11.4")],
        [_u("IND", "support", "India confirms all protection perimeters are in place. We invite UN monitors to begin their assessment.", ["USA", "CHN"]),
         _u("USA", "support", "The United States has transferred the first $25 million tranche. Satellite monitoring is active.", ["IND"]),
         _u("CHN", "support", "Drone surveys are complete. Data has been shared with the UN and all member states.", ["IND"]),
         _u("RUS", "support", "Russia accepts the emergency inscription with the 6-month review provision. We contribute technical expertise.", ["IND"]),
         _u("SAU", "support", "The Kingdom's funds are deployed. Saudi heritage engineers are en route.", ["IND"]),
         _u("DPRK", "neutral", "The DPRK notes the resolution and maintains its position on universal application."),
         _u("UN", "mediate", "All commitments are logged. The heritage protection corridor is operational. This chamber has acted decisively.", ["IND"], "WHC-1972 Operational Guidelines Para.177")],
    ),
    "gdp_shock": _rebuttal_set(
        [_u("USA", "modify", "The US proposes a G20 emergency lending facility with fast-disbursement provisions. Conditionality must be streamlined.", ["CHN"]),
         _u("CHN", "support", "China supports the emergency facility and pledges $50 billion through AIIB. We propose joint IMF-AIIB lending.", ["USA"]),
         _u("IND", "support", "India welcomes the joint approach. We call for debt moratorium extension to 24 months for least-developed countries.", ["USA", "CHN"]),
         _u("RUS", "modify", "Russia insists that energy price floors are included. We cannot support recovery that destabilizes commodity producers.", ["USA"]),
         _u("SAU", "support", "The Kingdom supports energy price stabilization through OPEC+ adjustments. Coordinated action prevents a spiral.", ["RUS"]),
         _u("DPRK", "oppose", "International lending institutions serve creditor nations. The DPRK rejects any framework that increases foreign debt dependency.", ["USA"]),
         _u("UN", "mediate", "Cultural sector emergency funding must be included. Museums and heritage sites face permanent closures without immediate support.", [], "UNESCO 2015 Recommendation Para.18")],
        [_u("CHN", "support", "China confirms the $50 billion AIIB commitment. Joint lending begins within 30 days.", ["USA"]),
         _u("USA", "support", "The United States matches with IMF special drawing rights allocation. We call the vote.", ["CHN"]),
         _u("IND", "support", "India thanks the chamber. The 24-month moratorium for developing nations is a lifeline.", ["USA", "CHN"]),
         _u("RUS", "support", "Energy price floors are included. Russia will participate in the recovery framework.", ["USA", "SAU"]),
         _u("SAU", "support", "The Kingdom votes in favor. OPEC+ stabilization measures take effect immediately.", ["RUS"]),
         _u("DPRK", "oppose", "The DPRK maintains its objection but will not block consensus."),
         _u("UN", "mediate", "Cultural sector provisions are included. The Secretariat will monitor implementation across all member states.", [], "UNESCO 2015 Recommendation Para.22")],
    ),
    "education_collapse": _rebuttal_set(
        [_u("IND", "support", "India proposes a South-South digital education platform built on open-source technology — no single vendor dependency.", ["USA", "CHN"]),
         _u("USA", "modify", "The US supports open standards but insists on quality benchmarks. We offer technical certification frameworks.", ["IND", "CHN"]),
         _u("CHN", "modify", "China agrees to open-source principles. We contribute our digital education infrastructure expertise.", ["IND", "USA"]),
         _u("RUS", "support", "Russia supports the multilingual platform. Educational content must respect cultural diversity.", ["IND"]),
         _u("SAU", "support", "The Kingdom increases its pledge to $750 million for digital infrastructure in underserved regions.", ["IND"]),
         _u("DPRK", "oppose", "Open platforms are surveillance platforms. The DPRK will develop its own educational technology.", ["USA"]),
         _u("UN", "mediate", "The platform must meet the Education 2030 Framework quality standards. I will convene a technical advisory panel.", [], "UNESCO Education 2030 Framework for Action")],
        [_u("IND", "support", "India confirms the open-source platform architecture. Beta testing begins in 90 days.", ["USA", "CHN"]),
         _u("USA", "support", "The US commits technical teams to the quality assurance framework. We call the vote.", ["IND"]),
         _u("CHN", "support", "China ratifies the open-source approach. Technology transfer begins immediately.", ["IND"]),
         _u("RUS", "support", "Russia will contribute Russian-language educational content to the platform.", ["IND"]),
         _u("SAU", "support", "The Kingdom's funds are committed. Arabic-language content will be our contribution.", ["IND"]),
         _u("DPRK", "oppose", "The DPRK does not participate but does not block the resolution."),
         _u("UN", "mediate", "The education emergency response is formalized. All commitments will be tracked through the Secretariat.", [], "UNESCO 1960 Convention Art.4")],
    ),
    "bloc_formation": _rebuttal_set(
        [_u("CHN", "modify", "China proposes a cross-bloc economic coordination mechanism. Competition is healthy; confrontation is not.", ["USA", "RUS"]),
         _u("USA", "modify", "The US is open to cross-bloc coordination on shared challenges: climate, pandemic preparedness, nuclear security.", ["CHN"]),
         _u("RUS", "support", "Russia endorses cross-bloc coordination. We propose starting with energy security as common ground.", ["USA", "CHN"]),
         _u("IND", "support", "India volunteers to chair the cross-bloc coordination working group as a multi-aligned nation.", ["USA", "CHN", "RUS"]),
         _u("SAU", "support", "The Kingdom hosts the inaugural session. Energy coordination transcends bloc boundaries.", ["USA", "CHN"]),
         _u("DPRK", "modify", "The DPRK will observe but not commit. Cross-bloc mechanisms must not become tools of coercion.", ["USA"]),
         _u("UN", "mediate", "Cultural exchange programs across blocs prevent intellectual fragmentation. I propose a joint cultural heritage database.", [], "UNESCO Constitution — Intellectual Solidarity")],
        [_u("USA", "support", "The United States endorses the cross-bloc coordination mechanism. Shared challenges require shared solutions.", ["CHN", "RUS"]),
         _u("CHN", "support", "China commits to the framework. The first agenda item: a joint climate action protocol.", ["USA"]),
         _u("RUS", "support", "Russia ratifies. Energy cooperation begins within 60 days.", ["USA", "CHN"]),
         _u("IND", "support", "India accepts the chair position. The first session convenes in 30 days.", ["USA", "CHN", "RUS"]),
         _u("SAU", "support", "The Kingdom confirms Riyadh as the venue. All logistics are in place.", ["IND"]),
         _u("DPRK", "neutral", "The DPRK will send observers to the first session."),
         _u("UN", "mediate", "The Secretariat will establish the joint cultural heritage database as agreed. Bloc formation need not mean cultural division.", [], "UNESCO Constitution Art.1")],
    ),
    "alliance_rupture": _rebuttal_set(
        [_u("USA", "modify", "The US proposes a new security compact with burden-sharing reform. Alliance obligations must be reciprocal.", ["RUS"]),
         _u("RUS", "modify", "Russia is open to a new compact only if it replaces, not supplements, existing alliance structures.", ["USA"]),
         _u("CHN", "support", "China endorses a more inclusive security architecture. We propose adding climate security to the mandate.", ["USA", "RUS"]),
         _u("IND", "support", "India supports a reformed security architecture with equitable burden-sharing for developing nations.", ["USA"]),
         _u("SAU", "modify", "The Kingdom insists on explicit energy security provisions in any new compact.", ["USA"]),
         _u("DPRK", "oppose", "New compacts, old compacts — the structure of hegemony remains the same.", ["USA"]),
         _u("UN", "mediate", "Cultural cooperation agreements must be preserved regardless of security alliance changes.", [], "UNESCO Constitution Art.1")],
        [_u("USA", "support", "The United States endorses the reformed security compact with burden-sharing and energy security provisions.", ["RUS", "SAU"]),
         _u("RUS", "support", "Russia accepts the new framework. We commit to confidence-building measures within 90 days.", ["USA"]),
         _u("CHN", "support", "China signs on. Climate security provisions make this framework forward-looking.", ["USA", "RUS"]),
         _u("IND", "support", "India ratifies. Equitable burden-sharing was the key breakthrough.", ["USA"]),
         _u("SAU", "support", "The Kingdom votes in favor. Energy security provisions protect all parties.", ["USA", "RUS"]),
         _u("DPRK", "oppose", "The DPRK does not recognize this compact but will not actively obstruct.", ["USA"]),
         _u("UN", "mediate", "Cultural cooperation provisions are embedded. The Secretariat will monitor compliance.", [], "UNESCO Constitution Art.1")],
    ),
    "regime_change": _rebuttal_set(
        [_u("USA", "modify", "The US pivots to supporting an inclusive national dialogue facilitated by the UN. No external imposition of governance models.", ["RUS", "CHN"]),
         _u("RUS", "modify", "Russia accepts UN-facilitated dialogue only with guaranteed representation for all domestic factions.", ["USA"]),
         _u("CHN", "support", "China supports the inclusive dialogue framework. Sovereignty must be respected throughout the process.", ["USA", "RUS"]),
         _u("IND", "support", "India endorses the UN-facilitated approach. We offer peacekeeping personnel from our experienced forces.", ["USA", "RUS"]),
         _u("SAU", "modify", "The Kingdom insists on stability guarantees. Transitional governance must maintain institutional continuity.", ["USA"]),
         _u("DPRK", "oppose", "Foreign-facilitated dialogue is foreign interference by committee. Let nations resolve their own governance.", ["USA"]),
         _u("UN", "mediate", "Cultural institutions must be protected during any transition. I invoke emergency measures for national museums and archives.", [], "UNESCO Universal Declaration on Cultural Diversity Art.4")],
        [_u("USA", "support", "The United States endorses the UN-facilitated national dialogue with full representation guarantees.", ["RUS"]),
         _u("RUS", "support", "Russia accepts. The framework respects sovereignty while enabling peaceful transition.", ["USA"]),
         _u("CHN", "support", "China fully supports the resolution. Non-interference principles are preserved.", ["USA", "RUS"]),
         _u("IND", "support", "India commits peacekeeping assets. The UN framework provides the necessary legitimacy.", ["USA", "RUS"]),
         _u("SAU", "support", "The Kingdom votes in favor. Institutional continuity provisions address our concerns.", ["USA"]),
         _u("DPRK", "oppose", "The DPRK's objection is recorded. We will not block consensus.", ["USA"]),
         _u("UN", "mediate", "Cultural protection measures are activated. The Secretariat will monitor heritage sites throughout the transition.", [], "UNESCO Universal Declaration on Cultural Diversity Art.7")],
    ),
    "military_escalation": _rebuttal_set(
        [_u("RUS", "modify", "Russia proposes a 72-hour ceasefire to allow diplomatic channels to function. Military positions will hold but not advance.", ["USA"]),
         _u("USA", "support", "The US accepts the 72-hour ceasefire. We propose joint monitoring teams at all contact points.", ["RUS"]),
         _u("CHN", "support", "China endorses the ceasefire and offers Beijing for emergency negotiations.", ["USA", "RUS"]),
         _u("IND", "support", "India supports the ceasefire. We offer communication back-channels through our diplomatic corps.", ["USA", "RUS"]),
         _u("SAU", "modify", "The Kingdom proposes linking the ceasefire to energy corridor guarantees. Economic interdependence reinforces peace.", ["USA", "RUS"]),
         _u("DPRK", "oppose", "Ceasefires without addressing root causes only freeze injustice in place.", ["USA"]),
         _u("UN", "mediate", "During the ceasefire, all parties must grant access for cultural heritage damage assessment teams.", [], "Hague-1954 Protocol I Art.2")],
        [_u("USA", "support", "The ceasefire holds. The United States commits to good-faith negotiations within the 72-hour window.", ["RUS"]),
         _u("RUS", "support", "Russia confirms the ceasefire and accepts joint monitoring. Negotiations proceed.", ["USA"]),
         _u("CHN", "support", "China confirms Beijing as the negotiation venue. All parties are welcome.", ["USA", "RUS"]),
         _u("IND", "support", "India's back-channels are active. We see grounds for optimism.", ["USA", "RUS"]),
         _u("SAU", "support", "Energy corridor guarantees are part of the framework. The Kingdom votes in favor.", ["USA", "RUS"]),
         _u("DPRK", "oppose", "The DPRK records its objection but does not break consensus.", ["USA"]),
         _u("UN", "mediate", "Heritage assessment teams are deployed. The Secretariat will report on cultural property status within 48 hours.", [], "Hague-1954 Protocol I Art.3")],
    ),
    "war_outbreak": _rebuttal_set(
        [_u("USA", "modify", "The US proposes an immediate humanitarian corridor and a 48-hour unconditional ceasefire as a starting point.", ["RUS"]),
         _u("RUS", "modify", "Russia accepts a humanitarian corridor but requires neutral zone monitoring — not by NATO forces.", ["USA"]),
         _u("CHN", "support", "China supports the humanitarian corridor. We offer civilian logistics and medical teams.", ["USA", "RUS"]),
         _u("IND", "support", "India volunteers field hospitals and evacuation support. Humanitarian access must be unconditional.", ["USA", "RUS"]),
         _u("SAU", "modify", "The Kingdom proposes emergency oil price stabilization to prevent economic collapse alongside the ceasefire.", ["USA", "RUS"]),
         _u("DPRK", "oppose", "Humanitarian corridors become intelligence corridors. We propose a fully neutral monitoring force.", ["USA"]),
         _u("UN", "mediate", "Under the 1954 Hague Convention, cultural property must be marked and protected in the humanitarian corridor.", [], "Hague-1954 Convention Art.6")],
        [_u("RUS", "support", "Russia agrees to the neutral monitoring force. The ceasefire can proceed.", ["USA"]),
         _u("USA", "support", "The United States accepts neutral monitoring. We commit to the 48-hour ceasefire starting midnight.", ["RUS"]),
         _u("CHN", "support", "China confirms logistical deployment. Peace is within reach if both sides hold firm.", ["USA", "RUS"]),
         _u("IND", "support", "India's field hospitals deploy within 24 hours. We call on all parties to hold the ceasefire.", ["USA", "RUS"]),
         _u("SAU", "support", "Oil stabilization measures are active. The Kingdom votes for the ceasefire resolution.", ["USA", "RUS"]),
         _u("DPRK", "neutral", "The neutral monitoring force addresses our concern. The DPRK will not obstruct.", ["USA"]),
         _u("UN", "mediate", "Cultural property markers are being placed. This ceasefire must hold. The Secretariat will verify compliance.", [], "Hague-1954 Convention Art.7")],
    ),
    "sanctions": _rebuttal_set(
        [_u("USA", "modify", "The US agrees to add humanitarian exemptions for food and medicine. Targeted sanctions remain on designated entities.", ["RUS"]),
         _u("RUS", "modify", "Humanitarian exemptions are a step forward. Russia proposes a sunset clause — sanctions reviewed every 90 days.", ["USA"]),
         _u("CHN", "modify", "China supports the humanitarian exemptions and the sunset clause. Regular review prevents sanctions from becoming permanent.", ["USA", "RUS"]),
         _u("IND", "support", "India endorses humanitarian exemptions. Our trade partners need predictability — the sunset clause helps.", ["USA", "RUS"]),
         _u("SAU", "support", "The Kingdom's humanitarian corridor proposal is adopted. Energy exemptions must also be explicit.", ["USA"]),
         _u("DPRK", "oppose", "Exemptions are crumbs from the table of the powerful. Full sanctions lifting is the only just outcome.", ["USA"]),
         _u("UN", "mediate", "Cultural materials must be explicitly exempted. I invoke the 1970 Convention protections.", [], "UNESCO 1970 Convention Art.7")],
        [_u("USA", "support", "The United States accepts the 90-day review with humanitarian and energy exemptions. We call the vote.", ["RUS", "SAU"]),
         _u("RUS", "support", "Russia votes in favor. The review mechanism and exemptions address our core concerns.", ["USA"]),
         _u("CHN", "support", "China supports the amended sanctions framework. Regular review ensures accountability.", ["USA", "RUS"]),
         _u("IND", "support", "India votes in favor. Predictability and humanitarian protections are preserved.", ["USA", "RUS"]),
         _u("SAU", "support", "The Kingdom confirms energy exemptions are in effect. We vote in favor.", ["USA"]),
         _u("DPRK", "oppose", "The DPRK's fundamental objection stands. But we do not block the consensus.", ["USA"]),
         _u("UN", "mediate", "Cultural exemptions are confirmed. The Secretariat will monitor compliance with cultural property protections.", [], "UNESCO 1970 Convention Art.9")],
    ),
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
        {"id": "UN",     "name": "United Nations",   "tint": "#eab308"},
    ]

    def __init__(self):
        self.loader = PersonaLoader()
        self._round_counter = 0
        self._last_debate_step = -DEBATE_RATE_LIMIT_STEPS  # allow first debate immediately

        # Optional backends: Groq + trained model (HF OpenAI-compatible endpoint)
        api_key = os.environ.get("GROQ_API_KEY", "")
        self._groq_client = AsyncGroq(api_key=api_key) if GROQ_AVAILABLE and api_key else None
        self._hf_clients: list[tuple[str, AsyncOpenAI]] = []
        if _OPENAI_AVAILABLE and _HF_TOKEN:
            for base in _hf_base_candidates(_HF_API_BASE):
                self._hf_clients.append((base, AsyncOpenAI(base_url=base, api_key=_HF_TOKEN)))

        mode = _BACKEND_MODE if _BACKEND_MODE in {"mappo", "groq", "auto"} else "mappo"
        if mode == "groq":
            self._backend = "groq" if self._groq_client else "none"
        elif mode == "auto":
            self._backend = "mappo" if self._hf_clients else ("groq" if self._groq_client else "none")
        else:
            # Default: trained model first (requested behavior)
            self._backend = "mappo" if self._hf_clients else "none"

        self._use_live = self._backend in {"mappo", "groq"}
        print(
            "DebateOrchestrator initialized. "
            f"backend={self._backend} mode={mode} "
            f"hf_model={bool(self._hf_clients)} groq={bool(self._groq_client)}"
        )

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

    async def _call_hf_model(
        self,
        system_prompt: str,
        agent_id: str,
        crisis_description: str = "",
        live_events: list[str] | None = None,
        public_sentiment: dict | None = None,
        round_num: int = 1,
        prior_utterances: list[dict] | None = None,
    ) -> dict:
        """Call trained model via HF Serverless Inference (OpenAI-compatible endpoint)."""
        if not self._hf_clients:
            raise RuntimeError("HF client not initialized")

        start = time.time()
        # Condense prompt to fit 3B model context — take last 800 chars
        condensed = system_prompt[-800:] if len(system_prompt) > 800 else system_prompt
        prompt = (
            f"{condensed}\n\n"
            f"Respond as {agent_id} in JSON with keys: text, stance, mentioned_countries, authority_citation.\n"
            f'stance must be one of: support, oppose, modify, neutral, mediate\n'
            "JSON only, no markdown:"
        )
        raw_text = ""
        used_model = _HF_MODEL
        last_err = None
        for base, client in self._hf_clients:
            try:
                resp = await client.chat.completions.create(
                    model=_HF_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0.7,
                )
                raw_text = (resp.choices[0].message.content or "").strip()
                if raw_text:
                    break
            except Exception as e:
                last_err = e
                print(f"⚠️  HF model call failed for {agent_id} via {base}: {type(e).__name__}: {e}")
                continue

        # Auto-fallback when account/provider doesn't support the primary fine-tuned model.
        if not raw_text and last_err is not None and "model_not_supported" in str(last_err):
            for base, client in self._hf_clients:
                try:
                    resp = await client.chat.completions.create(
                        model=_HF_FALLBACK_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=200,
                        temperature=0.7,
                    )
                    raw_text = (resp.choices[0].message.content or "").strip()
                    if raw_text:
                        used_model = _HF_FALLBACK_MODEL
                        break
                except Exception:
                    continue

        if not raw_text and last_err is not None:
            fallback = self._local_fallback_from_prompt(
                agent_id,
                system_prompt,
                crisis_description=crisis_description,
                live_events=live_events,
                public_sentiment=public_sentiment,
                round_num=round_num,
                prior_utterances=prior_utterances,
                raw_text="",
            )
            fallback["_latency_ms"] = int((time.time() - start) * 1000)
            fallback["_model"] = used_model
            fallback["_fallback_reason"] = f"{type(last_err).__name__}"
            return fallback

        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        try:
            parsed = json.loads(match.group()) if match else {}
        except (json.JSONDecodeError, AttributeError):
            parsed = {}

        if not parsed:
            parsed = self._local_fallback_from_prompt(
                agent_id,
                system_prompt,
                crisis_description=crisis_description,
                live_events=live_events,
                public_sentiment=public_sentiment,
                round_num=round_num,
                prior_utterances=prior_utterances,
                raw_text=raw_text,
            )

        sanitized = {
            "text": str(parsed.get("text", f"{agent_id} weighs the proposal."))[:MAX_UTTERANCE_TEXT_LEN],
            "stance": parsed.get("stance", "neutral") if parsed.get("stance") in VALID_STANCES else "neutral",
            "mentioned_countries": [
                c for c in parsed.get("mentioned_countries", [])
                if isinstance(c, str) and len(c) <= 10
            ][:10],
            "authority_citation": str(parsed.get("authority_citation", ""))[:200] if parsed.get("authority_citation") else None,
        }
        sanitized["_latency_ms"] = int((time.time() - start) * 1000)
        sanitized["_model"] = used_model
        return sanitized

    def _local_fallback_from_prompt(
        self,
        agent_id: str,
        system_prompt: str,
        crisis_description: str = "",
        live_events: list[str] | None = None,
        public_sentiment: dict | None = None,
        round_num: int = 1,
        prior_utterances: list[dict] | None = None,
        raw_text: str = "",
    ) -> dict:
        """Produce contextual fallback when HF response is unavailable/non-JSON."""
        default_stance = {
            "USA": "support",
            "CHN": "modify",
            "RUS": "oppose",
            "IND": "neutral",
            "DPRK": "oppose",
            "SAU": "support",
            "UN": "mediate",
        }.get(agent_id, "neutral")
        crisis = crisis_description.strip() or "the current crisis"
        if len(crisis) > 140:
            crisis = crisis[:140] + "..."
        event_hint = (live_events[0].strip()[:140] if live_events else "")
        sentiment_hint = ""
        if public_sentiment:
            sentiment_hint = f" Public sentiment is {public_sentiment.get('label', 'neutral')}."
        relation_row = self.loader.get_relationship_row(agent_id)
        allies = [a for a, v in sorted(relation_row.items(), key=lambda kv: kv[1], reverse=True) if v > 0.25 and a != agent_id][:2]
        rivals = [a for a, v in sorted(relation_row.items(), key=lambda kv: kv[1]) if v < -0.25 and a != agent_id][:2]
        grudges = self.loader.get_grudge_memory(agent_id, limit=2)
        prior_utterances = prior_utterances or []
        latest_other = next((u for u in reversed(prior_utterances) if u.get("speakerId") != agent_id), None)

        mentioned = []
        if latest_other and latest_other.get("speakerId"):
            mentioned.append(latest_other["speakerId"])
        if allies:
            mentioned.extend(allies[:1])
        elif rivals:
            mentioned.extend(rivals[:1])
        mentioned = [m for m in mentioned if m != agent_id][:3]

        text = raw_text.strip()
        if not text or len(text) < 16:
            # Round-aware fallback: react to prior speaker + relationships + live events.
            response_clause = ""
            if latest_other:
                other = latest_other.get("speakerId", "another delegation")
                other_stance = latest_other.get("stance", "position")
                response_clause = f" In response to {other}'s {other_stance} remarks, "

            alliance_clause = ""
            if allies:
                alliance_clause = f" It seeks coordination with {', '.join(allies)}."
            elif rivals:
                alliance_clause = f" It challenges pressure from {', '.join(rivals)}."

            history_clause = ""
            if grudges:
                g = grudges[0]
                history_clause = f" It references prior friction with {g.get('against', 'a rival')}."

            if agent_id == "UN":
                text = (
                    f"Under current mandate, UN mediates on {crisis} and pushes a compliance-focused compromise."
                    f"{response_clause}it urges all parties to remain within legal authority."
                    f"{(' Recent UNESCO context: ' + event_hint + '.') if event_hint else ''}"
                )
            else:
                text = (
                    f"{agent_id} takes a {default_stance} stance on {crisis} in round {round_num}."
                    f"{response_clause}it frames its position around current risk signals."
                    f"{(' Recent domestic signal: ' + event_hint + '.') if event_hint else ''}"
                    f"{alliance_clause}{history_clause}{sentiment_hint}"
                )
        return {
            "text": text[:MAX_UTTERANCE_TEXT_LEN],
            "stance": default_stance,
            "mentioned_countries": mentioned,
            "authority_citation": None,
        }

    def _get_canned(self, crisis_type: str, agent_order: list[str], round_num: int = 1) -> list[dict]:
        """Return canned debate utterances, with round-specific rebuttals when available."""
        if round_num > 1:
            rebuttals = CANNED_REBUTTALS.get(crisis_type, {})
            base = rebuttals.get(round_num)
            if not base:
                base = rebuttals.get(max(rebuttals.keys())) if rebuttals else None
            if not base:
                base = CANNED_DEBATES.get(crisis_type, CANNED_DEBATES["natural_disaster"])
        else:
            base = CANNED_DEBATES.get(crisis_type, CANNED_DEBATES["natural_disaster"])

        ordered = []
        for agent_id in agent_order:
            match = next((u for u in base if u["speaker"] == agent_id), None)
            if match:
                ordered.append(match)
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

        # Determine speaker order: involved first, then peripheral, skip uninvolved (not UN)
        involved = involvement.get("involved", [])
        peripheral = involvement.get("peripheral", [])
        speaker_order = [a for a in involved if a != "UN"] + \
                        [a for a in peripheral if a != "UN"] + \
                        ["UN"]

        use_live = self._use_live and not force_canned
        round_utterances = []

        if use_live:
            # ── LIVE PATH: trained model (default) or Groq (optional) ───────
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
                if self._backend == "groq":
                    tasks[agent_id] = asyncio.create_task(self._call_groq(prompt, agent_id))
                else:
                    tasks[agent_id] = asyncio.create_task(
                        self._call_hf_model(
                            prompt,
                            agent_id,
                            crisis_description=crisis_description,
                            live_events=live_events,
                            public_sentiment=sentiment,
                            round_num=1,
                            prior_utterances=[],
                        )
                    )

            timeout = GROQ_TIMEOUT + 2 if self._backend == "groq" else 30.0
            for agent_id in speaker_order:
                try:
                    raw = await asyncio.wait_for(tasks[agent_id], timeout=timeout)
                except Exception as e:
                    backend = "Groq" if self._backend == "groq" else "trained model"
                    print(f"⚠️  {backend} failed for {agent_id}: {e}. Falling back to canned.")
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

                for mentioned in raw.get("mentioned_countries", []):
                    self.loader.update_relationship(agent_id, mentioned, raw.get("stance", "neutral"))

                yield utterance
                await asyncio.sleep(1.8)

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
                await asyncio.sleep(2.5)

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
        max_rounds = max(1, min(max_rounds, 3))
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
                    if self._backend == "groq":
                        tasks[agent_id] = asyncio.create_task(self._call_groq(prompt, agent_id))
                    else:
                        tasks[agent_id] = asyncio.create_task(
                            self._call_hf_model(
                                prompt,
                                agent_id,
                                crisis_description=crisis_description,
                                live_events=live_events,
                                public_sentiment=sentiment,
                                round_num=round_num,
                                prior_utterances=all_utterances,
                            )
                        )

                timeout = GROQ_TIMEOUT + 2 if self._backend == "groq" else 30.0
                for agent_id in speaker_order:
                    try:
                        raw = await asyncio.wait_for(tasks[agent_id], timeout=timeout)
                    except Exception as e:
                        backend = "Groq" if self._backend == "groq" else "trained model"
                        print(f"⚠️  {backend} failed for {agent_id} round {round_num}: {e}")
                        canned = self._get_canned(crisis_type, [agent_id], round_num)
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
                    await asyncio.sleep(1.8)
            else:
                canned = self._get_canned(crisis_type, speaker_order, round_num)
                for raw in canned:
                    agent_id = raw["speaker"]
                    utterance = make_utterance(agent_id, raw, current_step, self.AGENTS_CONFIG)
                    utterance["roundId"] = round_id
                    utterance["roundNumber"] = round_num
                    utterance["_live"] = False
                    round_utterances.append(utterance)
                    yield {"_event": "utterance", **utterance}
                    await asyncio.sleep(2.5)

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

            await asyncio.sleep(2.0)

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
        return [a for a in involved if a != "UN"] + \
               [a for a in peripheral if a != "UN"] + \
               ["UN"]

    def _build_rebuttal_order(self, involvement: dict, prior_utterances: list[dict]) -> list[str]:
        """Rebuttal rounds: agents mentioned by others respond first, then
        oppose/modify speakers, then remaining, then UN last."""
        mentioned_targets: list[str] = []
        rebuttal_speakers: list[str] = []
        seen: set[str] = set()

        for u in reversed(prior_utterances):
            for m in u.get("mentionedCountries", []):
                if m != "UN" and m not in seen:
                    mentioned_targets.append(m)
                    seen.add(m)

            sid = u["speakerId"]
            if sid == "UN" or sid in seen:
                continue
            if u["stance"] in ("oppose", "modify"):
                rebuttal_speakers.append(sid)
                seen.add(sid)

        priority = mentioned_targets + rebuttal_speakers
        all_agents = self._build_speaker_order(involvement)
        remaining = [a for a in all_agents if a not in seen and a != "UN"]
        return priority + remaining + ["UN"]

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
        if round_num < 2:
            return True
        oppose = tally.get("oppose", 0)
        modify = tally.get("modify", 0)
        if oppose == 0 and modify == 0:
            return False
        return True

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
        """Compute vote tally from utterances (UN excluded from vote)."""
        tally = {"support": 0, "oppose": 0, "modify": 0, "neutral": 0}
        for u in utterances:
            if u["speakerId"] == "UN":
                continue  # UN is non-voting
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


# ── UN Mediator Helper ─────────────────────────────────────────────────────────

class UNMediator:
    """Selects relevant authority articles for UN utterances."""

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
            "peripheral": ["CHN", "RUS", "UN"],
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
