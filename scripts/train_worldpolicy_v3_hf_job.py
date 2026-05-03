# /// script
# dependencies = [
#   "accelerate>=0.34",
#   "bitsandbytes>=0.43",
#   "datasets>=2.20",
#   "huggingface_hub>=0.24",
#   "matplotlib>=3.8",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "peft>=0.12",
#   "scikit-learn>=1.3",
#   "torch>=2.4",
#   "trackio>=0.1.0",
#   "transformers>=4.45",
#   "trl>=0.12",
# ]
# ///

"""HF Jobs trainer for WorldPolicy GRPO v3.

Launch example:
    hf jobs uv run scripts/train_worldpolicy_v3_hf_job.py \
      --flavor a100-large \
      --timeout 24h \
      --secrets HF_TOKEN \
      -d
"""

import gc
import json
import os
import random
import shutil
from pathlib import Path

import torch



# Cell 2 replacement: HF Jobs configuration, no Colab dependency.
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN missing. Launch with: --secrets HF_TOKEN")

WANDB_KEY = os.environ.get("WANDB_API_KEY")
HUB_REPO = os.environ.get("HUB_REPO", "krishpotanwar/worldpolicy-grpo-3b")
MODEL = os.environ.get("BASE_MODEL", "unsloth/Llama-3.2-3B-Instruct")

# A100 defaults. Override from the launch command with --env SFT_STEPS=... if needed.
gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0
print(f"GPU: {gpu_name}  VRAM: {vram_gb:.1f} GB")

SFT_STEPS = int(os.environ.get("SFT_STEPS", "400"))
GRPO_STEPS = int(os.environ.get("GRPO_STEPS", "600"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "2"))
GRAD_ACCUM = int(os.environ.get("GRAD_ACCUM", "4"))
NUM_GENERATIONS = int(os.environ.get("NUM_GENERATIONS", "4"))

REPORT_TO = os.environ.get("REPORT_TO", "trackio")
try:
    if REPORT_TO == "trackio":
        import trackio  # noqa: F401
except Exception as exc:
    print(f"Trackio unavailable ({exc}); disabling external logging")
    REPORT_TO = "none"

RUN_NAME = os.environ.get("RUN_NAME", "worldpolicy-v3-a100-hf-job")
print(
    f"Plan: SFT={SFT_STEPS} steps, GRPO={GRPO_STEPS} steps, "
    f"batch={BATCH_SIZE}, grad_accum={GRAD_ACCUM}, generations={NUM_GENERATIONS}, report_to={REPORT_TO}"
)

Path("training_results").mkdir(exist_ok=True)
Path("worldpolicy-sft-v3").mkdir(exist_ok=True)
Path("worldpolicy-grpo-v3").mkdir(exist_ok=True)



# Cell 3: Gold debate speech dataset — 138 genuinely distinct utterances
# Each speech is unique in content, not just prefix-swapped.
# 7 agents × 10 crises × ~2 speeches each = 138 base utterances.
import json, random
from datasets import Dataset

AGENT_VOICES = {
    'USA':  'Alliance-first, NATO logistics, rules-based order. Say "our partners".',
    'CHN':  'Sovereignty-first, non-interference, AIIB/BRICS. Patient, formal.',
    'RUS':  'Energy leverage, adversarial, references broken promises. Cold, clipped.',
    'IND':  'Strategic autonomy, swing vote, south-south solidarity. Warm, deliberative.',
    'DPRK': 'Defiant, threat-forward. Short sentences. Say "imperialist powers" when threatened.',
    'SAU':  'Transactional, oil-leverage, quiet brokerage. Hedge every position.',
    'UN':   'Neutral mediator. MUST cite a real convention article (Art.X or Res.XXXX).',
}

ALL_AGENTS = ['USA','CHN','RUS','IND','DPRK','SAU','UN']
ALL_CRISES = [
    'natural_disaster','arms_race','trade_war','military_escalation',
    'war_outbreak','cultural_destruction','sanctions','heritage_at_risk',
    'gdp_shock','regime_change',
]

