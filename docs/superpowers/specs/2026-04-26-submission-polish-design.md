# Submission Polish — WorldPolicy-Env
**Date:** 2026-04-26  
**Deadline:** 5PM IST today  
**Scope:** README result visualization (mandatory) + quick polish. No code changes. No retraining.

---

## Goal

Make the existing quality visible to judges before 5PM. All minimum requirements are already met and all files are live on the HF Space. This plan only improves discoverability and judge-facing presentation.

---

## Safety

Before any changes:
```bash
git tag submission-backup
```
Rollback if anything breaks:
```bash
git checkout submission-backup -- .
git push space main --force
```

---

## Change 1 — Benchmark Table in README (mandatory)

**File:** `README.md`  
**Where:** Under the existing `<img src="training_results/reward_curve.png" .../>` in the Training Results section.

Add immediately after the image tag:

```markdown
| Task | Crisis | Heuristic baseline | GRPO-trained | Improvement |
|---|---|---|---|---|
| Task 1 (easy) | Natural disaster | 0.9695 | 0.9967 | +2.7% |
| Task 2 (medium) | Trade war | 0.9204 | 0.9819 | +6.2% |
| Task 3 (hard) | Arms race + nuclear trigger | 0.1314 | 0.9937 | **+86.2%** |

> **Task 3 is where the signal is real:** the trained model learned to prioritize
> coalition-building before the DPRK nuclear escalation trigger fires at step 4 —
> a strategy the heuristic never discovered.
```

Numbers sourced directly from `training_results/benchmark_results.json`. No new artifacts needed.

---

## Change 2 — Quick Links in README

**File:** `README.md`  
**Where:** The existing `## 🚀 Quick Links` section.

Add two lines:

```markdown
- **📝 Blog post:** [BLOG.md](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6/blob/main/BLOG.md)
- **📓 Training notebook:** [train.ipynb](https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6/blob/main/train.ipynb)
```

---

## Change 3 — Roadmap Fix in README

**File:** `README.md`  
**Where:** The `## 🛣️ Roadmap` table.

Update three rows from `⏭ Open` to `✅ Shipped`:

| Row | Old status | New status |
|---|---|---|
| `train.ipynb` Colab GRPO notebook | ⏭ Open | ✅ Shipped |
| Reward curve plot + before/after comparison | ⏭ Open | ✅ Shipped |
| Sizzle reel / 90s demo video | ⏭ Open | ✅ Replaced by BLOG.md |

---

## Change 4 — Expand openenv.yaml

**File:** `openenv.yaml`  
**Current (6 lines):**
```yaml
spec_version: 1
name: worldpolicy_env
type: space
runtime: fastapi
app: server:app
port: 7860
```

**New:**
```yaml
spec_version: 1
name: worldpolicy_env
description: >
  OpenEnv-compliant multi-agent geopolitical RL environment. Seven AI agents
  debate live crises pulled from GDELT, with World Bank GDP baselines, yfinance
  market data, and GDELT public sentiment. MOGSR 4-layer reward with
  crisis-adaptive weights and nuclear-escalation hard penalty.
type: space
runtime: fastapi
app: server:app
port: 7860
tags:
  - reinforcement-learning
  - multi-agent
  - geopolitics
  - llm
  - grpo
authors:
  - krishpotanwar
```

---

## Change 5 — Commit and Push

```bash
git add README.md openenv.yaml
git commit -m "docs: add benchmark table, fix roadmap, expand openenv manifest for submission"
git push space main
```

---

## Submission Form URLs

| Field | Value |
|---|---|
| HF Space URL | `https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6` |
| Training Notebook URL | `https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6/blob/main/train.ipynb` |
| Blog Post URL | `https://huggingface.co/spaces/krishpotanwar/worldpolicy-v6/blob/main/BLOG.md` |

---

## What Is Not Changing

- `graders.py` — no reward weight changes (Option C dropped; honest limitation already documented in blog)
- `environment.py`, `server.py`, any backend Python — no changes
- `train.ipynb` — no changes
- `training_results/` — no changes (numbers already correct)
- No retraining required
