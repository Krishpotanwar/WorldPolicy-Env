# /// script
# dependencies = [
#   "accelerate>=0.34",
#   "huggingface_hub>=0.24",
#   "peft>=0.12",
#   "safetensors>=0.4",
#   "torch>=2.4",
#   "torchao>=0.16.0",
#   "transformers>=4.45",
# ]
# ///

"""Merge the WorldPolicy LoRA adapter into a standalone HF model.

Launch example:
    hf jobs uv run scripts/merge_worldpolicy_v3_hf_job.py \
      --flavor a10g-large \
      --timeout 4h \
      --secrets HF_TOKEN \
      -d
"""

import os
from pathlib import Path

import torch
from huggingface_hub import HfApi
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN missing. Launch with: --secrets HF_TOKEN")

BASE_MODEL = os.environ.get("BASE_MODEL", "unsloth/Llama-3.2-3B-Instruct")
ADAPTER_REPO = os.environ.get("ADAPTER_REPO", "krishpotanwar/worldpolicy-grpo-3b")
MERGED_REPO = os.environ.get("MERGED_REPO", "krishpotanwar/worldpolicy-grpo-3b-merged")
OUT_DIR = Path(os.environ.get("OUT_DIR", "worldpolicy-grpo-3b-merged"))
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "4096"))

print(f"Base model:     {BASE_MODEL}")
print(f"Adapter repo:   {ADAPTER_REPO}")
print(f"Merged repo:    {MERGED_REPO}")
print(f"Max model len:  {MAX_MODEL_LEN}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

print("Loading base model in fp16 ...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
    token=HF_TOKEN,
    low_cpu_mem_usage=True,
)

print("Loading tokenizer ...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, token=HF_TOKEN)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.model_max_length = MAX_MODEL_LEN

print("Loading LoRA adapter ...")
model = PeftModel.from_pretrained(model, ADAPTER_REPO, token=HF_TOKEN)

print("Merging LoRA into base weights ...")
model = model.merge_and_unload()

if hasattr(model.config, "max_position_embeddings"):
    original_ctx = getattr(model.config, "max_position_embeddings", None)
    if original_ctx and original_ctx > MAX_MODEL_LEN:
        print(f"Capping max_position_embeddings: {original_ctx} -> {MAX_MODEL_LEN}")
        model.config.max_position_embeddings = MAX_MODEL_LEN

if getattr(model, "generation_config", None) is not None:
    model.generation_config.max_length = MAX_MODEL_LEN
    model.generation_config.pad_token_id = tokenizer.pad_token_id
    model.generation_config.eos_token_id = tokenizer.eos_token_id

print("Running tiny generation smoke test ...")
prompt = (
    "You are USA, a diplomatic representative in the WorldPolicy security council.\n"
    "Active crisis: Natural Disaster\n"
    "Respond as USA in JSON with keys: text, stance, mentioned_countries, authority_citation.\n"
)
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
with torch.no_grad():
    output = model.generate(
        **inputs,
        max_new_tokens=80,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
print(tokenizer.decode(output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True))

print(f"Saving merged model to {OUT_DIR} ...")
OUT_DIR.mkdir(parents=True, exist_ok=True)
model.save_pretrained(OUT_DIR, safe_serialization=True, max_shard_size="2GB")
tokenizer.save_pretrained(OUT_DIR)

readme = OUT_DIR / "README.md"
readme.write_text(
    f"""---
base_model: {BASE_MODEL}
library_name: transformers
pipeline_tag: text-generation
tags:
- llama
- merged
- worldpolicy
- grpo
---

# WorldPolicy GRPO 3B Merged

Standalone merged model for WorldPolicy debate inference.

- Base: `{BASE_MODEL}`
- Adapter: `{ADAPTER_REPO}`
- Context capped for serving: `{MAX_MODEL_LEN}` tokens
""",
    encoding="utf-8",
)

print("Uploading merged model to Hub ...")
api = HfApi(token=HF_TOKEN)
api.create_repo(MERGED_REPO, exist_ok=True, private=True)
api.upload_folder(
    folder_path=str(OUT_DIR),
    repo_id=MERGED_REPO,
    commit_message="merge v3 grpo adapter into standalone model",
)
print(f"Pushed merged model to https://huggingface.co/{MERGED_REPO}")