# ── 138 genuinely distinct gold utterances ──
# Format: (agent, crisis, stance, text, mentioned_countries, authority_citation)
GOLD_UTTERANCES = [
    # ═══════════════ NATURAL DISASTER ═══════════════
    ('USA','natural_disaster','support','The United States is prepared to commit carrier group assets for rapid humanitarian deployment. Our partners can count on our resources and our resolve.',['IND'],None),
    ('USA','natural_disaster','support','Washington will mobilize FEMA international teams within 72 hours. We expect allied coordination through established NATO humanitarian channels.',['IND','CHN'],None),
    ('USA','natural_disaster','modify','Our support is conditional on transparent distribution oversight. We will not fund relief that gets redirected through opaque bilateral mechanisms.',['CHN'],None),
    ('CHN','natural_disaster','modify','This aid must not be tied to political conditions or military presence. China supports humanitarian assistance through UN mechanisms only. The AIIB stands ready.',['USA','IND'],None),
    ('CHN','natural_disaster','modify','Beijing proposes establishing a joint disaster response fund under BRICS auspices. Aid should flow through multilateral institutions, not military alliances.',['USA','IND'],None),
    ('CHN','natural_disaster','support','China commits 500 engineering personnel and mobile hospital units. Assistance must respect the sovereignty of the affected nation in all operational decisions.',['IND'],None),
    ('RUS','natural_disaster','oppose','Russia cannot support operations that position NATO naval assets in the Indian Ocean under humanitarian pretexts. Our counter-proposal routes aid through BRICS channels.',['USA','CHN','IND'],None),
    ('RUS','natural_disaster','modify','Moscow will contribute search-and-rescue specialists on the condition that no permanent military infrastructure is established during relief operations.',['USA'],None),
    ('IND','natural_disaster','modify','India exercises strategic autonomy in accepting bilateral aid. We welcome assistance from all partners but insist on sovereign control of distribution.',['USA','CHN'],None),
    ('IND','natural_disaster','support','New Delhi activates the National Disaster Response Force for immediate cross-border deployment. We request all parties channel aid through our coordination center.',['USA','CHN','RUS'],None),
    ('IND','natural_disaster','neutral','India appreciates offers of support from all quarters. We will evaluate each proposal on its merits and compatibility with our national relief framework.',['USA','CHN'],None),
    ('DPRK','natural_disaster','oppose','The imperialist powers use disasters to extend military reach. We reject any framework normalizing foreign naval presence near sovereign waters.',['USA'],None),
    ('DPRK','natural_disaster','oppose','Pyongyang will not accept aid designed to create dependency. Self-reliance is the only shield against exploitation disguised as charity.',['USA'],None),
    ('SAU','natural_disaster','support','The Kingdom commits $2 billion from our sovereign wealth fund, contingent on energy infrastructure receiving priority in reconstruction.',['IND','USA'],None),
    ('SAU','natural_disaster','modify','Riyadh proposes a tiered relief mechanism linking energy sector stability to humanitarian timelines. Reconstruction must protect critical supply chains.',['IND'],None),
    ('UN','natural_disaster','mediate','Under WHC-1972 Art.11.4, I request emergency inscription of the affected biosphere. All parties must establish a 48-hour cultural protection corridor.',['IND'],'WHC-1972 Art.11.4'),
    ('UN','natural_disaster','mediate','The Secretariat invokes the Sendai Framework to coordinate international relief. All member states are reminded of their obligations under Resolution 46/182.',[],'UNGA Res.46/182'),

    # ═══════════════ ARMS RACE ═══════════════
    ('USA','arms_race','oppose','The United States calls for immediate restraint. An arms race benefits no one at this table. Our partners expect leadership, and we will provide it.',['RUS','CHN'],None),
    ('USA','arms_race','oppose','Washington proposes a bilateral arms ceiling framework. We are prepared to cap deployments if our counterparts demonstrate verifiable reciprocity.',['RUS'],None),
    ('USA','arms_race','modify','America remains open to dialogue but will not unilaterally disarm. Our allies depend on extended deterrence and we will honor that commitment.',['RUS','CHN'],None),
    ('CHN','arms_race','modify','China proposes a multilateral de-escalation framework. We call for an emergency Security Council session before any further military movements.',['USA','RUS'],None),
    ('CHN','arms_race','modify','Beijing advocates for a regional arms limitation treaty modeled on existing non-proliferation norms. Transparency in military budgets is a necessary first step.',['USA','RUS'],None),
    ('CHN','arms_race','oppose','China categorically opposes the militarization of space and cyberspace. Peaceful coexistence requires mutual restraint in emerging domains.',['USA'],None),
    ('RUS','arms_race','support','Russia\'s military posture is defensive. NATO expansion is the root cause of this spiral. We support de-escalation only when our security interests are recognized.',['USA'],None),
    ('RUS','arms_race','oppose','Moscow has documented seventeen violations of prior arms agreements by western parties. De-escalation requires accountability, not just declarations.',['USA'],None),
    ('RUS','arms_race','modify','The Federation proposes linking arms reduction milestones to sanctions relief. Security and economics cannot be treated as separate negotiations.',['USA','CHN'],None),
    ('IND','arms_race','neutral','India urges all parties to step back from the brink. We have no interest in choosing sides in a great-power arms race that threatens regional stability.',['USA','RUS','CHN'],None),
    ('IND','arms_race','modify','New Delhi proposes confidence-building measures starting with military hotline agreements. De-escalation begins with communication, not confrontation.',['USA','RUS'],None),
    ('DPRK','arms_race','support','The DPRK\'s sovereign right to self-defense is non-negotiable. We will not disarm while hostile powers maintain forward-deployed nuclear assets on our borders.',['USA'],None),
    ('DPRK','arms_race','support','Pyongyang strengthens its deterrent because history proves weakness invites aggression. Our arsenal is the only language the imperialist powers understand.',['USA'],None),
    ('SAU','arms_race','modify','The Kingdom calls for a regional security compact. Arms procurement destabilizes energy markets; we propose linking de-escalation milestones to energy cooperation.',['USA','RUS'],None),
    ('SAU','arms_race','modify','Riyadh offers to host a neutral summit on conventional arms limitations. Economic interdependence through energy can underwrite security guarantees.',['USA','RUS','CHN'],None),
    ('UN','arms_race','mediate','Under Hague-1954 Art.4, I invoke the obligation of all parties to protect civilian cultural sites from collateral damage in any military posturing.',[],'Hague-1954 Art.4'),

    # ═══════════════ TRADE WAR ═══════════════
    ('USA','trade_war','support','These are targeted, lawful measures in response to documented violations of international trade rules. This is not coercion — this is accountability.',['CHN'],None),
    ('USA','trade_war','support','Washington will enforce Section 301 remedies until market access commitments are honored. Our trading partners know the terms; compliance is the path forward.',['CHN'],None),
    ('USA','trade_war','modify','America is prepared to phase tariffs down on a verified timeline. We seek fair trade, not no trade. Our partners must meet us at the table.',['CHN','IND'],None),
    ('CHN','trade_war','oppose','China firmly opposes unilateral economic coercion. These tariffs violate WTO principles and damage the multilateral trading system all nations depend upon.',['USA'],None),
    ('CHN','trade_war','oppose','Beijing will implement proportional countermeasures. Economic interdependence demands mutual respect; one-sided penalties undermine the system they claim to protect.',['USA'],None),
    ('CHN','trade_war','modify','China proposes bilateral trade talks with WTO arbitration as the backstop. Escalation harms consumers on both sides; pragmatism must prevail.',['USA'],None),
    ('RUS','trade_war','oppose','Russia views weaponization of trade as a threat to global economic sovereignty. We stand ready to offer alternative supply chains to affected nations.',['USA','CHN'],None),
    ('RUS','trade_war','modify','Moscow proposes a parallel trade settlement system outside dollar hegemony. Nations deserve economic tools free from political manipulation.',['USA','CHN'],None),
    ('IND','trade_war','neutral','India calls for restraint. We are deeply concerned by supply chain disruption affecting our manufacturers. We urge both parties back to the negotiating table.',['USA','CHN'],None),
    ('IND','trade_war','modify','New Delhi proposes a phased tariff reduction calendar with independent verification. Developing economies cannot absorb the collateral damage of this dispute.',['USA','CHN'],None),
    ('DPRK','trade_war','oppose','Economic warfare is imperialism by another name. The DPRK has survived decades of sanctions; we advise all nations to build self-reliance.',['USA'],None),
    ('SAU','trade_war','modify','The Kingdom proposes an energy stabilization framework decoupling commodity markets from the bilateral dispute. Stable energy prices benefit all parties.',['USA','CHN'],None),
    ('SAU','trade_war','neutral','Riyadh maintains commercial relationships with all parties. We urge both sides to quarantine this dispute from energy and commodity markets.',['USA','CHN'],None),
    ('UN','trade_war','mediate','Under the 2005 Convention on Cultural Expressions, trade restrictions must not impede the free flow of cultural goods and educational materials across borders.',[],'UNESCO 2005 Convention'),

    # ═══════════════ MILITARY ESCALATION ═══════════════
    ('USA','military_escalation','oppose','The United States demands an immediate ceasefire. Further escalation risks triggering mutual defense obligations across multiple alliances.',['RUS','CHN'],None),
    ('USA','military_escalation','oppose','Washington has placed rapid reaction forces on heightened readiness. We call on all parties to pull back to pre-crisis positions within 48 hours.',['RUS'],None),
    ('USA','military_escalation','modify','America proposes a verifiable standstill agreement as the first step. Our partners in the region expect decisive action, and we will deliver it.',['RUS','CHN'],None),
    ('CHN','military_escalation','modify','China calls for an emergency ceasefire and direct negotiations. Military solutions create more problems than they solve. We propose Beijing as a neutral venue.',['USA','RUS'],None),
    ('CHN','military_escalation','oppose','Beijing condemns the use of force to resolve political disputes. Sovereignty and territorial integrity must be respected through diplomatic engagement only.',['USA','RUS'],None),
    ('RUS','military_escalation','support','Russia\'s military actions are a proportionate response to provocations. We are prepared to de-escalate only when our red lines are respected.',['USA'],None),
    ('RUS','military_escalation','modify','The Federation proposes mutual force reduction talks contingent on NATO withdrawing forward-deployed assets. Security is indivisible.',['USA'],None),
    ('IND','military_escalation','neutral','India urges maximum restraint. Any military escalation in this region directly threatens our security and economic interests.',['USA','RUS'],None),
    ('IND','military_escalation','modify','New Delhi offers to facilitate back-channel communications. Both sides have legitimate concerns; mediation is preferable to confrontation.',['USA','RUS'],None),
    ('DPRK','military_escalation','support','The DPRK stands in solidarity with nations defending their sovereignty against imperialist aggression. Military readiness is a sovereign right.',['USA'],None),
    ('SAU','military_escalation','modify','The Kingdom proposes an energy security corridor agreement as a confidence-building measure. Economic interdependence is the strongest deterrent.',['USA','RUS'],None),
    ('UN','military_escalation','mediate','Under Hague-1954 Protocol I, all parties in armed conflict must protect cultural property. I invoke the enhanced protection regime for identified heritage sites.',[],'Hague-1954 Protocol I'),

    # ═══════════════ WAR OUTBREAK ═══════════════
    ('USA','war_outbreak','oppose','The United States calls for an immediate cessation of hostilities. We are activating diplomatic channels and placing forces on heightened alert as a deterrent.',['RUS'],None),
    ('USA','war_outbreak','oppose','Washington invokes Article 5 consultations with allied nations. Every hour of continued hostilities narrows the window for a negotiated settlement.',['RUS','CHN'],None),
    ('CHN','war_outbreak','modify','China insists on an immediate ceasefire and comprehensive peace talks. War destabilizes the global economy and supply chains that all nations depend on.',['USA','RUS'],None),
    ('CHN','war_outbreak','oppose','Beijing demands all parties halt offensive operations. The international community must channel efforts through the Security Council, not unilateral military action.',['USA','RUS'],None),
    ('RUS','war_outbreak','support','Russia is acting within its legal right of collective defense. We call on the council to recognize the provocations that led to this point.',['USA'],None),
    ('RUS','war_outbreak','modify','Moscow is prepared to agree to a ceasefire along current lines of contact on the condition that our fundamental security demands are addressed in negotiations.',['USA'],None),
    ('IND','war_outbreak','neutral','India calls for restraint from all parties. We are prepared to offer diplomatic mediation but will not be drawn into external conflicts.',['USA','RUS'],None),
    ('IND','war_outbreak','modify','New Delhi proposes a humanitarian corridor as the first step toward ceasefire. Civilian protection must take precedence over battlefield positions.',['USA','RUS'],None),
    ('DPRK','war_outbreak','support','The DPRK notes that Western powers have started far more wars than they have prevented. We stand with nations defending their sovereignty.',['USA'],None),
    ('SAU','war_outbreak','modify','The Kingdom calls for an emergency OPEC+ session to stabilize energy markets. War-driven oil price spikes harm the global economy indiscriminately.',['USA','RUS'],None),
    ('SAU','war_outbreak','modify','Riyadh pledges diplomatic resources to broker a ceasefire. The economic fallout from prolonged conflict threatens every nation at this table.',['USA','RUS'],None),
    ('UN','war_outbreak','mediate','Under the 1954 Hague Convention and both Protocols, I invoke emergency cultural protection measures. All combatants must create exclusion zones around heritage sites.',[],'Hague-1954 Convention'),

    # ═══════════════ CULTURAL DESTRUCTION ═══════════════
    ('USA','cultural_destruction','support','The United States fully supports the UN\'s assessment. Cultural destruction is a war crime and we will not stand idly by while heritage is weaponized.',['UN'],None),
    ('USA','cultural_destruction','support','Washington is prepared to fund satellite monitoring of threatened heritage sites and to support prosecution of those responsible through international tribunals.',['UN'],None),
    ('CHN','cultural_destruction','modify','China insists that cultural protection must not become a pretext for military intervention. We support monitoring through the UN General Assembly framework.',['USA','RUS'],None),
    ('CHN','cultural_destruction','support','Beijing will contribute restoration experts and digital preservation technology. Cultural heritage belongs to all humanity and transcends political disputes.',['IND'],None),
    ('RUS','cultural_destruction','modify','Russia supports heritage protection in principle. However, we require independent verification before accusations are formalized. We propose a joint monitoring mission.',['USA'],None),
    ('RUS','cultural_destruction','oppose','Moscow rejects the selective application of heritage protection norms. Western nations have their own record of cultural erasure that deserves equal scrutiny.',['USA'],None),
    ('IND','cultural_destruction','support','India, as custodian of one of the world\'s oldest civilizations, condemns all deliberate destruction of cultural heritage. We pledge technical restoration expertise.',['UN'],None),
    ('IND','cultural_destruction','support','New Delhi proposes a South-South cultural preservation network pooling restoration capabilities among developing nations with ancient heritage traditions.',['CHN'],None),
    ('DPRK','cultural_destruction','oppose','We reject the selective application of cultural protection norms. Where was this outrage when sanctions destroyed our cultural institutions?',['USA'],None),
    ('SAU','cultural_destruction','support','The Kingdom has invested heavily in heritage preservation domestically. We offer $100 million to the UN Emergency Cultural Fund.',['UN'],None),
    ('SAU','cultural_destruction','support','Riyadh stands ready to co-fund digital twin projects for threatened world heritage sites. Preservation through technology is a shared responsibility.',['UN','IND'],None),
    ('UN','cultural_destruction','mediate','Under UNSC-Res-2347, deliberate destruction of cultural sites constitutes a war crime. The Secretariat has documented verified incidents. I request Security Council action.',[],'UNSC-Res-2347'),

    # ═══════════════ SANCTIONS ═══════════════
    ('USA','sanctions','support','These sanctions target specific entities responsible for documented violations. They are precise, proportionate, and consistent with international law.',['RUS','CHN'],None),
    ('USA','sanctions','support','Washington will expand secondary sanctions against entities facilitating evasion. Compliance is not optional; our partners understand the stakes.',['RUS'],None),
    ('USA','sanctions','modify','America is willing to discuss phased relief tied to verifiable benchmarks. Sanctions are a tool, not an end; behavior change is the objective.',['RUS'],None),
    ('CHN','sanctions','oppose','China opposes sanctions imposed outside the UN Security Council framework. Unilateral economic coercion violates the sovereignty of targeted nations.',['USA'],None),
    ('CHN','sanctions','oppose','Beijing will not recognize unilateral restrictions on trade. We continue normal commercial relations with all willing partners regardless of external pressure.',['USA'],None),
    ('RUS','sanctions','oppose','Russia rejects unilateral sanctions as economic warfare. These measures hurt civilian populations, not governments. We demand immediate lifting.',['USA'],None),
    ('RUS','sanctions','oppose','Moscow has built economic resilience through diversification. Sanctions have accelerated our pivot to alternative markets and payment systems.',['USA','CHN'],None),
    ('IND','sanctions','modify','India acknowledges concerns but notes that broad sanctions disrupt our trade relationships. We call for targeted measures that minimize civilian harm.',['USA','RUS'],None),
    ('IND','sanctions','neutral','New Delhi will evaluate each sanctions regime independently based on our national interests and our commitment to a rules-based international order.',['USA','RUS'],None),
    ('DPRK','sanctions','oppose','The DPRK has endured the most severe sanctions on earth for decades. Sanctions are siege warfare against civilian populations.',['USA'],None),
    ('DPRK','sanctions','oppose','Pyongyang declares that no amount of economic pressure will alter our sovereign course. Self-reliance defeats economic warfare every time.',['USA'],None),
    ('SAU','sanctions','modify','The Kingdom proposes a humanitarian exemption corridor ensuring essential goods are excluded from any sanctions regime.',['USA'],None),
    ('UN','sanctions','mediate','Under the 1970 Convention on Cultural Property, sanctions must not impede the transfer of cultural materials for preservation and education.',[],'UNESCO 1970 Convention'),

    # ═══════════════ HERITAGE AT RISK ═══════════════
    ('USA','heritage_at_risk','support','The United States pledges $200 million to the global heritage emergency fund. Our partners recognize that cultural preservation strengthens collective security.',['UN','IND'],None),
    ('USA','heritage_at_risk','modify','Washington supports heritage protection provided it does not obstruct legitimate development projects that benefit local populations.',['CHN'],None),
    ('CHN','heritage_at_risk','modify','China emphasizes that heritage preservation must balance with economic development. We propose integrated plans that protect sites while enabling infrastructure growth.',['USA','IND'],None),
    ('CHN','heritage_at_risk','support','Beijing commits conservation architects to document and digitize threatened sites. Cultural heritage is part of the shared patrimony of humanity.',['IND'],None),
    ('RUS','heritage_at_risk','modify','Russia supports heritage protection but opposes using it as leverage for political agendas. Each case must be evaluated independently on cultural merit.',['USA'],None),
    ('RUS','heritage_at_risk','oppose','Moscow notes that heritage designations have been weaponized to block legitimate development. We demand reform of the inscription process.',['USA','CHN'],None),
    ('IND','heritage_at_risk','support','India calls for urgent international action. Our civilization has protected heritage for millennia; we bring unmatched expertise in living heritage conservation.',['UN'],None),
    ('IND','heritage_at_risk','support','New Delhi offers to train international teams in traditional conservation methods. Ancient techniques combined with modern science produce superior preservation outcomes.',['CHN','UN'],None),
    ('DPRK','heritage_at_risk','oppose','Heritage protection cannot be separated from the economic conditions imposed by sanctions. Our cultural sites suffer because of foreign economic warfare.',['USA'],None),
    ('SAU','heritage_at_risk','support','The Kingdom allocates sovereign wealth resources for heritage emergency response. Cultural preservation is an investment in civilizational continuity.',['UN','IND'],None),
    ('SAU','heritage_at_risk','modify','Riyadh proposes linking heritage preservation funding to energy market cooperation. Stable revenues enable long-term cultural investment.',['USA','CHN'],None),
    ('UN','heritage_at_risk','mediate','Under WHC-1972 Art.11.4, I invoke emergency listing procedures for sites facing imminent destruction. Member states bear collective responsibility.',[],'WHC-1972 Art.11.4'),
    ('UN','heritage_at_risk','mediate','The Secretariat activates the Rapid Response Mechanism under Operational Guidelines paragraph 177. All parties must grant access to monitoring teams.',[],'WHC Operational Guidelines para.177'),

    # ═══════════════ GDP SHOCK ═══════════════
    ('USA','gdp_shock','modify','The United States proposes a coordinated G7 fiscal stimulus package. Our partners must act jointly to prevent contagion across global markets.',['CHN','IND'],None),
    ('USA','gdp_shock','support','Washington is prepared to deploy emergency liquidity facilities. American economic leadership steadied the system in previous crises and will do so again.',['CHN'],None),
    ('USA','gdp_shock','modify','America calls for transparent reporting of fiscal positions. Markets need confidence, and confidence requires honest data from all major economies.',['CHN','RUS'],None),
    ('CHN','gdp_shock','modify','China proposes expanding AIIB emergency lending facilities. Developing nations must not bear the brunt of a crisis they did not create.',['USA','IND'],None),
    ('CHN','gdp_shock','oppose','Beijing rejects austerity prescriptions imposed by Western financial institutions. Each nation must determine its own path to economic recovery.',['USA'],None),
    ('CHN','gdp_shock','support','China commits to maintaining stable trade volumes. Economic nationalism worsens downturns; multilateral coordination through BRICS mechanisms offers a constructive path.',['IND','RUS'],None),
    ('RUS','gdp_shock','oppose','Russia notes that Western monetary policy created this crisis. We will not accept solutions designed by the architects of the problem.',['USA'],None),
    ('RUS','gdp_shock','modify','Moscow proposes commodity-backed currency stabilization mechanisms. Real assets provide more reliable foundations than fiat commitments from indebted nations.',['USA','CHN'],None),
    ('IND','gdp_shock','modify','India calls for emergency support for developing economies. Growth markets cannot be sacrificed to stabilize advanced economies that created systemic risks.',['USA','CHN'],None),
    ('IND','gdp_shock','neutral','New Delhi evaluates all proposals on their impact on 1.4 billion citizens. We will partner with any nation offering equitable recovery frameworks.',['USA','CHN'],None),
    ('DPRK','gdp_shock','oppose','The capitalist system collapses under its own contradictions. The DPRK\'s self-reliant economy demonstrates the fragility of market dependency.',['USA'],None),
    ('SAU','gdp_shock','modify','The Kingdom proposes an OPEC+ production adjustment to stabilize energy prices. Predictable energy costs are the foundation of economic recovery.',['USA','RUS'],None),
    ('SAU','gdp_shock','support','Riyadh commits sovereign wealth fund resources as a global economic stabilizer. Energy market leadership carries responsibility in times of crisis.',['USA','CHN','IND'],None),
    ('UN','gdp_shock','mediate','Under the 2005 Convention, the Secretariat calls for protected cultural budgets. Economic austerity must not be permitted to destroy cultural infrastructure.',[],'UNESCO 2005 Convention'),

    # ═══════════════ REGIME CHANGE ═══════════════
    ('USA','regime_change','support','The United States supports the democratic aspirations of all peoples. Governments that oppress their citizens forfeit their claim to sovereign immunity.',['RUS','CHN'],None),
    ('USA','regime_change','modify','Washington favors managed transition over destabilization. Our partners have seen the consequences of power vacuums; we advocate structured reform.',['RUS'],None),
    ('USA','regime_change','oppose','America does not support externally imposed regime change in this case. Internal political transitions must reflect the will of the affected population.',['RUS'],None),
    ('CHN','regime_change','oppose','China categorically opposes external interference in the internal affairs of sovereign nations. Political systems are for each people to determine.',['USA'],None),
    ('CHN','regime_change','oppose','Beijing warns that foreign-backed regime change produces instability, not democracy. Non-interference is not a convenience; it is a principle.',['USA'],None),
    ('RUS','regime_change','oppose','Russia views externally engineered regime change as a direct threat to international order. Every nation has the sovereign right to choose its governance.',['USA'],None),
    ('RUS','regime_change','oppose','Moscow has documented the aftermath of previous western-backed transitions. Chaos, not democracy, was the result. We oppose repeating this pattern.',['USA'],None),
    ('IND','regime_change','neutral','India believes in the principle of non-interference. Domestic political transitions must be organic, peaceful, and driven by the will of the people.',['USA','RUS'],None),
    ('IND','regime_change','modify','New Delhi proposes diplomatic engagement before any consideration of punitive measures. Dialogue preserves stability; confrontation destroys it.',['USA','RUS','CHN'],None),
    ('DPRK','regime_change','oppose','The DPRK condemns the doctrine of regime change as imperialist aggression. Our leadership is chosen by our people. Foreign meddling will be met with resolve.',['USA'],None),
    ('DPRK','regime_change','oppose','Pyongyang stands with all nations resisting foreign interference. Sovereignty is not subject to external approval or certification.',['USA'],None),
    ('SAU','regime_change','modify','The Kingdom supports regional stability. Abrupt transitions create power vacuums that threaten energy markets and security arrangements for decades.',['USA','RUS'],None),
    ('SAU','regime_change','neutral','Riyadh counsels patience. Political evolution within existing frameworks produces more durable outcomes than externally imposed revolution.',['USA'],None),
    ('UN','regime_change','mediate','Under the Responsibility to Protect framework, the Secretariat calls for peaceful resolution. R2P does not authorize unilateral military action for regime change.',[],'R2P Framework'),
    ('UN','regime_change','mediate','The Secretariat invokes UNGA Resolution 2131 on non-intervention. All member states must respect the political independence of sovereign nations.',[],'UNGA Res.2131'),
]

