# WorldPolicy-Env Environment Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all broken subsystems that caused evaluation failure — model serving, market data, fallback logic, and README accuracy.

**Architecture:** Five independent fixes: (1) merge LoRA adapter into servable model on HF, (2) replace delisted Russian tickers, (3) add circuit breaker for HF model calls, (4) fix README to match reality, (5) improve startup diagnostics. User handles training curve image separately.

**Tech Stack:** Python 3.11, PyTorch, PEFT/transformers, yfinance, FastAPI, HuggingFace Hub

---

### Task 1: Merge LoRA Adapter into Servable Model

The model `krishpotanwar/worldpolicy-grpo-3b` is a PEFT LoRA adapter (48.7 MB delta weights). HF Inference Router cannot serve adapters — it needs full merged weights tagged as `transformers` with `pipeline_tag: text-generation`.

**Files:**
- Create: `merge_and_push.py` (one-shot script, run locally with GPU/CPU)

- [ ] **Step 1: Create the merge script**

```python
"""Merge LoRA adapter into base model and push to HuggingFace Hub.

Run once locally:
    pip install peft transformers torch huggingface_hub
    python merge_and_push.py
"""
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "unsloth/Llama-3.2-3B-Instruct"
ADAPTER_REPO = "krishpotanwar/worldpolicy-grpo-3b"
MERGED_REPO = "krishpotanwar/worldpolicy-grpo-3b-merged"

print("Loading base model...")
base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16, device_map="cpu"
)
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_REPO)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(base, ADAPTER_REPO)

print("Merging weights...")
merged = model.merge_and_unload()

print("Saving locally...")
merged.save_pretrained("./worldpolicy-grpo-3b-merged")
tokenizer.save_pretrained("./worldpolicy-grpo-3b-merged")

print("Pushing to Hub...")
merged.push_to_hub(MERGED_REPO, private=False)
tokenizer.push_to_hub(MERGED_REPO, private=False)

print(f"Done. Model at: https://huggingface.co/{MERGED_REPO}")
```

- [ ] **Step 2: Run the merge script locally**

```bash
pip install peft transformers torch huggingface_hub
huggingface-cli login  # enter HF_TOKEN
python merge_and_push.py
```

Expected: Model pushed to `krishpotanwar/worldpolicy-grpo-3b-merged` with full weights, `library_name: transformers`, `pipeline_tag: text-generation`.

- [ ] **Step 3: Verify model is servable**

Go to `https://huggingface.co/krishpotanwar/worldpolicy-grpo-3b-merged` and check that "Inference Providers" shows at least one provider (e.g., HF Inference API, Featherless, etc.). If no provider picks it up within ~10 minutes, the model may need a `config.json` fix or manual endpoint deployment.

- [ ] **Step 4: Update default MODEL_NAME in debate_orchestrator.py**

In `debate_orchestrator.py` line 46, change the default:

```python
# Before:
_HF_MODEL    = os.environ.get("MODEL_NAME", "krishpotanwar/worldpolicy-grpo-3b")
# After:
_HF_MODEL    = os.environ.get("MODEL_NAME", "krishpotanwar/worldpolicy-grpo-3b-merged")
```

- [ ] **Step 5: Update default MODEL_NAME in inference.py**

In `inference.py` line 76, change the default:

```python
# Before:
MODEL_NAME = os.environ.get("MODEL_NAME", "krishpotanwar/worldpolicy-grpo-3b")
# After:
MODEL_NAME = os.environ.get("MODEL_NAME", "krishpotanwar/worldpolicy-grpo-3b-merged")
```

- [ ] **Step 6: Update .env.example**

Update the MODEL_NAME example to reference the merged model.

- [ ] **Step 7: Commit**

```bash
git add merge_and_push.py debate_orchestrator.py inference.py .env.example
git commit -m "fix: use merged model weights for HF Inference serving"
```

---

### Task 2: Fix Delisted Russian Market Tickers

`GAZP.ME` (Gazprom) and `ROSN.ME` (Rosneft) are delisted from Moscow Exchange via yfinance. They spam 12 warning lines per page load and never return live data.

**Files:**
- Modify: `market_data.py:53-76`

- [ ] **Step 1: Test replacement tickers**

```bash
python3 -c "
import yfinance as yf
for sym in ['OGZPY', 'ROSYY', 'MOEX.ME', 'ERUS']:
    t = yf.Ticker(sym)
    try:
        h = t.history(period='2d')
        print(f'{sym}: {len(h)} rows, last={h[\"Close\"].iloc[-1] if len(h) else \"NONE\"}')
    except Exception as e:
        print(f'{sym}: FAILED — {e}')
"
```

