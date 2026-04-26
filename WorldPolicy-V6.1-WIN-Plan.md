# WorldPolicy-Env V6.1 — The Debate-Anchored Win Plan
**Hackathon:** Scaler × PyTorch × HuggingFace × Meta — Bengaluru, April 25–26 2026
**Team:** Krish · Raj · Tushar
**Deadline:** ~50 hours from now
**Supersedes:** `WorldPolicy-V6-WIN-Plan.md`
**Objective:** Score 95%+ by anchoring the entire demo on a single jaw-dropping moment — a live multi-agent country debate with real-time profit & loss consequences, driven by a hybrid MAPPO + LLM architecture.

---

## What Changed from V6 → V6.1

V6 tried to win by stacking 20 features. That is a losing strategy because hackathon judges remember **moments**, not feature counts. V6.1 picks a single anchor — the **Debate Chamber** — and rebuilds the demo story around it. Lower-value V6 features are dropped or deferred so the anchor can be built to ship-quality.

| V6 Feature | V6.1 Status | Why |
|---|---|---|
| Cascade Failure Mode | **Kept** (feeds the debate with escalating crises) | Still the world-state driver |
| MAPPO vs Rule-Based Split Screen | **Dropped from Tier-1** (moved to optional overlay) | Debate replaces this as the evidence artifact |
| Policy Explanation Drawer | **Folded into the Debate** | Debate IS the policy explanation |
| Humanitarian Impact Panel | **Kept + merged into Country P&L Ledger** | Same metrics, better home |
| World Outcome Summary Card | **Kept** | Still the demo climax modal |
| Coalition Formation Detector | **Kept + enhanced** | Now detected from rhetoric too, not just actions |
| Scenario Library | **Kept** | Debate needs topic variety |
| Groq Flash Brief | **Kept + scope-expanded** | Now also drives debate speech generation |
| Timeline Replay Scrubber | **Deferred to Tier-2** | Too expensive if debate is prioritized |
| HF Spaces Auto-Deploy | **Kept** | Credibility still matters |
| 20-agent expansion | **Dropped** | V6.1 uses 6 countries + UNESCO; depth over breadth |
| Counterfactual Sandbox | **Deferred to Tier-3** | Only if everything else ships |
| Burden-Sharing Justice Panel | **Folded into Country P&L** | Same idea, better framing |

Net change: **fewer features, deeper build, stronger story.**

---

## The One-Line Pitch

> "Seven AI agents — six nations and UNESCO — debate every global crisis in real time. MAPPO picks the action, LLMs explain the *why*, and a live profit-and-loss ledger shows the consequences tick by tick."

Every feature in V6.1 serves this sentence.

---

## The Seven Agents

V6.1 intentionally drops the "20-agent heterogeneous expansion" idea from V6. Depth of persona beats count of agents. Judges will not remember agent #14. They will remember that North Korea said something unpredictable that made the Cold War detector fire.

| # | Agent | Country | Persona Archetype | Voice Register |
|---|-------|---------|-------------------|----------------|
| 1 | USA | United States | Alliance-first, rules-based, rhetorical appeals to international order | Confident, measured, frequent references to "partners" |
| 2 | China | People's Republic of China | Sovereignty-first, long-horizon, infrastructure-as-influence | Formal, patient, emphasizes non-interference and development |
| 3 | Russia | Russian Federation | Leverage-driven, adversarial, energy and security-guarantee talk | Cold, clipped, frequent red lines |
| 4 | India | Republic of India | Balancing, strategic autonomy, south-south solidarity | Warm, deliberative, historical framing |
| 5 | DPRK | Democratic People's Republic of Korea | Defiant, threat-forward, asymmetric leverage, unpredictable | Short sentences, stark, occasional grandiose claims |
| 6 | KSA | Kingdom of Saudi Arabia | Transactional, oil-leverage, quiet brokerage, religious framing when convenient | Discreet, hedging, proposes deals |
| 7 | **UNESCO** | — (international) | Neutral mediator, data-first, heritage + education guardianship | Institutional, precise, invokes conventions and articles |