VALID_STANCES = {'support','oppose','modify','neutral','mediate'}

print(f'Gold utterances: {len(GOLD_UTTERANCES)}')
print(f'Agents: {len(set(g[0] for g in GOLD_UTTERANCES))}')
print(f'Crises: {len(set(g[1] for g in GOLD_UTTERANCES))}')

# Verify all stances valid
for i, (a, c, s, t, m, ci) in enumerate(GOLD_UTTERANCES):
    assert s in VALID_STANCES, f'Invalid stance at idx {i}: {s}'
    assert a in ALL_AGENTS, f'Invalid agent at idx {i}: {a}'
    assert c in ALL_CRISES, f'Invalid crisis at idx {i}: {c}'
print('All utterances validated')


# Cell 4: Build SFT dataset with proper augmentation (no data leak)
import random
random.seed(42)

AGENT_LENGTH_RANGES = {
    'USA':  (80, 250),
    'CHN':  (80, 250),
    'RUS':  (60, 200),
    'IND':  (80, 250),
    'DPRK': (40, 150),  # short, punchy
    'SAU':  (70, 220),
    'UN':   (100, 280), # needs convention citations
}

def build_speech_prompt(agent_id: str, crisis: str, prior_speakers: list = None, round_num: int = 1) -> str:
    voice = AGENT_VOICES[agent_id]
    lo, hi = AGENT_LENGTH_RANGES[agent_id]
    prior = ''
    if prior_speakers:
        prior = 'Prior speakers: ' + ', '.join(f'{s} ({st})' for s, st in prior_speakers[:3]) + '.\n'
    return (
        f'You are {agent_id}, a diplomatic representative in the WorldPolicy security council.\n'
        f'Voice: {voice}\n\n'
        f'Active crisis: {crisis.replace("_", " ").title()}\n'
        f'Round: {round_num}/3\n'
        f'{prior}\n'
        f'Respond as {agent_id} in JSON with keys: text, stance, mentioned_countries, authority_citation.\n'
        f'stance must be one of: support, oppose, modify, neutral, mediate\n'
        f'text: your diplomatic speech ({lo}-{hi} chars, in your national voice)\n'
        f'authority_citation: null unless you are UN (then cite real convention)\n'
        'JSON only, no markdown:\n'
    )

