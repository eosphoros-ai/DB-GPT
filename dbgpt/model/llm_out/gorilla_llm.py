import torch


@torch.inference_mode()
def generate_stream(
    model, tokenizer, params, device, context_len=42048, stream_interval=2
):
    """Fork from https://github.com/ShishirPatil/gorilla/blob/main/inference/serve/gorilla_cli.py"""
    prompt = params["prompt"]
    l_prompt = len(prompt)
    max_new_tokens = int(params.get("max_new_tokens", 1024))
    stop_str = params.get("stop", None)

    input_ids = tokenizer(prompt).input_ids
    output_ids = list(input_ids)
    input_echo_len = len(input_ids)
    max_src_len = context_len - max_new_tokens - 8
    input_ids = input_ids[-max_src_len:]
    past_key_values = out = None

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

        probs = torch.softmax(last_token_logits, dim=-1)
        token = int(torch.multinomial(probs, num_samples=1))
        output_ids.append(token)

        if token == tokenizer.eos_token_id:
            stopped = True
        else:
            stopped = False

        if i % stream_interval == 0 or i == max_new_tokens - 1 or stopped:
            tmp_output_ids = output_ids[input_echo_len:]
            output = tokenizer.decode(
                tmp_output_ids,
                skip_special_tokens=True,
                spaces_between_special_tokens=False,
            )
            pos = output.rfind(stop_str, l_prompt)
            if pos != -1:
                output = output[:pos]
                stopped = True
            yield output

        if stopped:
            break

    del past_key_values