### Persona Depth — "Mid+" (confirmed in Q9)

Each agent gets:
- **Static character file** (`personas/USA.md`, etc.) — 40-80 lines: voice rules, vocabulary preferences, red lines, alliance defaults, domestic pressures
- **Relationship matrix** — 7×7 table loaded from `data/relationships.json`, values in `[-1.0, 1.0]`. Updates every debate round based on what was said and who voted how.
- **Grudge memory** — each agent stores the last 10 debates where another agent opposed them. Referenced in future speeches ("The Russian delegation opposed our last three interventions; we note that pattern.")
- **Crisis-adaptive behavior** — personas shift tone based on crisis type. E.g. DPRK becomes more belligerent during nuclear/military crises, more quiet during UNESCO/heritage debates.

### UNESCO is Special

UNESCO is not a country. It is an institutional mediator with three non-negotiable properties:

1. **Non-voting.** Speaks but never casts a vote. Visually tagged `MEDIATOR · NON-VOTING` in the UI.
2. **Unbiased.** Prompt-engineered to refuse to take sides between nations. Invokes only convention articles and data.
3. **Authority-scoped.** Every UNESCO utterance cites the article or convention it is invoking (e.g. "Convention 1972 Article 11.4 — World Heritage in Danger"). Sources loaded from a pre-scraped `data/unesco_authority.json` corpus (scrape happens in hours 0–2 of setup sprint).
4. **Data-grounded.** UNESCO references real heritage sites, risk data, education indicators from the pre-scraped corpus. It does not invent facts.

If UNESCO speaks outside its mandate (e.g. on military matters), the UI flags the utterance as `ADVISORY — NON-BINDING`. If within mandate, `WITHIN MANDATE ✓`. This credibility gating is a huge judge-trust signal.

---

## The Hybrid Architecture (Q2: Option C)

```
                    ┌────────────────────────────────┐
                    │     Event Engine / Cascade     │
                    │       (scripted events)        │
                    └────────────────┬───────────────┘
                                     │ crisis fires
                                     ▼
                    ┌────────────────────────────────┐
                    │   MAPPO Policy (PyTorch)       │
                    │   → picks candidate action     │
                    └────────────────┬───────────────┘
                                     │ proposed action
                                     ▼
                    ┌────────────────────────────────┐
                    │     LLM Debate Orchestrator    │
                    │  (Llama 3.3-70b via Groq)      │
                    │                                │
                    │  Each agent generates          │
                    │  utterance from:               │
                    │   - their persona file         │
                    │   - world state snapshot       │
                    │   - MAPPO proposed action      │
                    │   - their relationship matrix  │
                    │   - their grudge memory        │
                    │   - UNESCO authority corpus    │
                    └────────────────┬───────────────┘
                                     │ utterances + stances
                                     ▼
                    ┌────────────────────────────────┐
                    │  Vote Aggregator               │
                    │  support > oppose → confirm    │
                    │  modify wins      → re-ask MAPPO│
                    │                    with constraint│
                    └────────────────┬───────────────┘
                                     │ final action
                                     ▼
                    ┌────────────────────────────────┐
                    │  World State Step              │
                    │  → updates Country P&L         │
                    │  → updates Company P&L         │
                    │  → updates Relationship Matrix │
                    └────────────────────────────────┘
```

**Why this is the right framing (Q10 hybrid story):**
- MAPPO is still the policy. Training metrics, reward curves, EvalSummaryCard — all V5 artifacts stay valid.
- LLMs are an **explainability layer** on top of MAPPO, not a replacement. Judges who ask "where is MARL" get a clean answer: "The policy is MAPPO. The debate is how we make the policy decisions legible and interactive."
- The vote can modify MAPPO's action — this is a novel form of **human-in-the-loop constraint injection**, publishable-quality framing.

---

## Crisis Topic Coverage (Q4)

The four required domains map cleanly onto existing + new event types:

