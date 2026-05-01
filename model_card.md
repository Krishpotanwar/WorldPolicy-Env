---
language:
  - en
license: apache-2.0
library_name: transformers
pipeline_tag: text-generation
base_model: unsloth/Llama-3.2-3B-Instruct
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
- **Training steps:** 200
- **Training environment:** Google Colab + HF Spaces (WorldPolicyEnv v6.1)
- **Reward function:** MOGSR (Multi-Objective Geopolitical Stability Reward) — 4-layer stack combining stability score, GDP delta, relationship improvement, and authority citation bonus
- **Training reward:** Before μ=0.492 → After μ=0.504 (+2.4%)

## Intended Use

Multi-agent debate simulation where 7 AI country agents (USA, CHN, RUS, IND, DPRK, SAU, UN) negotiate crisis responses. The model generates JSON-formatted diplomatic utterances with stance, mentioned countries, and optional UN authority citations.

## Limitations

- Trained on simulated geopolitical scenarios — not a source of real policy advice
- 3B parameter model with limited training steps; larger models produce higher-quality debate utterances
- Groq Llama 3.3-70b produces better quality when available and is the recommended primary backend
- Training reward shows marginal improvement at 200 steps — longer runs needed to exceed 0.7 target
