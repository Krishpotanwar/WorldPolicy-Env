"""Merge LoRA adapter into base model and push to HuggingFace Hub.

The original model (krishpotanwar/worldpolicy-grpo-3b) is a PEFT LoRA adapter
that cannot be served by HF Inference Router. This script merges the adapter
weights into the base model and pushes the result as a standalone transformers
model that can be served directly.

Usage:
    pip install peft transformers torch huggingface_hub
    huggingface-cli login
    python merge_and_push.py
"""
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "unsloth/Llama-3.2-3B-Instruct"
ADAPTER_REPO = "krishpotanwar/worldpolicy-grpo-3b"
MERGED_REPO = "krishpotanwar/worldpolicy-grpo-3b-merged"

print(f"Loading base model: {BASE_MODEL}")
base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16, device_map="cpu"
)
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_REPO)

print(f"Loading LoRA adapter: {ADAPTER_REPO}")
model = PeftModel.from_pretrained(base, ADAPTER_REPO)

print("Merging weights...")
merged = model.merge_and_unload()

print("Saving locally...")
merged.save_pretrained("./worldpolicy-grpo-3b-merged")
tokenizer.save_pretrained("./worldpolicy-grpo-3b-merged")

print(f"Pushing to Hub: {MERGED_REPO}")
merged.push_to_hub(MERGED_REPO, private=False)
tokenizer.push_to_hub(MERGED_REPO, private=False)

print(f"Done. Model at: https://huggingface.co/{MERGED_REPO}")