Pick whichever tickers return data. Likely candidates:
- `OGZPY` — Gazprom ADR (OTC)
- `ROSYY` — Rosneft ADR (OTC)
- `ERUS` — iShares MSCI Russia ETF (if still trading)
- If none work, set `yf: None` like DPRK and rely on fallback values cleanly.

- [ ] **Step 2: Update COMPANY_TICKERS in market_data.py**

Replace GAZP entry (line 58). Example if OGZPY works:

```python
"GAZP":  {"yf": "OGZPY",       "name": "Gazprom",    "countryId": "RUS",  "currency": "$",
          "fallback_price": 3.42, "fallback_pct": -2.1},
```

If no ADR works, set `yf: None` for clean fallback:

```python
"GAZP":  {"yf": None,           "name": "Gazprom",    "countryId": "RUS",  "currency": "₽",
          "fallback_price": 142.00, "fallback_pct": -2.1},
```

- [ ] **Step 3: Update COUNTRY_INDEX_TICKERS in market_data.py**

Replace ROSN.ME entry (line 72). Example if ERUS works:

```python
"RUS":  "ERUS",       # iShares MSCI Russia ETF
```

If nothing works:

```python
"RUS":  None,         # Moscow Exchange tickers sanctions-blocked; uses fallback
```

- [ ] **Step 4: Verify no more "delisted" warnings**

```bash
python3 -c "from market_data import get_market_snapshot; import json; print(json.dumps(get_market_snapshot(), indent=2))"
```

Expected: No "possibly delisted" warnings in stderr. RUS data shows either live prices or clean fallback values.

- [ ] **Step 5: Commit**

```bash
git add market_data.py
git commit -m "fix: replace delisted Russian tickers to stop log spam"
```

---

### Task 3: Add Circuit Breaker for HF Model Calls

When the primary HF model is unservable, all 7 country agents can fail sequentially with identical errors. Add a primary-model circuit breaker that skips repeated primary calls after the first unsupported-model failure, while still trying `MODEL_NAME_FALLBACK`.

**Files:**
- Modify: `debate_orchestrator.py:577-648`

- [ ] **Step 1: Add circuit breaker state to DebateOrchestrator.__init__**

After line 490 in `__init__`, add:

```python
self._hf_circuit_open = False
self._hf_circuit_opened_at: float = 0.0
```

- [ ] **Step 2: Add circuit breaker check method**

After `_map_countries` method (after line 575), add:

```python
def _hf_circuit_tripped(self) -> bool:
    if not self._hf_circuit_open:
        return False
    if time.time() - self._hf_circuit_opened_at > 300:
        self._hf_circuit_open = False
        return False
    return True
```

- [x] **Step 3: Integrate circuit breaker into _call_hf_model**

After building the prompt, skip only the primary model when the circuit is open:

```python
skip_primary = self._hf_circuit_tripped()
if skip_primary:
    last_err = RuntimeError("HF primary circuit breaker open")
```

After the `print(f"⚠️  HF model call failed...")` line (614), add circuit breaker trigger:

```python
if "model_not_supported" in str(e) or "not supported by any provider" in str(e):
    self._hf_circuit_open = True
    self._hf_circuit_opened_at = time.time()
    print("🔌 Primary HF model unsupported; trying fallback model for 5min")
    break
```

- [ ] **Step 4: Test that circuit breaker fires**

Start server, trigger a debate. First agent should fail primary and trip the breaker. Remaining agents should skip primary HF calls and try `MODEL_NAME_FALLBACK` before local/canned fallback. Log should show one primary `⚠️` + one `🔌`, then fallback-model calls.

- [ ] **Step 5: Commit**

```bash
git add debate_orchestrator.py
git commit -m "fix: add circuit breaker to skip HF calls after model_not_supported"
```

---

### Task 4: Fix README Model Documentation

README claims the trained model runs on HF Inference. After Task 1 (merge), this becomes true — but the model name changes. Also update the training results section to be accurate.

**Files:**
- Modify: `README.md:414-430` (model setup section)
- Modify: `README.md:67-84` (training results section)

- [ ] **Step 1: Update model name references in README**

Line 414: Change `krishpotanwar/worldpolicy-grpo-3b` → `krishpotanwar/worldpolicy-grpo-3b-merged` (3 occurrences in setup section, lines 414, 423, 439).

- [ ] **Step 2: Add note about LoRA vs merged**

After line 430, add a note:

