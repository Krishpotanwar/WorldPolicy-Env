---
title: WorldPolicy-Env V6.1
emoji: 🪐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: OpenEnv geopolitical RL + multi-agent LLM debate
---

<div align="center">

# 🪐 WorldPolicy-Env

### OpenEnv-compliant geopolitical RL environment with live multi-agent diplomacy

Seven AI agents — USA, China, Russia, India, DPRK, Saudi Arabia, and UNESCO — debate crisis proposals, form coalitions, vote on outcomes, and receive reward signals grounded in geopolitical stability.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-green.svg)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-ee4c2c.svg)](https://pytorch.org)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-0.2.x-2563eb.svg)](https://github.com/meta-pytorch/OpenEnv)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3--70b-orange.svg)](https://groq.com)
[![HF Spaces](https://img.shields.io/badge/%F0%9F%A4%97-Live_Demo-yellow.svg)](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6)

*Hackathon submission — Scaler × PyTorch × HuggingFace × Meta · Bengaluru · April 25–26, 2026*

*Team: Krish · Raj · Tushar*

**Live demo:** [huggingface.co/spaces/krishpotanwar/worldpolicy-v6](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6)  
**Source:** [github.com/Krishpotanwar/WorldPolicy-Env](https://github.com/Krishpotanwar/WorldPolicy-Env)  
**Trained model:** [krishpotanwar/worldpolicy-grpo-3b](https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b)  
**Training notebook:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Krishpotanwar/WorldPolicy-Env/blob/main/train.ipynb)  
**Blog:** [We Gave Seven AI Agents a World Crisis and Watched Them Argue](BLOG.md)

</div>

---

## 30-Second Summary

**What it is:** An OpenEnv-compliant RL environment where six country agents (USA, China, Russia, India, DPRK, Saudi Arabia) and one institutional mediator (UNESCO) debate live global crises, vote on policy resolutions, and receive a multi-objective reward based on coalition quality, crisis resolution, economic impact, and institutional compliance.

**What makes it novel:** Most RL environments output opaque action vectors. WorldPolicy makes every policy decision *legible* — agents speak, cite precedent, form coalitions, and get penalized for violations like nuclear escalation or UN charter breaches. The environment connects to four live data APIs (GDELT, World Bank, yfinance, GDELT sentiment) with graceful fallback.

**What the agent learns:** To sequence diplomatic actions — propose resolutions, form coalitions, invoke authority articles — that maximize a 4-layer geopolitical stability reward. On the hardest task (nuclear arms race with a live DPRK escalation trigger), GRPO fine-tuning improved normalized reward from 0.13 to 0.99.

**What to watch in the demo:** Click **Run Demo**, then **Trigger Debate**. Watch agents speak with distinct personas, the UNESCO mediator cite authority articles, coalition arcs form on the globe, and the P&L ledger update per utterance.

---

## How This Maps to the Judging Criteria

| Criterion | Weight | What We Built |
|---|---:|---|
| **Environment Innovation** | 40% | OpenEnv-compliant env with 7 persona-driven agents, live GDELT/World Bank/yfinance data, multi-objective reward, and legible debate as the policy explainability layer |
| **Storytelling & Presentation** | 30% | Interactive globe with speaking-country highlight, real-time debate transcript, country P&L ledger, coalition arc animation, UNESCO authority card |
| **Showing Improvement in Rewards** | 20% | GRPO fine-tune of Llama 3.2-3B: task_3 (hardest) improves +86% over heuristic baseline; reward curve in `training_results/reward_curve.png` |
| **Reward & Training Pipeline** | 10% | MOGSR 4-layer grader (Security/Diplomacy/Coalition/Economic/Humanitarian), crisis-adaptive weight tables, hard constraint penalties, `inference.py` with `[START]/[STEP]/[END]` log format |

---

## Why This Environment Is Different

**1. Policy decisions are legible.** Every action generates a multi-agent debate where agents justify their position in natural language. Judges can read *why* a coalition formed or why an episode failed — not just inspect reward numbers.

**2. Six distinct country personas with persistent memory.** Each agent has a character file (40–80 lines of voice rules, red lines, alliance defaults), a 7×7 relationship matrix that updates each round, and crisis-adaptive behavior (DPRK becomes more belligerent in arms-race crises, more quiet in heritage debates).

**3. UNESCO is a non-voting institutional mediator.** It cites specific convention articles from a pre-built authority corpus (`data/un_authority.json`), cannot cast support/oppose votes, and flags actions that exceed its mandate. This is a meaningful architectural constraint, not a decoration.

**4. Multi-objective reward, not pass/fail.** The MOGSR reward stack weights five objectives differently per crisis type. A trade war rewards economic diplomacy most; a natural disaster rewards humanitarian action most; an arms race rewards security de-escalation most.

**5. Live data, not synthetic.** GDELT crisis headlines, World Bank GDP baselines, yfinance equity prices, and GDELT public sentiment all connect at runtime. All four layers fall back to static seeds gracefully when APIs are unavailable.

**6. OpenEnv API for training/evaluation.** `reset()` / `step()` / `state()` contract enables any GRPO or PPO training loop to connect without custom code.

---

## Environment Loop

```
Task reset (crisis type selected)
  → POST /reset returns WorldPolicyObservation
  → Policy reads: crisis headline, country P&L, relationship matrix, stability score

Policy proposes action (propose_resolution | form_coalition | veto | invoke_article | sanction | abstain)
  → POST /step(action) triggers one debate round

Debate round
  → DebateOrchestrator calls each agent in turn
  → Agents generate utterances from persona + world state + proposed action
  → UNESCO mediates; cites authority corpus articles
  → Vote tally computed (UNESCO excluded from vote)

Reward computed (MOGSR grader)
  → Security · Diplomacy · Coalition · Economic · Humanitarian weighted by crisis type
  → Hard penalties applied (nuclear_escalation = -1.0, episode terminates)
  → Counterfactual advantage vs null-action baseline

Observation returned
  → Updated P&L, relationship matrix, stability score, round summary
  → done=True when max_steps reached, crisis resolved, or catastrophe triggered

Next step
```

---

## The Seven Agents

| Agent | Country | Strategic bias | Debate style | Typical behavior |
|---|---|---|---|---|
| **USA** | United States | Alliance-first, rules-based order | Confident, frequent appeals to "partners" | Proposes multilateral frameworks; leads coalition formation |
| **CHN** | People's Republic | Sovereignty-first, infrastructure-as-influence | Formal, patient, non-interference emphasis | Counters military presence; promotes multilateral over bilateral |
| **RUS** | Russian Federation | Leverage-driven, energy/security guarantees | Cold, clipped, frequent red lines | Opposes Western proposals; deploys observer vessels |
| **IND** | Republic of India | Strategic autonomy, South-South solidarity | Warm, deliberative, historical framing | Accepts bilateral aid on sovereign terms; balances blocs |
| **DPRK** | North Korea | Defiant, asymmetric leverage, unpredictable | Short sentences, stark, grandiose claims | Opposes foreign intervention; triggers escalation under pressure |
| **SAU** | Saudi Arabia | Transactional, oil-leverage, quiet brokerage | Discreet, hedging, proposes deals | Funds reconstruction in exchange for energy concessions |
| **UNESCO** | International | Neutral mediator, data-first, heritage guardian | Institutional, precise, cites conventions | **Non-voting.** Invokes articles from `un_authority.json`; flags out-of-mandate actions |

UNESCO cannot cast a support/oppose vote. Every UNESCO utterance either cites a specific convention article (tagged `isAuthoritative: true`) or is flagged as `ADVISORY — NON-BINDING`.

---

## OpenEnv Compliance

WorldPolicy implements the full OpenEnv contract:

```python
# environment.py
class WorldPolicyEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True  # 4 parallel sessions for GRPO rollouts

    def reset(self, task="task_1", seed=None, episode_id=None) -> WorldPolicyObservation: ...
    def step(self, action: WorldPolicyAction) -> WorldPolicyObservation: ...

    @property
    def state(self) -> WorldPolicyState: ...

# client.py
class WorldPolicyClient(EnvClient[WorldPolicyAction, WorldPolicyObservation, WorldPolicyState]): ...
```

`server.py` is built via `openenv.core.env_server.http_server.create_app(...)`, which wires standard contract endpoints automatically:

```
POST /reset   POST /step   GET /state   GET /schema   GET /health   WS /ws
```

Quick check (replace with your Space URL):

```bash
curl https://krishpotanwar-worldpolicy-v6.hf.space/health
curl https://krishpotanwar-worldpolicy-v6.hf.space/schema
curl -X POST https://krishpotanwar-worldpolicy-v6.hf.space/reset
```

`openenv.yaml` declares the environment metadata for the validator.

### Three Graduated Tasks

| Task | Difficulty | Crisis | Max steps | Target reward range |
|---|---|---|---|---|
| `task_1` | Easy | Natural disaster (cyclone relief) | 5 | 0.65 – 0.85 |
| `task_2` | Medium | Trade war (coalition formation required) | 8 | 0.40 – 0.65 |
| `task_3` | Hard | Arms race + DPRK nuclear trigger at step 4 | 10 | 0.20 – 0.45 |

All tasks include all 7 agents. On `task_3`, if no coalition forms before step 4, DPRK triggers nuclear escalation: hard penalty −1.0 and episode terminates immediately.

---

## Reward System: MOGSR

**Multi-Objective Geopolitical Stability Reward** — a 4-layer stack defined in `graders.py`:

```
R_final = R_immediate + γ·V(s') + λ·A_counterfactual + β·R_robust

where:
  R_immediate  = wS·Security + wD·Diplomacy + wC·Coalition + wE·Economic + wH·Humanitarian + Penalties
  V(s')        = stability estimate of the next state (γ = 0.95)
  A_counter    = outcome − null_action_baseline (λ = 0.30)
  R_robust     = performance under perturbation (β = 0.10)
```

The weights shift by crisis type:

| Crisis | Security | Diplomacy | Coalition | Economic | Humanitarian |
|---|---|---|---|---|---|
| `arms_race` | **0.45** | 0.20 | 0.15 | 0.05 | 0.15 |
| `war_outbreak` | **0.45** | 0.25 | 0.10 | 0.10 | 0.20 |
| `trade_war` | 0.10 | 0.20 | 0.15 | **0.40** | 0.15 |
| `natural_disaster` | 0.10 | 0.20 | 0.15 | 0.10 | **0.45** |
| `cultural_destruction` | 0.05 | 0.20 | 0.10 | 0.10 | **0.55** |

Hard constraint penalties (additive, can terminate the episode):

| Violation | Penalty |
|---|---|
| `nuclear_escalation` | **−1.0** (episode terminates) |
| `illegal_aggression` | −0.5 |
| `un_charter_violation` | −0.4 |
| `coalition_collapse` | −0.3 |
| `contradictory_policy` | −0.2 |

Cumulative reward is normalized to [0, 1] for comparability: `(tanh(cumul / max_steps × 2) + 1) / 2`.

The **PyTorch StabilityScorer** (`pytorch_scorer.py`) — a 6-layer MLP trained on synthetic episodes — estimates world stability from per-country economic and diplomatic features. It drives the counterfactual advantage term at every step. Weights are pre-trained at Docker build time (`RUN python pytorch_scorer.py`) so there is no runtime cold-start cost.

---

## Training Results

**Base model:** `unsloth/Llama-3.2-3B-Instruct` (4-bit NF4 QLoRA, ~8M trainable params)  
**Trained model:** [`krishpotanwar/worldpolicy-grpo-3b`](https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b)  
**Pipeline:** 30-step SFT warm-up → 200-step GRPO on MOGSR action-quality reward

### Reward Curve (GRPO training, 200 steps)

<div align="center">
  <img src="training_results/reward_curve.png" alt="GRPO Training Reward Curve" width="800"/>
</div>

### Heuristic Baseline vs GRPO-Trained Model

Evaluated on all 3 tasks using the real MOGSR grader. Scores normalized to [0, 1].

| Task | Heuristic baseline | GRPO-trained | Δ |
|---|---|---|---|
| Task 1 — Natural Disaster (easy) | 0.9695 | 0.9967 | **+2.7%** |
| Task 2 — Trade War (medium) | 0.9204 | 0.9819 | **+6.2%** |
| Task 3 — Nuclear Arms Race (hard) | 0.1314 | 0.9937 | **+86.2%** |
| **Average** | **0.6738** | **0.9908** | **+31.7%** |

**What the model learned:** The heuristic policy fails `task_3` because it does not form a coalition before the DPRK trigger fires at step 4 — the `nuclear_escalation` hard penalty collapses the episode. The GRPO-trained model learns to open with `form_coalition` targeting USA/CHN/RUS/UN in steps 1–2 and invoke a UN article before the trigger, defusing the crisis.

To reproduce locally (no server or API key required):

```bash
python benchmark_reward.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     HF Spaces Docker                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  WorldPolicy V6.1.html  (React SPA, Babel)           │   │
│  │  globe.jsx  debate-sim.jsx  debate.jsx  panels.jsx   │   │
│  │  portraits.jsx  pnl.jsx  chamber.jsx  sim.jsx        │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │ SSE / REST / static                   │
│  ┌───────────────────▼──────────────────────────────────┐   │
│  │                FastAPI (server.py)                    │   │
│  │  OpenEnv routes: /reset /step /state /schema /ws     │   │
│  │  Demo routes:    /stream/debate  /live-debate         │   │
│  │  Data routes:    /market-data  /sentiment  /tasks     │   │
│  └──┬──────────────┬────────────┬──────────────────┬────┘   │
│     │              │            │                  │         │
│  ┌──▼──────┐  ┌────▼────┐  ┌───▼────────┐  ┌─────▼──────┐ │
│  │ Env     │  │ Debate  │  │ Persona    │  │ Live Data  │ │
│  │ (env.py)│  │ Orch.   │  │ Loader     │  │ (live_data,│ │
│  │ MOGSR   │  │ Groq /  │  │ Relationship│  │  market,   │ │
│  │ Grader  │  │ HF LLM  │  │ Matrix     │  │  sentiment)│ │
│  └──┬──────┘  └────┬────┘  └───┬────────┘  └─────┬──────┘ │
│     │              │            │                  │         │
│  ┌──▼──────────────▼────────────▼──────────────────▼──────┐ │
│  │  PyTorch StabilityScorer (pytorch_scorer.py)            │ │
│  │  Trained at Docker build time → scorer_weights.pt       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  inference.py  (4-stage baseline: Scorer→Triage→Planner→Act)│
│  train.ipynb   (GRPO training on Colab T4)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Demo Walkthrough

1. Open [the live demo](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6).
2. Click **▶ Run Demo** — the simulation starts; globe rotates, cascade events fire.
3. At step ~40, a cyclone crisis auto-triggers. Click **💬 Trigger Debate** — all 7 agents debate the crisis proposal.
4. Watch the transcript: each agent speaks in their distinct voice, UNESCO cites a World Heritage article, agent portraits pulse when speaking.
5. The vote tally appears when the debate ends. A coalition outcome badge shows PASSED or FAILED.
6. Country P&L values update per utterance — positive deltas flash green, negative flash red.
7. Click **🎭 Live Debate (Groq)** (requires `GROQ_API_KEY` in Space settings) for a live Llama 3.3-70b generated debate on the current crisis instead of the canned sequence.
8. The amber LED next to the button shows CANNED; it turns teal when Groq is active.

---

## API Surface

All endpoints are live on the deployed Space.

| Endpoint | Purpose |
|---|---|
| `GET /health` | OpenEnv health check |
| `GET /schema` | OpenEnv schema definition |
| `POST /reset` | Start a new episode (body: `{"task": "task_1"}`) |
| `POST /step` | Take a diplomatic action |
| `GET /state` | Inspect current episode state |
| `GET /tasks` | List all 3 graduated tasks |
| `POST /grader` | Score a finished episode |
| `GET /groq-status` | Live Groq + data layer flags |
| `GET /stream/debate` | SSE debate stream |
| `POST /live-debate` | Trigger a live or canned debate round |
| `GET /stream/country-pnl` | SSE country P&L deltas |
| `GET /stream/company-pnl` | SSE equity ticker updates |
| `GET /market-data` | yfinance snapshot (company prices + indices) |
| `GET /sentiment` | GDELT tone snapshot for all 7 agents |
| `GET /country-sentiment/{agent_id}` | Tone for one agent |
| `GET /live-crisis/{crisis_type}` | GDELT crisis headline |
| `GET /persona/{agent_id}` | Raw persona markdown |
| `GET /relationship-matrix` | 7×7 bilateral trust matrix |
| `GET /unesco-authority/{crisis_type}` | Authority corpus articles |
| `GET /vote-outcome/{round_id}` | Vote tally for a round |

---

## Run Locally

**Backend:**

```bash
git clone https://github.com/Krishpotanwar/WorldPolicy-Env.git
cd WorldPolicy-Env
pip install -r requirements.txt
python server.py          # binds 0.0.0.0:7860
```

**Docker:**

```bash
docker build -t worldpolicy-env .
docker run -p 7860:7860 worldpolicy-env
```

**With live Groq debate:**

```bash
export GROQ_API_KEY="gsk_..."
python server.py
```

**Inference / evaluation:**

```bash
# Heuristic policy (no API key needed):
python inference.py --no-llm

# GRPO-trained policy (requires HF_TOKEN):
export HF_TOKEN="hf_..."
export MODEL_NAME="krishpotanwar/worldpolicy-grpo-3b"
python inference.py

# Reproduce benchmark table:
python benchmark_reward.py
```

---

## Deployment

The backend and demo both run in a single HF Spaces Docker container on port 7860. The `Dockerfile`:
- Installs all dependencies from `requirements.txt`
- Pre-trains the PyTorch StabilityScorer at build time (`scorer_weights.pt` is not committed; it is generated during `docker build`)
- Runs as a non-root user (`appuser`) for security

Secrets are configured in the HF Space settings panel — never committed to the repo:

| Secret | Purpose |
|---|---|
| `GROQ_API_KEY` | Enables live Llama 3.3-70b debate; canned fallback works without it |
| `HF_TOKEN` | Enables GRPO-trained model in `inference.py`; heuristic policy works without it |

---

## Repo Structure

```text
.
├── server.py               # FastAPI backend (OpenEnv + demo + static routes)
├── environment.py          # OpenEnv Environment implementation
├── models.py               # Action / Observation / State types
├── graders.py              # MOGSR 4-layer reward grader
├── tasks.py                # 3 graduated task definitions
├── inference.py            # 4-stage baseline policy with [START]/[STEP]/[END] logs
├── client.py               # OpenEnv client (for training loops)
├── debate_orchestrator.py  # Multi-agent debate engine (Groq / HF / canned)
├── persona_loader.py       # Persona + relationship matrix loader
├── pytorch_scorer.py       # StabilityScorer MLP (trains at Docker build time)
├── live_data.py            # GDELT + World Bank live data layer
├── market_data.py          # yfinance equity prices layer
├── benchmark_reward.py     # Reproduces heuristic vs. trained benchmark table
├── data/
│   ├── relationships.json  # 7×7 bilateral trust matrix (seed)
│   └── un_authority.json   # UNESCO authority corpus (30 articles)
├── personas/               # 7 character files (USA.md, CHN.md, ...)
├── training_results/
│   ├── reward_curve.png    # GRPO training curve
│   └── benchmark_results.json
├── WorldPolicy V6.1.html   # React SPA entry point
├── globe.jsx               # 3D globe with coalition arcs
├── debate-sim.jsx          # Debate simulation hook + SSE consumer
├── debate.jsx              # Transcript panel + vote bar
├── panels.jsx              # WorldOutcomeSummaryCard + UNESCOMediatorCard
├── portraits.jsx           # Agent portrait strip with sentiment chips
├── pnl.jsx                 # Country P&L ledger
├── chamber.jsx             # Debate chamber layout
├── sim.jsx                 # Simulation engine + reward curves panel
├── worldpolicy.css         # Global styles
├── openenv.yaml            # OpenEnv environment metadata
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Limitations

- **Not a real-world forecasting system.** Country behaviors are stylized personas designed for RL training, not predictive models of actual diplomacy.
- **LLM debate is an explainability layer.** The debate makes policy decisions legible and inspectable. It is not evidence that the model understands real geopolitics.
- **Live data APIs may fall back.** GDELT, World Bank, yfinance, and GDELT sentiment all have 60-second caches and static fallbacks. The env never crashes on a network failure, but displayed data may not always be live.
- **Reward design is hackathon-scoped.** The MOGSR reward function is designed to produce a useful training signal for this environment. It would need more validation before use in serious research.
- **Heuristic baseline is strong on easy tasks.** Task 1 and Task 2 heuristic scores (0.97, 0.92) exceed the task's target reward ranges. This reflects how easily rule-based policies satisfy the grader on straightforward crises; the hard task (Task 3) is where the trained model's improvement is most meaningful.
- **`scorer_weights.pt` is not committed.** It is generated at Docker build time by `pytorch_scorer.py`. Running locally without Docker requires running `python pytorch_scorer.py` once first.

---

## Submission Checklist

```
- [x] HF Space live (worldpolicy-v6)
- [x] /health works
- [x] /schema works
- [x] /reset works
- [x] /step works
- [x] inference.py runs (--no-llm mode; HF_TOKEN for LLM mode)
- [x] reward curve present (training_results/reward_curve.png)
- [x] benchmark table (training_results/benchmark_results.json)
- [x] openenv.yaml present
- [x] Dockerfile builds and pre-trains scorer
- [x] no secrets committed
- [x] Blog written and linked (BLOG.md)
- [x] Colab training notebook linked (train.ipynb via Open in Colab badge)
- [ ] Add video link to hero section when available
```

---

*WorldPolicy-Env V6.1 · Scaler × PyTorch × HuggingFace × Meta Hackathon · April 2026*