| Domain | Event Types | New? |
|---|---|---|
| World Economy | trade_war, gdp_shock, sanctions | V5 carryover |
| War Conditions | arms_race, military_escalation, war_outbreak | V5 carryover |
| Country Politics | bloc_formation, alliance_rupture, regime_change | V5 carryover |
| **UNESCO Topics** | **heritage_at_risk, education_collapse, cultural_destruction** | **NEW in V6.1** |

Add `data/unesco_events.json` with pre-seeded scenarios:
- Heritage site damaged in conflict (e.g. fictional UNESCO-listed Zone 7 temple hit by cyclone)
- Education collapse during crisis (e.g. school systems shutting down under humanitarian stress)
- Cultural destruction as war crime (e.g. deliberate heritage destruction during militarization)

Each UNESCO event carries a `authority_citation` field mapping to one or more articles from the scraped corpus. This is what UNESCO agent cites verbatim when it speaks.

---

## Country P&L Ledger (Q5: more metrics + separate company track)

### Country-level P&L — 7 metrics per country

| Metric | Description | Derived from |
|---|---|---|
| GDPΔ | Economic output delta per step | world_state.gdp_index |
| Jobs | Employment index | gdp × crisis_impact_factor |
| Energy | Energy security score | energy_reserves × sanctions_applied |
| Influence | Geopolitical soft-power index | relationship_matrix row sum |
| Welfare | Citizen welfare (health + humanitarian) | disaster_severity × aid_received |
| Heritage | UNESCO heritage integrity | heritage_sites_safe / heritage_sites_total |
| Military | Military readiness | arms_race_index × alliance_strength |

UNESCO row: only `heritage` populated. All other columns show `—`. This is visually important — it reinforces the agent's non-national nature.

### Company-level P&L — separate strip (new in V6.1)

One flagship company per country, displayed as a ticker-tape strip:

| Country | Symbol | Company | Rationale |
|---|---|---|---|
| USA | AAPL | Apple | Global consumer-tech index |
| China | BYDDY | BYD | State-aligned industrial, EV |
| Russia | GAZP | Gazprom | Energy leverage proxy |
| India | RELI | Reliance | Conglomerate breadth |
| DPRK | KOMID* | (state arms, simulated) | Sanctions sensitivity proxy |
| KSA | 2222.SR | Saudi Aramco | Oil price exposure |

*KOMID is a fictional ticker for simulation purposes — label it clearly as `SIMULATED` in the UI.

Company prices tick from a pre-seeded 500-step Brownian motion with crisis-driven shocks. When a crisis fires that is relevant to a company (e.g. sanctions on Russia → GAZP drops), apply a step-function delta. When an agent speaks defending or harming their company's position, apply a rhetoric-response delta (small, but visible). This is the **"red/green ledger ticks as each agent speaks"** effect from Moment-C.

### Why a separate company track?

- **Narrative clarity.** Country P&L measures national outcomes; company P&L measures corporate/market consequences. Judges see both and understand the distinction.
- **Demo drama.** Watching AAPL drop in real time as the USA agent proposes sanctions creates palpable tension.
- **Novelty.** No other hackathon project will show both sovereign and corporate P&L side by side.

---

## The Demo Moments (Q8)

### Moment-C — Primary Anchor: "Live P&L Consequences"

During every debate round, the Country P&L ledger and Company Ticker both tick red/green as each agent speaks. The effect must be **visible and legible** to the judge sitting 3 meters away. This is the visceral hook.

Implementation requirements:
- P&L cells must flash at speakerTint at 40% alpha on arrival, decaying over 600ms
- Flash duration precisely tied to utterance-arrival-timestamp, not a timer
- Company ticker pauses on active speaker's company with a tint wash
- Delta magnitudes are pre-computed server-side to be visible (no sub-pixel deltas) — scale to at least 0.01 per speech round

### Moment-B — Emergent Twist: "Rhetoric Cold War"

