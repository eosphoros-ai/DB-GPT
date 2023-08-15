from typing import Dict
import torch


@torch.inference_mode()
def generate_stream(model, tokenizer, params: Dict, device: str, context_len: int):
    # Just support LlamaCppModel
    return model.generate_streaming(params=params, context_len=context_len)
