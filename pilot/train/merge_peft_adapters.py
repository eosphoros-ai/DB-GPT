from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
import sys
import os
import argparse

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)
from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG
CFG = Config()
model_path = LLM_MODEL_CONFIG[CFG.LLM_MODEL]

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model_name_or_path", type=str, default=model_path)
    parser.add_argument("--peft_model_path", type=str, default="train/output/checkpoint-10/adapter_model")
    parser.add_argument("--output_dir", type=str, default="train/output/merged_models/")
    parser.add_argument("--device", type=str, default="cpu")

    return parser.parse_args()

def main():
    args = get_args()

    print(f"Loading base model: {args.base_model_name_or_path}")
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model_name_or_path,
        return_dict=True,
        torch_dtype=torch.float16,
        trust_remote_code=True
    )

    print(f"Loading PEFT: {args.peft_model_path}")
    model = PeftModel.from_pretrained(base_model, args.peft_model_path)
    model.to(args.device)
    print(f"Running merge_and_unload")
    model = model.merge_and_unload() # https://github.com/huggingface/peft/blob/main/src/peft/tuners/lora.py#L382

    tokenizer = AutoTokenizer.from_pretrained(args.base_model_name_or_path)

    model.save_pretrained(f"{args.output_dir}")
    tokenizer.save_pretrained(f"{args.output_dir}")
    print(f"Model saved to {args.output_dir}")

if __name__ == "__main__" :
    main()