During or after a debate, if two agents exchange N consecutive `OPPOSE`-stance utterances on the same crisis (N=4, tunable), the **RhetoricColdWarAlert** fires. The Cold War detector badge lights up — but from rhetoric, not from military actions. This is a genuinely novel narrative-emergent phenomenon.

The judge's reaction: "Wait — the cold war fired because they *argued*, not because they built weapons?"
Your response: "Yes. The emergent detector is agnostic to action modality. It catches structural polarization wherever it appears — in actions, in alliances, or in rhetoric."

This is the kind of moment judges write down in their notes.

---

## V6.1 Feature Plan

### TIER 1 — Must ship for the anchor to work (~32 hrs)

#### 1. Persona System (5 hrs — Krish)
- Create `personas/` directory with 7 markdown files: USA, CHN, RUS, IND, DPRK, SAU, UNESCO
- Each file: 40-80 lines covering voice rules, vocabulary, red lines, alliance defaults, crisis-adaptive tone shifts
- Create `data/relationships.json` — 7×7 matrix, seeded with historically plausible values
- Create `persona_loader.py` — loads persona files, injects into the LLM system prompt for each agent

#### 2. LLM Debate Orchestrator (8 hrs — Krish + Raj backend)
- New module `debate_orchestrator.py`:
  - On crisis fire: build shared world-state context
  - For each involved agent: compose system prompt = persona + relationship row + grudge memory + authority corpus (UNESCO only) + world state + MAPPO proposed action
  - Call Groq (Llama 3.3-70b) in parallel for 3–5 agents per round (only involved + peripheral)
  - Each agent returns: utterance text, stance (support/oppose/modify/neutral/mediate), mentioned_countries list
  - Aggregate into `DebateUtterance[]` stream, expose via `GET /stream/debate` SSE
- Rate limit: cap at 1 debate round per 8 simulation steps to control token cost
- Fallback: pre-generated canned debates for 5 demo scenarios, in case Groq is flaky at venue

#### 3. Vote Aggregator + Action Modifier (3 hrs — Krish)
- Count stances across voting agents (UNESCO excluded)
- If `support >= ceil(6/2) + 1` → MAPPO action executes unchanged
- If `modify > support` → re-invoke MAPPO with a constraint (e.g. "aid dispatch is required but without military escort") — implemented via a discrete action mask
- If `oppose > support` → action blocked, penalty applied to proposing country's influence
- Log vote outcomes to `debate_audit.jsonl` for reproducibility

#### 4. UNESCO Authority Corpus (2 hrs — Tushar)
- Scrape or manually transcribe 20–30 key UNESCO convention articles into `data/unesco_authority.json`
- Each entry: `{id, title, text, domain: 'heritage'|'education'|'culture'|'bioethics', authority_level: 'binding'|'advisory'}`
- `unesco_mediator.py` selects 1–3 relevant articles per UNESCO utterance based on crisis type
- UNESCO utterances that cite real articles get the `WITHIN MANDATE ✓` badge

#### 5. Debate Chamber Frontend (10 hrs — Raj, per the separate design prompt)
- `AgentPortraitStrip.tsx`
- `DebateTranscriptPanel.tsx`
- `CountryPnLLedger.tsx`
- `CompanyPnLStrip.tsx`
- `UNESCOMediatorCard.tsx`
- `RhetoricColdWarAlert.tsx`
- `ChamberView.tsx`
- `LayoutModeToggle.tsx`
- New CSS rules added to `styles/worldpolicy.css`
- All 7 acceptance criteria from the design prompt must pass

#### 6. Rhetoric Cold-War Detector (2 hrs — Krish)
- Extend `analytics.py`: monitor consecutive `OPPOSE` stances between agent pairs on the same crisis
- When threshold N=4 reached, fire `emergent_event: rhetoric_cold_war` on the existing SSE channel
- Frontend mounts `RhetoricColdWarAlert` + adds a 4th badge to `EmergentBadgePanel`

#### 7. Country & Company P&L Streams (2 hrs — Krish backend)
- `GET /stream/country-pnl` — 7-row snapshot with per-metric deltas since last tick
- `GET /stream/company-pnl` — 6 ticker rows (no company for UNESCO)
- Deltas fire on debate-utterance arrival via a backend hook in the orchestrator