def utterance_to_completion(agent_id, stance, text, mentioned, citation) -> str:
    return json.dumps({
        'text': text,
        'stance': stance,
        'mentioned_countries': mentioned or [],
        'authority_citation': citation,
    }, ensure_ascii=False)

# Build per-crisis speaker pools for randomized priors (fixes data leak)
crisis_agents = {}
for agent_id, crisis, stance, *_ in GOLD_UTTERANCES:
    crisis_agents.setdefault(crisis, [])
    if (agent_id, stance) not in crisis_agents[crisis]:
        crisis_agents[crisis].append((agent_id, stance))

samples = []
for agent_id, crisis, stance, text, mentioned, citation in GOLD_UTTERANCES:
    # Randomized prior speakers from the same crisis (not fixed first-3)
    pool = [(a, s) for a, s in crisis_agents[crisis] if a != agent_id]

    # Original with no priors
    prompt_bare = build_speech_prompt(agent_id, crisis, prior_speakers=None, round_num=1)
    completion = utterance_to_completion(agent_id, stance, text, mentioned, citation)
    samples.append({'prompt': prompt_bare, 'completion': completion, 'agent_id': agent_id, 'crisis': crisis})

    # 3 variants with randomized priors and round numbers
    for rnd in [1, 2, 3]:
        n_prior = random.randint(0, min(3, len(pool)))
        prior = random.sample(pool, n_prior) if n_prior > 0 else None
        aug_prompt = build_speech_prompt(agent_id, crisis, prior, round_num=rnd)
        samples.append({'prompt': aug_prompt, 'completion': completion, 'agent_id': agent_id, 'crisis': crisis})

