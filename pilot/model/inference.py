#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch

@torch.inference_mode()
def generate_output(model, tokenizer, params, device, context_len=2048):
    prompt = params["prompt"]
    temperature = float(params.get("temperature", 1.0))
    max_new_tokens = int(params.get("max_new_tokens", 256))
    stop_parameter = params.get("stop", None)
    if stop_parameter == tokenizer.eos_token:
        stop_parameter = None
    stop_strings = []
    if isinstance(stop_parameter, str):
        stop_strings.append(stop_parameter)
    elif isinstance(stop_parameter, list):
        stop_strings = stop_parameter
    elif stop_parameter is None:
        pass
    else:
        raise TypeError("Stop parameter must be string or list of strings.")

    pos = -1
    input_ids = tokenizer(prompt).input_ids
    output_ids = []

    max_src_len = context_len - max_new_tokens - 8
    input_ids = input_ids[-max_src_len:]

    for i in range(max_new_tokens):
        if i == 0:
            out = model(torch.as_tensor([input_ids], device=device), use_cache=True)
            logits = out.logits
            past_key_values = out.past_key_values
        else:
            out = model(
                input_ids=torch.as_tensor([[token]], device=device),
                use_cache=True,
                past_key_values=past_key_values,
            )
            logits = out.logits
            past_key_values = out.past_key_values

        last_token_logits = logits[0][-1]

        if temperature < 1e-4:
            token = int(torch.argmax(last_token_logits))
        else:
            probs = torch.softmax(last_token_logits / temperature, dim=-1)
            token = int(torch.multinomial(probs, num_samples=1))

        output_ids.append(token)

        if token == tokenizer.eos_token_id:
            stopped = True
        else:
            stopped = False

        output = tokenizer.decode(output_ids, skip_special_tokens=True)
        for stop_str in stop_strings:
            pos = output.rfind(stop_str)
            if pos != -1:
                output = output[:pos]
                stopped = True
                break
            else:
                pass

        if stopped:
            break

    del past_key_values
    if pos != -1:
        return output[:pos]
    return output


@torch.inference_mode()
def get_embeddings(model, tokenizer, prompt):
    input_ids = tokenizer(prompt).input_ids
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    input_embeddings = model.get_input_embeddings().to(device)

    embeddings = input_embeddings(torch.LongTensor([input_ids]).to(device))
    mean = torch.mean(embeddings[0], 0).cpu().detach()
    return mean.to(device)