### TIER 2 — Strong additions if Tier-1 done by April 26 noon (~8 hrs)

#### 8. Groq Live Debate (1 hr — Raj)
- "Generate Live Debate" button that bypasses canned fallbacks and calls Groq with current live state
- Streams utterances word-by-word into the transcript panel
- Labels: `Generated live by Meta Llama 3.3-70b via Groq · 1.8s`

#### 9. Cascade Failure Integration (3 hrs — Krish, from V6)
- Keep the V6 cascade trigger + countdown
- When cascade fires, automatically open a debate round
- `"Collapse Imminent in N steps"` countdown visible above the Debate Chamber

#### 10. Coalition-from-Rhetoric Detector (2 hrs — Krish)
- Extends existing coalition detector: 3+ agents with `SUPPORT` stance on same action for 2+ debate rounds
- Badge label: `COALITION FORMED · USA, India, EU — aid dispatch (rounds 12-14)`

#### 11. World Outcome Summary Card (2 hrs — Raj, from V6)
- Same as V6 spec, but now includes debate stats: `14 debate rounds · 3 coalitions formed · 1 rhetoric cold war`
- Full-screen modal on episode termination

### TIER 3 — Polish only if all Tier-1 and Tier-2 done (~6 hrs)

- Chamber Mode entrance animations polish
- Keyboard shortcuts: `T`=Chamber, `G`=Globe, `S`=Split, `D`=trigger demo debate
- Subtle voice effects (Web Audio API only): soft chime on vote result, low thud on rhetoric cold-war fire
- HF Spaces README update with debate screenshot + architecture diagram
- Record a 90-second sizzle reel for backup in case live demo has issues

---

## New API Endpoints (V6.1)

All V5 endpoints remain. New V6.1 endpoints:

| Endpoint | Method | Returns | Tier |
|---|---|---|---|
| `/stream/debate` | GET SSE | `DebateUtterance` events | 1 |
| `/stream/country-pnl` | GET SSE | Country P&L snapshots | 1 |
| `/stream/company-pnl` | GET SSE | Company ticker updates | 1 |
| `/crisis-involvement/{crisis_id}` | GET | `{involved, peripheral, uninvolved}` | 1 |
| `/persona/{agent_id}` | GET | Persona card (for hover tooltip details) | 1 |
| `/relationship-matrix` | GET | 7×7 live matrix | 1 |
| `/unesco-authority/{crisis_type}` | GET | Relevant articles for a crisis | 1 |
| `/vote-outcome/{round_id}` | GET | Vote tally + modified action (if any) | 1 |
| `/rhetoric-metrics` | GET | Rhetoric divergence index per agent pair | 2 |
| `/live-debate` | POST | Force a fresh Groq-streamed debate round | 2 |

Dropped from V6: `/stream/mappo`, `/stream/rulebased` (no more split screen), `/counterfactual`, `/confidence/{agent_id}`, `/replay` (deferred).

---

## 50-Hour Implementation Timeline (Revised)

### Hours 0–3: Setup Sprint
- **Krish**: verify training checkpoint loads, run `make freeze`, scaffold `debate_orchestrator.py` stub
- **Raj**: scaffold all new API endpoints with stub responses, verify SSE
- **Tushar**: scrape UNESCO authority corpus into `data/unesco_authority.json` (manual transcription is fine — 30 entries max), set up HF Space

### Hours 3–15: Core Backend (Krish primary, Raj support)
- **Krish**: persona files, relationship matrix, debate orchestrator with Groq integration (parallel per-agent calls), vote aggregator
- **Raj**: Country P&L + Company P&L stream generators, involvement calculator, rhetoric cold-war detector

### Hours 15–30: Debate Chamber Frontend (Raj primary, Tushar support)
- **Raj**: implement all 8 new components per the design prompt, wire hooks to SSE streams
- **Tushar**: UNESCO authority corpus integration, UNESCO mediator card polish, pre-generated fallback debates for 5 scenarios