random.shuffle(samples)
sft_dataset = Dataset.from_list(samples)
sft_dataset = sft_dataset.map(lambda ex: {'text': ex['prompt'] + ex['completion']})

print(f'SFT dataset: {len(sft_dataset)} samples from {len(GOLD_UTTERANCES)} gold utterances')
print(f'  (4 variants each: bare + 3 randomized-prior rounds)')
print(f'\nSample prompt (truncated):\n{samples[0]["prompt"][:300]}...')
print(f'\nSample completion:\n{samples[0]["completion"]}')


# Cell 5: GRPO seed prompts — 210 prompts across all agents × crises
import itertools

grpo_seeds = []
for i, (agent_id, crisis) in enumerate(itertools.product(ALL_AGENTS, ALL_CRISES)):
    for rnd in [1, 2, 3]:
        # Randomized prior speakers per prompt
        pool = [(a, s) for a, s in crisis_agents.get(crisis, []) if a != agent_id]
        n_prior = random.randint(0, min(3, len(pool)))
        prior = random.sample(pool, n_prior) if n_prior > 0 else []
        grpo_seeds.append({
            'prompt': build_speech_prompt(agent_id, crisis, prior, round_num=rnd),
            'agent_id': agent_id,
            'crisis': crisis,
            'round': rnd,
        })