```markdown
> **Note:** The original LoRA adapter lives at `krishpotanwar/worldpolicy-grpo-3b`.
> The merged (servable) model is at `krishpotanwar/worldpolicy-grpo-3b-merged`.
> The merged version is required for HF Inference Router — LoRA adapters cannot be served directly.
```

- [ ] **Step 3: Update training results section to match actual data**

User will replace `training_results/reward_curve.png` locally with a correct image. Once replaced, verify the table at lines 75-79 matches the new image's numbers. If the benchmark_results.json numbers are correct (from a separate evaluation run, not the training curve), keep them. If not, update to match reality.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update model name to merged version, clarify LoRA vs merged"
```

---

### Task 5: Improve Startup Diagnostics

The startup log says `hf_model=True` even when the model can't be served. Make it actually probe the model.

**Files:**
- Modify: `debate_orchestrator.py:487-514` (DebateOrchestrator.__init__)

- [ ] **Step 1: Add model availability check to __init__**

Replace the print statement at lines 510-514 with a smarter diagnostic:

```python
hf_status = "none"
if self._hf_clients:
    hf_status = f"configured ({_HF_MODEL})"
groq_status = "ready" if self._groq_client else "not configured"

print(
    f"DebateOrchestrator initialized. "
    f"backend={self._backend} mode={mode} "
    f"hf_model={hf_status} groq={groq_status}"
)
if self._backend == "none":
    print("⚠️  No live debate backend available. Debates will use canned responses.")
```

- [ ] **Step 2: Commit**

```bash
git add debate_orchestrator.py
git commit -m "fix: improve startup diagnostics with model name and backend status"
```

---

### Task 6: Fill Out HuggingFace Model Card

The model card at `krishpotanwar/worldpolicy-grpo-3b` (and the new merged repo) is entirely empty template.

**Files:**
- Create locally: `model_card.md` (to be pushed to HF repo)

- [ ] **Step 1: Write model card**

```markdown
---
language:
  - en
license: apache-2.0
library_name: transformers
pipeline_tag: text-generation
base_model: meta-llama/Llama-3.2-3B-Instruct
tags:
  - geopolitics
  - rl
  - grpo
  - worldpolicy
  - openenv
---

# WorldPolicy GRPO 3B (Merged)

Fine-tuned Llama-3.2-3B-Instruct for multi-agent geopolitical debate simulation.

## Training

- **Method:** GRPO (Group Relative Policy Optimization) via TRL
- **Base model:** unsloth/Llama-3.2-3B-Instruct
- **Adapter:** LoRA (rank 16, alpha 32)
- **Target modules:** q_proj, k_proj, v_proj, o_proj, up_proj, down_proj, gate_proj
- **Training environment:** Google Colab + HF Spaces (WorldPolicyEnv v6.1)
- **Reward function:** MOGSR (Multi-Objective Geopolitical Stability Reward) — 4-layer stack combining stability score, GDP delta, relationship improvement, and authority citation bonus

## Intended Use

Multi-agent debate simulation where 7 AI country agents (USA, CHN, RUS, IND, DPRK, SAU, UN) negotiate crisis responses. The model generates JSON-formatted diplomatic utterances with stance, mentioned countries, and optional UN authority citations.

## Limitations

- Trained on simulated geopolitical scenarios — not a source of real policy advice
- 3B parameter model; larger models produce higher-quality debate utterances
- LoRA fine-tune with limited training steps; Groq Llama 3.3-70b produces better quality when available
```

- [ ] **Step 2: Push model card to both repos**

```bash
# Push to merged repo
huggingface-cli upload krishpotanwar/worldpolicy-grpo-3b-merged model_card.md README.md

# Also update original adapter repo
huggingface-cli upload krishpotanwar/worldpolicy-grpo-3b model_card.md README.md
```

- [ ] **Step 3: Commit the model card to this repo**

```bash
git add model_card.md
git commit -m "docs: add HuggingFace model card for GRPO fine-tune"
```

---

## Execution Order

Tasks 1-5 are mostly independent. Recommended order:

1. **Task 2** (Russian tickers) — quickest, no external dependencies
2. **Task 3** (circuit breaker) — code-only, testable immediately
3. **Task 5** (startup diagnostics) — small change, pairs with Task 3
4. **Task 1** (merge model) — requires local GPU/CPU time + HF push
5. **Task 4** (README) — do after Task 1 so model name is finalized
6. **Task 6** (model card) — do after Task 1 so merged repo exists

## Out of Scope (User Handles)

- Replacing `training_results/reward_curve.png` with correct image
- Updating `benchmark_results.json` if numbers are wrong
- Re-running GRPO training for more steps