### Hours 30–38: Integration + Polish
- Wire everything end-to-end
- Cascade + debate integration (Tier-2)
- Coalition-from-rhetoric detector
- World Outcome Summary Card

### Hours 38–44: Demo Rehearsal + Overnight Training
- **Krish**: run overnight MAPPO training to 50k steps in background
- **All three**: 3 full demo rehearsals (5 min hard cap each), record on phone, fix anything that felt awkward
- `make freeze` — commit `demo-freeze-v6.1`

### Hours 44–48: Freeze + Final Polish
- No new features.
- Rehearsals #4 and #5 — critique together.
- Sleep. At least 6 hours. Presenter rest > one more feature.

### Hours 48–50: Venue
- Arrive 30 min early, set up, run `make freeze` once more
- Do not open the editor unless there is a showstopper

---

## Demo Script (5 Minutes, V6.1)

**[0:00 — 0:20] Hook**
"A cyclone hits the Bay of Bengal. A UNESCO heritage site is in the flood path. Seven AI agents — six nations and UNESCO itself — are about to debate the response. Every word they speak moves a real-time profit-and-loss ledger. Let's watch."

**[0:20 — 1:00] Crisis + MAPPO Proposal**
Load Scenario 1. Cyclone fires on globe. Country P&L ledger starts ticking. MAPPO proposes `AID_DISPATCH_COORDINATED`. Debate Chamber opens in Split Mode. India's portrait pulses first — India is directly involved.

"The MAPPO policy, trained with PyTorch over 50,000 steps, proposes a coordinated aid dispatch. Now watch what the agents say about it."

**[1:00 — 2:00] The Debate**
India speaks in support. USA supports with conditions. China modifies — proposes non-tied aid. Russia opposes, citing sovereignty. As each agent speaks, the P&L ledger ticks red or green, Company ticker flashes — AAPL up, GAZP down.

"This is where it gets interesting. Every utterance changes the numbers. The debate is not theater — it is the policy explanation layer."

**[2:00 — 2:45] UNESCO Intervenes**
UNESCO portrait pulses teal. Mediator Card slides in: "Convention 1972 Article 11.4 — heritage site at risk". `WITHIN MANDATE ✓` badge.

"UNESCO is not a nation. It cannot vote. But it invokes its authority — and flags a convention that every signatory is bound by."

**[2:45 — 3:30] Moment-B: Rhetoric Cold War**
Russia and USA exchange four consecutive OPPOSE stances on follow-up sanctions. `RhetoricColdWarAlert` slides in. Cold War badge lights up.

"Notice what just happened. The Cold War detector fired — not because of military actions, but because of rhetoric. This is genuinely emergent narrative polarization. We did not script that pattern. It emerged from the persona-driven debate dynamics."

**[3:30 — 4:15] Vote + Outcome**
Vote closes: 4 support, 1 oppose, 1 modify. Action executes with Chinese modification — aid dispatch proceeds, non-tied. World outcome ticks toward stabilization. Coalition badge fires: USA + India + Saudi Arabia.

"The policy was MAPPO. The explanation was LLM. The constraint was voted. This is what explainable multi-agent RL looks like in practice."

**[4:15 — 4:45] The Evidence**
Click EvalSummaryCard. MAPPO beats rule-based by X%. Click TrainingFactsCard. Checkpoint hash visible. Open ClaimBoundaryBanner.

"Here is what is scripted and what is trained. The world events are scripted. The policy is trained. The debate layer explains the trained policy. Every claim is traceable."

**[4:45 — 5:00] Close**
World Outcome card: `HERITAGE PRESERVED · FRAGILE PEACE · RHETORIC COLD WAR ACTIVE`.

"WorldPolicy-Env V6.1. Seven agents. One policy. A debate that actually moves the needle. Built with PyTorch, Meta Llama, HuggingFace, in fifty hours."

---

## Scoring Projection: V6.1 vs V6 vs V5