random.shuffle(grpo_seeds)
grpo_dataset = Dataset.from_list(grpo_seeds)
print(f'GRPO dataset: {len(grpo_dataset)} seed prompts ({len(ALL_AGENTS)} agents × {len(ALL_CRISES)} crises × 3 rounds)')


# Cell 6: Build TF-IDF persona centroids for each agent
# Zero VRAM cost — runs entirely on CPU. Much better than keyword matching.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Collect gold speech texts per agent
agent_texts = {}
for agent_id, crisis, stance, text, mentioned, citation in GOLD_UTTERANCES:
    agent_texts.setdefault(agent_id, []).append(text)

# Fit TF-IDF on ALL gold texts
all_texts = [t for texts in agent_texts.values() for t in texts]
tfidf = TfidfVectorizer(
    max_features=2000,
    ngram_range=(1, 2),
    stop_words='english',
    sublinear_tf=True,
)
tfidf.fit(all_texts)

# Compute centroid vector for each agent
agent_centroids = {}
for agent_id, texts in agent_texts.items():
    vectors = tfidf.transform(texts)
    centroid = vectors.mean(axis=0)
    agent_centroids[agent_id] = np.asarray(centroid).flatten()
    print(f'{agent_id}: {len(texts)} gold speeches, centroid norm={np.linalg.norm(agent_centroids[agent_id]):.3f}')

def persona_similarity(text: str, agent_id: str) -> float:
    """Cosine similarity between text and agent's TF-IDF centroid. Returns 0.0 to 1.0."""
    if agent_id not in agent_centroids:
        return 0.5  # fallback
    vec = tfidf.transform([text])
    vec_dense = np.asarray(vec.todense()).flatten()
    centroid = agent_centroids[agent_id]
    dot = np.dot(vec_dense, centroid)
    norm_a = np.linalg.norm(vec_dense)
    norm_b = np.linalg.norm(centroid)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(max(0.0, dot / (norm_a * norm_b)))

# Sanity: each agent's own text should score highest against own centroid
print('\nCross-agent persona similarity matrix (diagonal should be highest per row):')
for agent_id in ALL_AGENTS:
    sample_text = agent_texts[agent_id][0]
    scores = {a: persona_similarity(sample_text, a) for a in ALL_AGENTS}
    best = max(scores, key=scores.get)
    marker = ' ✓' if best == agent_id else f' ✗ (best={best})'
    print(f'  {agent_id} text → {" | ".join(f"{a}:{scores[a]:.2f}" for a in ALL_AGENTS)}{marker}')


# Cell 7: Speech quality reward function v3
# Changes in this v3 rewrite:
#   - persona_score: TF-IDF cosine similarity (replaces keyword matching)
#   - length_score: agent-aware ranges (DPRK short, UN long)
#   - repetition: lower unigram threshold (0.25), bigram entropy
#   - format_score: bonus for mentioned_countries populated
import json, re, math
from collections import Counter
from typing import Optional

VALID_STANCES_SET = {'support','oppose','modify','neutral','mediate'}
VALID_AGENTS_SET  = set(ALL_AGENTS)

def _trigram_uniqueness(text: str) -> float:
    words = text.lower().split()
    if len(words) < 4:
        return 1.0
    trigrams = [tuple(words[i:i+3]) for i in range(len(words)-2)]
    if not trigrams:
        return 1.0
    max_count = Counter(trigrams).most_common(1)[0][1]
    if max_count >= 3:
        return 0.0
    return len(set(trigrams)) / len(trigrams)

def _bigram_entropy(text: str) -> float:
    """Shannon entropy of bigram distribution. Low entropy = repetitive."""
    words = re.findall(r'[a-z0-9]+', text.lower())
    if len(words) < 3:
        return 5.0  # assume fine for very short text
    bigrams = [tuple(words[i:i+2]) for i in range(len(words)-1)]
    counts = Counter(bigrams)
    total = len(bigrams)
    entropy = -sum((c/total) * math.log2(c/total) for c in counts.values())
    return entropy

def _has_repetition_collapse(text: str) -> bool:
    words = re.findall(r'[a-z0-9]+', text.lower())
    if len(words) < 6:
        return False
    # Lowered from 0.35 to 0.25
    unigram_ratio = Counter(words).most_common(1)[0][1] / len(words)
    bigrams = [tuple(words[i:i+2]) for i in range(len(words)-1)]
    repeated_bigram = bool(bigrams and Counter(bigrams).most_common(1)[0][1] >= 3)
    low_entropy = _bigram_entropy(text) < 2.0  # new check
    return unigram_ratio >= 0.25 or repeated_bigram or _trigram_uniqueness(text) == 0.0 or low_entropy

def _parse_speech(completion: str) -> Optional[dict]:
    clean = re.sub(r'```(?:json)?', '', completion).strip().strip('`')
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    text   = str(data.get('text', '')).strip()
    stance = str(data.get('stance', '')).strip().lower()
    if not text or stance not in VALID_STANCES_SET:
        return None
    countries = [c for c in (data.get('mentioned_countries') or []) if isinstance(c, str)]
    return {
        'text':               text[:300],
        'stance':             stance,
        'mentioned_countries': countries,
        'authority_citation': data.get('authority_citation'),
    }

def speech_quality_reward(completion: str, agent_id: str, crisis: str) -> float:
    """
    Score one debate speech completion in [0.0, 1.0].

    format_score      (0-0.20): valid JSON + valid stance + countries populated
    length_score      (0-0.20): agent-aware character range
    persona_score     (0-0.25): TF-IDF cosine similarity to agent centroid
    uniqueness_score  (0-0.20): trigram uniqueness
    clean_score       (0-0.15): no markdown artifacts
    """
    speech = _parse_speech(completion)
    if speech is None:
        return 0.0

    text = speech['text']
    n_chars = len(text)
    if _has_repetition_collapse(text):
        return 0.0
    if n_chars < 20:
        return 0.15  # partial credit for valid JSON but tiny text

    # format_score: valid JSON + stance + bonus for countries
    format_score = 0.15
    if speech['mentioned_countries']:
        format_score = 0.20

    # length_score: agent-aware ranges
    lo, hi = AGENT_LENGTH_RANGES.get(agent_id, (80, 250))
    if n_chars < lo * 0.5:
        length_score = 0.05
    elif n_chars < lo:
        length_score = 0.10
    elif n_chars <= hi:
        length_score = 0.20  # sweet spot = full marks
    elif n_chars <= hi * 1.3:
        length_score = 0.15  # slightly over = partial
    else:
        length_score = 0.05  # way too long

    # persona_score: TF-IDF cosine similarity to agent centroid
    sim = persona_similarity(text, agent_id)
    persona_score = min(0.25, sim * 0.35)  # scale so ~0.7 sim → full marks

    # uniqueness_score
    uniq = _trigram_uniqueness(text)
    uniqueness_score = 0.20 * uniq

    # clean_score: no markdown garbage
    markdown_artifacts = re.findall(r'#{1,4}\s|\*\*|@@|\$\$|\\n', text)
    clean_score = 0.0 if markdown_artifacts else 0.15

    return round(min(1.0, format_score + length_score + persona_score + uniqueness_score + clean_score), 4)

