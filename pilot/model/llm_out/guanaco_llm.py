import torch
from threading import Thread
from transformers import TextIteratorStreamer, StoppingCriteriaList, StoppingCriteria


def guanaco_generate_output(model, tokenizer, params, device, context_len=2048):
    """Fork from: https://github.com/KohakuBlueleaf/guanaco-lora/blob/main/generate.py"""

    print(params)
    stop = params.get("stop", "###")
    prompt = params["prompt"]
    query = prompt
    print("Query Message: ", query)

    input_ids = tokenizer(query, return_tensors="pt").input_ids
    input_ids = input_ids.to(model.device)

    streamer = TextIteratorStreamer(
        tokenizer, timeout=10.0, skip_prompt=True, skip_special_tokens=True
    )
    stop_token_ids = [0]

    class StopOnTokens(StoppingCriteria):
        def __call__(
            self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs
        ) -> bool:
            for stop_id in stop_token_ids:
                if input_ids[0][-1] == stop_id:
                    return True
            return False

    stop = StopOnTokens()

    generate_kwargs = dict(
        input_ids=input_ids,
        max_new_tokens=512,
        temperature=1.0,
        do_sample=True,
        top_k=1,
        streamer=streamer,
        repetition_penalty=1.7,
        stopping_criteria=StoppingCriteriaList([stop]),
    )

    t1 = Thread(target=model.generate, kwargs=generate_kwargs)
    t1.start()

    generator = model.generate(**generate_kwargs)
    for output in generator:
        # new_tokens = len(output) - len(input_ids[0])
        decoded_output = tokenizer.decode(output)
        if output[-1] in [tokenizer.eos_token_id]:
            break

        out = decoded_output.split("### Response:")[-1].strip()

        yield out


def guanaco_generate_stream(model, tokenizer, params, device, context_len=2048):
    """Fork from: https://github.com/KohakuBlueleaf/guanaco-lora/blob/main/generate.py"""
    tokenizer.bos_token_id = 1
    print(params)
    stop = params.get("stop", "###")
    prompt = params["prompt"]
    max_new_tokens = params.get("max_new_tokens", 512)
    temerature = params.get("temperature", 1.0)

    query = prompt
    print("Query Message: ", query)

    input_ids = tokenizer(query, return_tensors="pt").input_ids
    input_ids = input_ids.to(model.device)

    streamer = TextIteratorStreamer(
        tokenizer, timeout=10.0, skip_prompt=True, skip_special_tokens=True
    )

    tokenizer.bos_token_id = 1
    stop_token_ids = [0]

    class StopOnTokens(StoppingCriteria):
        def __call__(
            self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs
        ) -> bool:
            for stop_id in stop_token_ids:
                if input_ids[-1][-1] == stop_id:
                    return True
            return False

    stop = StopOnTokens()

    generate_kwargs = dict(
        input_ids=input_ids,
        max_new_tokens=max_new_tokens,
        temperature=temerature,
        do_sample=True,
        top_k=1,
        streamer=streamer,
        repetition_penalty=1.7,
        stopping_criteria=StoppingCriteriaList([stop]),
    )

    model.generate(**generate_kwargs)

    out = ""
    for new_text in streamer:
        out += new_text
        yield out