| Dimension | V5 | V6 | V6.1 Target | What Changes |
|---|---|---|---|---|
| Technical Depth | 9/10 | 10/10 | **10/10** | Hybrid MAPPO+LLM with vote-modifier is publishable |
| Sponsor Stack | 9/10 | 10/10 | **10/10** | Llama drives 7 live debates per demo; HF Space; PyTorch in every badge |
| Demo Quality / Risk Mgmt | 9/10 | 10/10 | **10/10** | Single coherent anchor, canned fallbacks, 5 rehearsals |
| Novelty / Differentiation | 9/10 | 10/10 | **10/10** | Rhetoric Cold War is a phenomenon no one else has shown |
| Execution / Feasibility | 7/10 | 9/10 | **9/10** | Fewer features = shippable; anchor gets full build time |
| Judging Moment | 9/10 | 10/10 | **10/10** | P&L ticking in real time as agents speak is visceral |
| **Total** | **52/60** | **59/60** | **59/60** | **98.3% of max — same total as V6 but far higher probability of actually landing it** |

V6.1 does not score higher than V6 on paper. **It scores higher in the room.** V6 was 20 features spread thin. V6.1 is one story, one anchor, executed with depth.

---

## Judge Framing — Hybrid Story (Q10)

If asked "where is the MARL?":
> "The policy is MAPPO — multi-agent PPO, trained with PyTorch across 50,000 steps. The reward curves and evaluation summary are in the UI. The LLM debate is an *explainability and human-in-the-loop constraint layer* on top of the policy — not a replacement. You can see the decomposition: MAPPO picks, LLMs explain, vote can constrain. This is what it looks like to make a trained multi-agent policy legible to non-ML stakeholders in a real-world coordination context."

If asked "is this just Llama chatbots talking":
> "No. Each agent has a mid-depth persona with memory, relationships, and grudges, all grounded in shared world state that is driven by the MAPPO policy and the event engine. The debate affects the action only through the vote aggregator. The rhetoric is not free-form — it is structurally constrained to emit stance plus mentioned-countries, which feeds back into emergent detectors."

If asked "why UNESCO specifically":
> "UNESCO demonstrates agent heterogeneity in a principled way — it has a different action space (only mediation), a different reward structure (only heritage preservation), and it is authority-scoped to real-world conventions. It shows that our architecture supports non-state actors with bounded mandates, not just country clones."

---

## Non-Negotiable Quality Bars

Every single one must be true on demo day:

- [ ] `make freeze` shows all 7 OK
- [ ] At least one live debate round renders cleanly within 20 seconds of loading Scenario 1
- [ ] Country P&L ledger flashes on at least 3 utterances per round, not on timer
- [ ] UNESCO utterance cites a real article from `unesco_authority.json`
- [ ] `RhetoricColdWarAlert` fires at least once in Scenario 1 demo rehearsal #5
- [ ] Split Mode renders correctly at 1440×900 and 1920×1080
- [ ] Hovering and clicking portraits responds in under 200ms
- [ ] Groq fallback (canned debate) is seamless if live call fails
- [ ] ClaimBoundaryBanner is always visible
- [ ] All V5 emergent detector tests pass: `python -m pytest tests -v`
- [ ] HF Space is live and loads from presenter's phone before entering venue

---

## What Makes V6.1 Different

V6 tried to win by adding features. V6.1 wins by telling a story that each piece of code serves.

Every agent has a personality. Every persona has memory. Every utterance moves a number the judge can see. Every number has a P&L meaning they already understand. Every debate ends with a vote that can modify the MAPPO action — which means the LLMs are not decoration, they are a constraint layer. Every emergent phenomenon — including the novel rhetoric-driven cold war — is detected from the same structural signals that the V5 badges already watch.

This is not more features. This is a complete narrative loop.

**That is what 95%+ feels like in the room.**

---

*WorldPolicy-Env V6.1 Win Plan · Team: Krish · Raj · Tushar · Generated: April 25, 2026 · Supersedes V6*