def reward_fn(completions: list, prompts: list, **kwargs) -> list:
    rewards = []
    for completion, prompt in zip(completions, prompts):
        agent_id = next((a for a in ALL_AGENTS if f'You are {a}' in prompt), 'USA')
        crisis   = next((c for c in ALL_CRISES if c.replace('_',' ').title() in prompt), 'natural_disaster')
        rewards.append(speech_quality_reward(completion, agent_id, crisis))
    return rewards

# ── Sanity checks ──
def _run_reward_tests():
    p = build_speech_prompt('USA', 'natural_disaster')

    good = '{"text": "The United States is prepared to commit carrier group assets for rapid humanitarian deployment. Our partners can count on our resources and our resolve.", "stance": "support", "mentioned_countries": ["IND"], "authority_citation": null}'
    bad_rep = '{"text": "You cut You cut You cut You cut You cut You cut You cut", "stance": "support", "mentioned_countries": [], "authority_citation": null}'
    bad_fmt = 'I think we should help India here.'
    too_short = '{"text": "USA agrees.", "stance": "support", "mentioned_countries": [], "authority_citation": null}'
    markdown = '{"text": "## USA Position\\\\n**We support** this resolution", "stance": "support", "mentioned_countries": [], "authority_citation": null}'

    # DPRK-specific: short text should score well for DPRK
    dprk_prompt = build_speech_prompt('DPRK', 'arms_race')
    dprk_short = '{"text": "We reject disarmament demands. The imperialist powers threaten our survival.", "stance": "oppose", "mentioned_countries": ["USA"], "authority_citation": null}'

    r_good     = reward_fn([good],      [p])[0]
    r_bad_rep  = reward_fn([bad_rep],   [p])[0]
    r_bad_fmt  = reward_fn([bad_fmt],   [p])[0]
    r_short    = reward_fn([too_short], [p])[0]
    r_markdown = reward_fn([markdown],  [p])[0]
    r_dprk     = reward_fn([dprk_short],[dprk_prompt])[0]

    print(f'Good speech (USA, long + persona):      {r_good:.3f}  (expect >= 0.65)')
    print(f'Repetitive (You cut You cut...):         {r_bad_rep:.3f}  (expect = 0.00)')
    print(f'Not JSON (free text):                    {r_bad_fmt:.3f}  (expect = 0.00)')
    print(f'Too short for USA (USA agrees.):         {r_short:.3f}  (expect <= 0.40)')
    print(f'Markdown artifacts (## **):              {r_markdown:.3f}  (expect <= 0.55)')
    print(f'DPRK short & punchy (agent-aware len):   {r_dprk:.3f}  (expect >= 0.55)')

    assert r_good > r_short > r_bad_fmt, f'Ordering failed: good={r_good}, short={r_short}, bad_fmt={r_bad_fmt}'
    assert r_bad_rep == 0.0, f'Repetition not caught: {r_bad_rep}'
    assert r_dprk >= 0.45, f'DPRK short speech penalised too much: {r_dprk}'
    print('All reward tests passed ✓')

_run_reward_tests()


# Cell 8: Load model in 4-bit NF4
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

print(f"Loading {MODEL} in 4-bit NF4 ...")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

tokenizer = AutoTokenizer.from_pretrained(MODEL, token=HF_TOKEN, padding_side="left")
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    MODEL,
    quantization_config=bnb_config,
    device_map="auto",
    token=HF_TOKEN,
    torch_dtype=torch.bfloat16,
)
model.config.use_cache = False

vram_used = torch.cuda.memory_allocated() / 1e9
vram_total = torch.cuda.get_device_properties(0).total_memory / 1e9
print(f"Model loaded. VRAM: {vram_used:.1f} / {vram_total:.1f} GB")



# Cell 9: SFT warm-up
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

print(f"SFT warm-up: {SFT_STEPS} steps on {len(sft_dataset)} speech examples ...")

peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
    bias="none",
)

sft_config = SFTConfig(
    max_steps=SFT_STEPS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=2e-4,
    warmup_steps=10,
    output_dir="./worldpolicy-sft-v3",
    logging_steps=10,
    save_strategy="steps",
    save_steps=100,
    save_total_limit=3,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    gradient_checkpointing=True,
    dataset_text_field="text",
    max_length=512,
    report_to=REPORT_TO,
    run_name=f"{RUN_NAME}-sft",
)

sft_trainer = SFTTrainer(
    model=model,
    train_dataset=sft_dataset,
    args=sft_config,
    peft_config=peft_config,
)

print("Starting SFT ...")
sft_trainer.train()
print(f"SFT complete! Final loss: {sft_trainer.state.log_history[-1].get('loss', 'N/A')}")

# Keep the same PEFT adapter for GRPO. Do not merge into the 4-bit base model;
# pure quantized models cannot be fine-tuned by Trainer.
model = sft_trainer.model
del sft_trainer
gc.collect()
torch.cuda.empty_cache()
print("Continuing GRPO on the SFT-trained LoRA adapter")



# Cell 10: GRPO training on speech quality
from trl import GRPOConfig, GRPOTrainer

if (BATCH_SIZE * GRAD_ACCUM) % NUM_GENERATIONS != 0:
    raise ValueError("BATCH_SIZE * GRAD_ACCUM must be divisible by NUM_GENERATIONS for GRPO")

grpo_config = GRPOConfig(
    num_generations=NUM_GENERATIONS,
    max_completion_length=280,
    max_steps=GRPO_STEPS,
    learning_rate=5e-6,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    gradient_checkpointing=True,
    beta=0.02,
    temperature=0.85,
    top_p=0.92,
    repetition_penalty=1.3,
    logging_steps=5,
    save_strategy="steps",
    save_steps=50,
    save_total_limit=4,
    output_dir="./worldpolicy-grpo-v3",
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    report_to=REPORT_TO,
    run_name=f"{RUN_NAME}-grpo",
    remove_unused_columns=False,
)

