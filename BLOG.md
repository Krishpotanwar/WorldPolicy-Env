# We Gave Seven AI Agents a World Crisis and Watched Them Argue. Here's What Happened.

*By Krish, Raj, and Tushar — Team WorldPolicy-Env*
*Scaler × PyTorch × HuggingFace × Meta Hackathon · Bengaluru · April 2026*

**[Live Demo](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6) · [GitHub](https://github.com/Krishpotanwar/WorldPolicy-Env) · [Trained Model](https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b)**

---

It was 2:47 in the morning.

Raj had his head down on the desk. Tushar was staring at a terminal that had been showing the same error for forty minutes. I was on my fourth cup of coffee, reading a Wikipedia article about the 1973 oil crisis and wondering if any of this was going to work.

And then North Korea said something.

Not a real North Korean diplomat. Our AI agent — the one we'd spent the last twenty-two hours wiring into a multi-agent debate system, building persona files for, feeding relationship matrices into — responded to a crisis proposal from the USA agent with something so perfectly on-brand that all three of us started laughing at the same time.

*"The imperialist powers use disasters to extend their military reach. We will not participate in any vote that legitimizes foreign intervention under any flag."*

We weren't laughing because it was funny. We were laughing because it *worked.*

---

## The Problem We Were Actually Trying to Solve

Here's something that's been nagging at the AI research community for a while, though not many people say it out loud.

Reinforcement learning environments are getting smarter. But they're also getting more opaque. You train an agent, watch the reward curve climb, declare success — and then you have absolutely no idea *why* it made the decisions it made. The policy is a black box. The action is a number. The reasoning is gone.

That bothered us.

Every RL environment we looked at had the same blind spot: the agent acts, the world responds, the reward updates — but the *thinking* is invisible. You can't inspect it. You can't argue with it. You definitely can't explain it to anyone who wasn't already deep in the paper.

We wanted to fix that. We wanted to build an environment where the policy was *legible* — where the agent's reasoning surfaced as natural language, where you could watch it think out loud, form positions, respond to opponents, and face real consequences for bad decisions.

Geopolitics is the sharpest version of this problem. Nations don't just act — they debate, negotiate, threaten, concede, and form alliances in real time, under pressure, with incomplete information. If you can make an RL agent navigate *that*, you've built something that teaches reasoning, not just pattern matching.

---

## What We Built (The 60-Second Version)

**WorldPolicy-Env** is a fully [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-compliant reinforcement learning environment where six country agents and one institutional mediator debate live global crises, vote on policy resolutions, and receive a multi-objective reward signal grounded in real-world data.

Every episode starts with a crisis pulled from live news. Agents respond with structured diplomatic actions. Those actions trigger a debate — spoken, in character, with distinct political voices. The debate produces a vote. The vote triggers a reward calculation across five geopolitical objectives. The next step begins.

The whole stack:

| Layer | What it does |
|---|---|
| **OpenEnv environment** (`environment.py`) | `reset()` / `step()` / `state()` contract — compatible with any GRPO or PPO loop |
| **MOGSR reward grader** (`graders.py`) | 4-layer multi-objective reward: Security · Diplomacy · Coalition · Economic · Humanitarian |
| **Debate orchestrator** (`debate_orchestrator.py`) | Groq Llama 3.3-70b live, or canned fallback — 7 agents speak in character |
| **PyTorch StabilityScorer** (`pytorch_scorer.py`) | 6-layer MLP estimating world stability from economic + diplomatic features |
| **Live data pipeline** (`live_data.py`, `market_data.py`) | GDELT crises + World Bank P&L + yfinance prices + GDELT sentiment — four layers, all with fallback |
| **React frontend** (`WorldPolicy V6.1.html`) | Rotating globe, debate transcript, P&L ledger, coalition arcs, sentiment chips |
| **GRPO-trained model** | `krishpotanwar/worldpolicy-grpo-3b` — Llama 3.2-3B fine-tuned on MOGSR reward |

---

## The Team Walked In Not Ready. That's the Truth.

Let me be honest about something: when we sat down at our table on the first morning, we were not a polished, synchronized team with a pre-built stack and a detailed execution plan.

Raj is brilliant at ML training loops. He can read a loss curve the way some people read music. But multi-agent debate systems? New territory. Tushar handles frontend like breathing — React components materializing from nothing — but he'd never touched an RL reward grader. I'd read enough papers on MARL to sound dangerous in a conversation, but I'd never built an OpenEnv-compliant environment from scratch.

We had overlapping knowledge and just enough shared stubbornness to figure out the gaps as we went.

The first two hours were just us arguing about scope. Not in a bad way — in the way that actually produces good ideas, where you say something ridiculous and someone else trims it into something possible. We kept the ridiculous parts. We trimmed what we had to.

By hour four, we had a name. By hour six, we had a structure. By hour eight, we'd committed to something that felt, honestly, a little too ambitious for a 48-hour window.

We did it anyway.

---

## Building the World (Seven Agents at a Time)

The core idea sounds simple when you say it fast. Seven AI agents representing real nations — the USA, China, Russia, India, North Korea, Saudi Arabia, and UNESCO — debate live global crises, vote on policy resolutions, and receive a reward signal based on how well they stabilize the world.

The execution is not simple at all.

Every agent needed a *character*. Not just a system prompt. A real persona — with historical context, alliance defaults, red lines, vocabulary preferences, and crisis-specific behavioral shifts. North Korea doesn't talk the same way during a natural disaster as it does during an arms race. Saudi Arabia proposes deals differently when oil is involved. The USA leans on "partners" when it's building coalitions and pivots to unilateral framing when things fall apart.

We wrote seven character files. Forty to eighty lines each. Raj kept poking at the North Korea one, convinced it wasn't unhinged enough. Tushar printed out the UNESCO persona and read it aloud at the table to make sure it sounded institutional without sounding wooden. I rewrote the Russia file three times because it kept being either too reasonable or cartoonishly villainous, and the truth sits somewhere much more uncomfortable in the middle.

UNESCO got its own special treatment.

UNESCO doesn't vote. That's a hard constraint — not a suggestion, a hard rule baked into the system. When the council votes on a resolution, UNESCO speaks but doesn't cast a ballot. Every utterance it makes has to cite a specific article from its authority corpus — a hand-built JSON file of 30 World Heritage Convention articles, UNESCO Education for All clauses, and cultural protection mandates. If UNESCO steps outside its mandate, the system flags it.

That credibility gating was one of the best decisions we made.

Because in the live demo, when the UNESCO agent invokes Article 11.4 of the 1972 Convention to protect a heritage site in the disaster zone — and the citation is *real* — judges stop scanning their phones and start paying attention.

---

## How It All Connects (The Architecture)

There's a version of this section where we draw a perfect diagram and everything looks clean and intentional. The truth is messier and more interesting.

Here's the actual data flow, the way we understand it now that we've lived inside it:

```
GDELT / World Bank / yfinance / GDELT Sentiment
        ↓
    /reset() — crisis headline + P&L baselines + relationship matrix + stability score
        ↓
  Policy chooses action: propose_resolution | form_coalition | veto | invoke_article | sanction
        ↓
    /step(action) → DebateOrchestrator runs one full debate round
        ↓
    7 agents speak in turn — Groq Llama 3.3-70b (live) or canned fallback
    UNESCO mediates, cites authority corpus, cannot vote
        ↓
    Vote tally computed — UNESCO excluded
        ↓
    PyTorch StabilityScorer estimates world stability before and after the action
        ↓
    MOGSR Grader computes reward:
      R = Immediate(S·D·C·E·H) + γ·V(s') + λ·(actual - null_action) + β·robustness
      Hard penalties: nuclear_escalation = -1.0, episode terminates
        ↓
    Updated observation returned — P&L deltas, relationship matrix, stability score, round summary
        ↓
    Next step (or done if max_steps / crisis_resolved / catastrophe)
```

The part that isn't obvious from a diagram: the PyTorch model runs twice per step. Once for the actual action's stability estimate. Once for the counterfactual — what would stability look like if the agent had just abstained? The difference between those two numbers is the counterfactual advantage term. It forces the reward to ask not just "was this good?" but "was this *better than doing nothing*?" That's the question worth teaching.

The whole backend is a single FastAPI server built with `openenv.core.env_server.http_server.create_app`, which wires the standard OpenEnv contract endpoints automatically. We add our demo routes on top. One container, port 7860, runs everything.

---

## The Thing That Almost Sank Us

The reward function.

We knew going in that this was the most important piece. The hackathon is explicit: 40% of the score is environment innovation, but 20% is showing *improvement in rewards*. You can't show improvement without a real signal to improve on. A reward function that's just +1 for passing a resolution and -1 for failing is not a reward function — it's a coin flip counter.

So we designed MOGSR. Multi-Objective Geopolitical Stability Reward.

The idea: agents aren't rewarded for passing resolutions. They're rewarded for making the world more stable across five dimensions simultaneously — Security, Diplomacy, Coalition quality, Economic impact, and Humanitarian outcomes. The weights shift depending on the crisis. A cyclone disaster weights Humanitarian at 45%. An arms race weights Security at 45%. A trade war flips the weight toward Economic. You can't game it with one behavior.

On top of that, a 4-layer stack: immediate reward, long-horizon value estimate, counterfactual advantage (how much better did you do than if you'd done nothing?), and shock robustness. Plus hard constraint penalties. Nuclear escalation is -1.0. Episode terminates. Full stop.

The first version didn't work.

At all.

Every agent was scoring the same. The reward was essentially flat. We spent two hours staring at `graders.py` wondering why our beautifully named functions were producing identical outputs. Raj finally found it at 1:15 AM: a normalization bug that was collapsing the entire range into a 0.02-wide band. One line. Fixed in thirty seconds after ninety minutes of confusion.

The curves started moving. We celebrated quietly because it was too late to celebrate loudly.

---

## When the PyTorch Model Walked So the LLM Could Run

Here's a design decision we're genuinely proud of — and one I don't think we'd have landed on without the time pressure forcing us to prioritize.

The hackathon requires a real PyTorch model. Not a wrapper. Not a call to someone else's API. Something you trained, something that's doing real inference in the critical path.

We built the StabilityScorer.

It's a 6-layer MLP — deliberately not large, deliberately not fancy — that takes the per-country economic and diplomatic feature vector (12 dimensions: normalized GDP and mean relationship trust for each of the six sovereign agents) and outputs a stability estimate between 0 and 1. Trains in under thirty seconds on synthetic episodes. Weights bake into the Docker image at build time so there's no cold-start cost.

But here's the part that matters: the StabilityScorer drives the counterfactual advantage term. At every step, before we compute the real reward, we ask — *what would stability look like if the agent had just abstained?* Then we measure how much better or worse the actual action did compared to that baseline.

This means the reward isn't just "did the vote pass." It's "did your action move the needle beyond what doing nothing would have achieved." That's a much harder thing to learn. And that's exactly what the GRPO training signal picks up on.

The PyTorch model isn't decoration. It's the backbone of the counterfactual architecture.

---

## 48 Hours. Four Live Data APIs. Zero Sleep.

We decided early that the environment shouldn't be synthetic.

Most RL environments are islands. The world inside them is consistent, controlled, predictable — which is useful for research and terrible for demonstrating that your environment reflects reality. We wanted live data. Four layers of it.

GDELT pulls real crisis headlines every sixty seconds. When a real cyclone hits the news, the environment sees it on the next `/reset`. World Bank feeds real GDP and military spend baselines into the country P&L at episode start. yfinance pulls real equity prices — AAPL, BYD, Reliance, Aramco, the indices — and they scroll across the bottom of the demo screen while the agents are arguing about them. GDELT sentiment gives each agent a public opinion score, derived from actual news tone, injected into their persona prompts before they speak.

Every layer has a fallback. The environment never crashes on a network blip. Static seeds kick in silently and everything keeps running. We needed this because HF Spaces can be unpredictable, especially with cold starts, and we weren't about to let an API timeout kill the demo in front of judges.

Tushar built the four-layer data pipeline in a single twelve-hour stretch. By the time he was done, he'd read more World Bank API documentation than any person should have to read in a single sitting. The yfinance layer was supposed to take two hours and took six because the package's column names are, let's say, *informally documented*.

Worth it.

When the MARKETS LIVE badge lights up green and real stock prices are scrolling next to a debate about a trade war between the USA and China agents — that's a moment that's hard to explain and easy to feel.

---

## Task 3. The One That Changed Everything.

We built three graduated tasks. Easy, medium, hard.

Task 1 is a natural disaster. USA and India are primary responders. The humanitarian weight is high. A good policy can resolve it in five steps. Task 2 is a trade war. You need a coalition to pass anything, so pure-veto strategies fail. Medium weight on economic objectives.

Task 3 is an arms race with a North Korea nuclear escalation trigger at step 4.

Here's what that means in practice. The episode starts. You have four steps to build a coalition — USA, China, Russia, and UN working together — and invoke a UN authority article before the trigger fires. If no coalition forms by step 4, the `nuclear_escalation` hard penalty hits: -1.0, episode terminates, normalized reward collapses.

The heuristic baseline scores 0.13 on Task 3. Consistently. Because rule-based policies respond to the visible crisis, not the hidden timer. They don't know to form coalitions *first*.

The GRPO-trained model scores 0.99.

It learned — from the reward signal alone, from running rollouts through the environment, from watching what happens when the penalty fires — that the first two steps need to be `form_coalition` actions. It doesn't know about DPRK. It doesn't have the escalation trigger in its context. It just learned that coalition-first strategies avoid catastrophic outcomes in this crisis type.

Watching that curve go from 0.13 to 0.99 over 200 training steps was one of those moments where all three of us went quiet for a second.

This is what reinforcement learning is supposed to feel like.

---

## The Results, Plainly Stated

We know judges need numbers. Here they are, from `training_results/benchmark_results.json`, reproducible with `python benchmark_reward.py`:

| Task | Crisis | Heuristic baseline | GRPO-trained | Improvement |
|---|---|---|---|---|
| Task 1 (easy) | Natural disaster | 0.9695 | 0.9967 | **+2.7%** |
| Task 2 (medium) | Trade war | 0.9204 | 0.9819 | **+6.2%** |
| Task 3 (hard) | Arms race + nuclear trigger | 0.1314 | 0.9937 | **+86.2%** |
| **Average** | | **0.6738** | **0.9908** | **+31.7%** |

Scores normalized to [0, 1] via `(tanh(cumul_reward / max_steps × 2) + 1) / 2`.

One honest note: Tasks 1 and 2 baselines are higher than their target reward ranges suggest. That's a reward design limitation — easy tasks don't stress the grader enough to separate heuristic from trained. Task 3 is where the signal is real. An 86-point improvement is not noise. It's the trained model learning to cooperate under a deadline the heuristic never understood existed.

The reward curve is in `training_results/reward_curve.png`. The model is at [`krishpotanwar/worldpolicy-grpo-3b`](https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b).

---

## The Demo Has a Heartbeat

We spent the last four hours of the hackathon on the demo flow. Not the backend. Not the reward function. The *experience* of watching it run.

Because we'd figured something out: the technology is impressive, but it's invisible until you can *see* it.

So the globe rotates. Country dots glow. When India speaks, India's region pulses. When a coalition forms between USA, India, and Saudi Arabia, alliance arcs animate between them in real time. The agent portrait strip shows seven faces — each with a sentiment chip reflecting the GDELT tone score for their country right now, today, this morning's news — and the speaking portrait gets a live pulse when that agent is generating an utterance.

The debate transcript scrolls. Each utterance gets a stance badge: SUPPORTS, OPPOSES, MODIFIES, MEDIATES. The color-coded left rail pulses when that agent is active. The vote bar fills in when the round ends. The UNESCO mediator card surfaces when it invokes a heritage article. The World Outcome card drops in when the vote resolves.

The P&L ledger is the most satisfying part. Every speech that has an economic consequence — Saudi Arabia committing to reconstruction funding, Russia opposing NATO deployment — causes the ledger to flash. GDP deltas tick. Welfare scores shift. It's not a simulation of consequences. It *is* the reward function, visualized in real time.

That's the thing we most wanted judges to feel: the connection between what the agents say and what the world does in response.

---

## The Challenges We Didn't Expect

Every project has the challenges you plan for and the ones that blindside you at the worst possible moment. We had both.

**The reward normalization bug** took ninety minutes to find and thirty seconds to fix. A single normalization step was collapsing our entire multi-objective reward range into a 0.02-wide band. Every agent looked identical in the grader's eyes. That bug existed in the most critical component — the thing the judges score most heavily — and we almost shipped it. Raj caught it at 1:15 AM.

**The yfinance column naming.** We will not elaborate further. Six hours. Informally documented. Moving on.

**The async/sync boundary in the environment.** OpenEnv's `step()` is synchronous. Our debate orchestrator is async. Calling `asyncio.run()` inside a FastAPI route that was already running an event loop caused silent deadlocks the first time we tested the full end-to-end flow. The fix — `run_coroutine_threadsafe` — took two hours to land on and ten minutes to implement.

**The canned debate versus live path.** Getting the frontend to correctly consume SSE from the live Groq debate, handle mid-stream errors, and fall back to the canned sequence gracefully — without any visible flicker in the UI — was the one place where Tushar had to rewrite the same function three times. The third version works. We're keeping the third version.

None of these were glamorous. All of them made the final product more solid.

---

## What We Got Wrong (The Honest Part)

The heuristic baseline scores high on Tasks 1 and 2. Higher than the target reward ranges. That means easy and medium tasks don't stress-test the grader enough to clearly separate heuristic from trained behavior. We noticed this and flagged it in the README. It's a reward design gap, not a performance claim, and the fix is tighter task calibration.

The frontend scripted debate is a fixed 14-utterance sequence. It's carefully written — real political tensions, UNESCO mediator arc, coalition dynamics — but it's still a script. The live Groq path is genuinely dynamic. Without a Groq API key in the Space settings, the live button falls back to the canned sequence. Judges should know which one they're seeing.

The StabilityScorer runs on synthetic data. It's not econometric modeling. P&L movements are heuristic deltas, not macro projections. This is an RL training environment, not a forecasting system.

We built something real. It just has real limits too.

---

## How to Run This Yourself

We want any judge, reviewer, or curious builder to be able to reproduce everything we claimed. Here's how:

**Run the server locally:**
```bash
git clone https://github.com/Krishpotanwar/WorldPolicy-Env.git
cd WorldPolicy-Env
pip install -r requirements.txt
python server.py          # binds 0.0.0.0:7860
```

**Or with Docker (matches the HF Spaces build exactly):**
```bash
docker build -t worldpolicy-env .
docker run -p 7860:7860 worldpolicy-env
```

**Run the evaluation / reproduce the benchmark table:**
```bash
python benchmark_reward.py     # no server, no API key needed
```

**Run the full inference pipeline with the trained model:**
```bash
export HF_TOKEN="hf_..."
export MODEL_NAME="krishpotanwar/worldpolicy-grpo-3b"
python inference.py            # runs all 3 tasks, emits [START]/[STEP]/[END] logs
python inference.py --no-llm   # heuristic-only mode, no token cost
```

**Enable live Groq debate:**
```bash
export GROQ_API_KEY="gsk_..."
python server.py
# Then open http://localhost:7860 → click "Live Debate (Groq)"
```

The `scorer_weights.pt` file isn't committed to the repo. It's generated at Docker build time by `RUN python pytorch_scorer.py`. If you're running locally without Docker, run `python pytorch_scorer.py` once first.

---

## What's Next

We didn't ship everything on the list. That was the plan — pick an anchor, serve the anchor, cut everything else.

But there are a few things we genuinely want to build after the hackathon:

**Grudge memory across episodes.** Right now each episode resets the relationship matrix to a static seed. The real version updates relationships based on who voted against whom and keeps that history across sessions. DPRK's relationship with the USA should degrade over repeated sanctions. That dynamic is in the code structure; it's not surfaced in the frontend yet.

**Tighter task calibration.** The easy and medium tasks need grader weight adjustments so the heuristic baseline stays inside the target reward ranges. That's a two-hour fix with the right benchmarking loop.

**A real MAPPO policy layer.** Right now the "policy" is a GRPO-tuned LLM making structured action decisions. We'd like to also train a proper MAPPO agent that uses the OpenEnv step/reset interface natively — so the LLM debate becomes the explainability wrapper for an underlying neural policy, not the policy itself.

**More crisis types.** We have thirteen crisis types defined in the system. We shipped three tasks. The others — sanctions, regime change, cultural destruction, education collapse — are real crisis categories with distinct reward weight profiles already in `graders.py`. They just need task definitions and a few more training rollouts.

---

## What Fifty Hours Taught Us

There's a version of this project that we could have built by stacking twenty features and calling it done. We had a list that long at the start. The WIN plan — what we called our strategy document — told us to cut it. Pick one anchor. Build it to ship quality. Everything else serves that anchor or gets dropped.

The anchor was the debate chamber. Everything — the reward function, the live data, the globe, the PyTorch scorer, the OpenEnv compliance — everything serves the moment when you watch seven AI agents argue about a real global crisis in real time and you can *understand* why each one is saying what it's saying.

We didn't build a geopolitical forecasting system. We're three college students at a 48-hour hackathon. What we built is something smaller and more interesting: a training environment where the policy is legible, the consequences are grounded in real data, and the reward signal is honest enough to teach a 3-billion-parameter model to build coalitions before nuclear timers expire.

Raj said it best somewhere around 4 AM, when the training curve had finally started climbing on Task 3.

*"It's not predicting the world. It's teaching the model to think about it."*

That felt like enough.

---

## Try It Yourself

The environment is live. The source is open. The model is on the Hub.

**[→ Open the live demo](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6)**

Click **Run Demo**. Wait for the crisis to escalate. Then hit **Trigger Debate** and watch what happens when seven AI agents with distinct voices, real grudges, and a live humanitarian clock try to agree on anything.

Then hit **Live Debate (Groq)** if you want to see what happens when the script goes away entirely and the world has to improvise.

**[→ Browse the source](https://github.com/Krishpotanwar/WorldPolicy-Env)**

**[→ Load the trained model](https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b)**

---

*Thanks to the Scaler, PyTorch, HuggingFace, and Meta teams for the platform and the problem space. Thanks to the GDELT project, the World Bank, and the yfinance maintainers whose open data made the live layers possible. And thanks to the UNESCO World Heritage Convention, 1972 — whose actual articles made our mediator feel less like a feature and more like a character.*

*— Krish, Raj, Tushar · Bengaluru · April 2026*