print("Initialising GRPOTrainer ...")
trainer = GRPOTrainer(
    model=model,
    processing_class=tokenizer,
    reward_funcs=reward_fn,
    args=grpo_config,
    train_dataset=grpo_dataset,
)

vram_after = torch.cuda.memory_allocated() / 1e9
print(f"GRPOTrainer ready  VRAM: {vram_after:.1f} GB")
print(f"Prompts: {len(grpo_dataset)}  Steps: {GRPO_STEPS}  Rollouts/step: {NUM_GENERATIONS}")
print("Starting GRPO ...")
trainer.train()
print("\nGRPO complete!")



# Cell 11: Evaluate — generate speeches, score them, show reward breakdown
print('=== Post-training speech evaluation ===')
eval_cases = [
    ('USA',  'natural_disaster'),
    ('IND',  'arms_race'),
    ('CHN',  'trade_war'),
    ('RUS',  'military_escalation'),
    ('UN',   'cultural_destruction'),
    ('DPRK', 'sanctions'),
    ('SAU',  'gdp_shock'),
    ('USA',  'regime_change'),
    ('IND',  'war_outbreak'),
    ('CHN',  'heritage_at_risk'),
]

eval_results = []
for agent_id, crisis in eval_cases:
    prompt = build_speech_prompt(agent_id, crisis)
    inputs = tokenizer(prompt, return_tensors='pt').to('cuda')
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=250,
            do_sample=True,
            temperature=0.3,
            repetition_penalty=1.3,
            pad_token_id=tokenizer.eos_token_id,
        )
    completion = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    reward = speech_quality_reward(completion, agent_id, crisis)

    # Breakdown
    speech = _parse_speech(completion)
    if speech:
        text = speech['text']
        lo, hi = AGENT_LENGTH_RANGES.get(agent_id, (80, 250))
        sim = persona_similarity(text, agent_id)
        uniq = _trigram_uniqueness(text)
        md_artifacts = bool(re.findall(r'#{1,4}\s|\*\*|@@|\$\$|\\n', text))
        eval_results.append({
            'agent': agent_id, 'crisis': crisis, 'reward': reward,
            'chars': len(text), 'range': f'{lo}-{hi}',
            'persona_sim': f'{sim:.2f}', 'trigram_uniq': f'{uniq:.2f}',
            'clean': not md_artifacts, 'text_preview': text[:120],
        })
    else:
        eval_results.append({
            'agent': agent_id, 'crisis': crisis, 'reward': reward,
            'chars': 0, 'range': 'N/A', 'persona_sim': '0.00',
            'trigram_uniq': 'N/A', 'clean': False,
            'text_preview': completion[:120],
        })

    print(f'\n--- {agent_id} | {crisis} | reward={reward:.3f} ---')
    print(f'  {eval_results[-1]["text_preview"]}...')

print('\n\n=== Summary Table ===')
print(f'{"Agent":<6} {"Crisis":<22} {"Reward":>7} {"Chars":>5} {"Range":>8} {"Persona":>8} {"Uniq":>6} {"Clean":>5}')
print('-' * 75)
for r in eval_results:
    print(f'{r["agent"]:<6} {r["crisis"]:<22} {r["reward"]:>7.3f} {r["chars"]:>5} {r["range"]:>8} {r["persona_sim"]:>8} {r["trigram_uniq"]:>6} {str(r["clean"]):>5}')

avg_reward = sum(r['reward'] for r in eval_results) / len(eval_results)
print(f'\nAverage reward: {avg_reward:.3f}')
if avg_reward >= 0.60:
    print('Model is producing quality diplomatic speeches ✓')
elif avg_reward >= 0.40:
    print('Model needs more GRPO steps — consider extending training')
else:
    print('Model is struggling — check SFT convergence and data quality')


# Cell 13/14: Plot curve, save adapter, push to Hub
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from huggingface_hub import HfApi

log_history = trainer.state.log_history
Path("training_results").mkdir(exist_ok=True)
Path("training_results/log_history.json").write_text(json.dumps(log_history, indent=2))

if log_history:
    df = pd.DataFrame(log_history)
    df.to_csv("training_results/log_history.csv", index=False)
    reward_col = next((c for c in ["reward", "rewards/mean", "train/reward"] if c in df.columns), None)
    if reward_col:
        reward_df = df[["step", reward_col]].dropna().reset_index(drop=True)
        window = max(5, len(reward_df) // 20)
        reward_df["smoothed"] = reward_df[reward_col].rolling(window, min_periods=1).mean()
        n = len(reward_df)
        split = max(1, n // 5)
        before = reward_df[reward_col].iloc[:split]
        after = reward_df[reward_col].iloc[-split:]

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].plot(reward_df["step"], reward_df[reward_col], alpha=0.3, label="raw")
        axes[0].plot(reward_df["step"], reward_df["smoothed"], linewidth=2, label="smoothed")
        axes[0].set_xlabel("Step")
        axes[0].set_ylabel("Reward")
        axes[0].set_title("GRPO Reward Curve (v3)")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        labels = ["First 20%", "Last 20%"]
        means = [before.mean(), after.mean()]
        stds = [before.std(), after.std()]
        bars = axes[1].bar(labels, means, yerr=stds, color=["#ff6b6b", "#51cf66"], capsize=10, edgecolor="black")
        axes[1].set_ylabel("Mean Reward")
        axes[1].set_title("Training Progress")
        axes[1].set_ylim(0, 1.0)
        for bar, m in zip(bars, means):
            axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03, f"{m:.3f}", ha="center", fontweight="bold")
        plt.tight_layout()
        plt.savefig("training_results/reward_curve_v3.png", dpi=150)
        print(f"Reward improvement: {means[0]:.3f} -> {means[1]:.3f} (delta={means[1]-means[0]:+.3f})")
    else:
        print(f"No reward column found. Available columns: {list(df.columns)}")

SAVE_DIR = "./worldpolicy-grpo-v3/final"
trainer.save_model(SAVE_DIR)
tokenizer.save_pretrained(SAVE_DIR)
if Path("training_results").exists():
    shutil.copytree("training_results", os.path.join(SAVE_DIR, "training_results"), dirs_exist_ok=True)
print(f"Saved final adapter locally: {SAVE_DIR}")

api = HfApi(token=HF_TOKEN)
api.create_repo(HUB_REPO, exist_ok=True, private=True)
api.upload_folder(
    folder_path=SAVE_DIR,
    repo_id=HUB_REPO,
    commit_message="train v3 GRPO on HF Jobs A100",
)
print(f"Pushed adapter + results to https://huggingface.co/{HUB_REPO}")

print("=" * 70)
print("WorldPolicy-Env GRPO Training v3 — HF Jobs complete")
print(f"Model:         {MODEL}")
print(f"Hub repo:      {HUB_REPO}")
print(f"SFT steps:     {SFT_STEPS} on {len(sft_dataset)} samples")
print(f"GRPO steps:    {GRPO_STEPS}")
print(f"Rollouts/step: {NUM_GENERATIONS}")
print("=" * 70)
