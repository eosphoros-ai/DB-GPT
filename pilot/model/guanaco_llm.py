import torch
from threading import Thread
from transformers import TextIteratorStreamer, StoppingCriteriaList, StoppingCriteria
from pilot.conversation import ROLE_ASSISTANT, ROLE_USER

def guanaco_generate_output(model, tokenizer, params, device, context_len=2048):
    """Fork from fastchat: https://github.com/KohakuBlueleaf/guanaco-lora/blob/main/generate.py"""
    stop = params.get("stop", "###")
    messages = params["prompt"].split(stop)


    hist = []
    for i in range(1, len(messages) - 2, 2):
        hist.append(
            (
                messages[i].split(ROLE_USER + ":")[1],
                messages[i + 1].split(ROLE_ASSISTANT + ":")[1],
            )
        )
    

    text = + "".join(["".join([f"### USER: {item[0]}\n",f"### Assistant: {item[1]}\n",])for item in hist[:-1]])
    text += "".join(["".join([f"### USER: {hist[-1][0]}\n",f"### Assistant: {hist[-1][1]}\n",])])


    query = messages[-2].split(ROLE_USER + ":")[1]
    print("Query Message: ", query)

    input_ids = tokenizer(query, return_tensors="pt").input_ids
    input_ids = input_ids.to(model.device)

    streamer = TextIteratorStreamer(tokenizer, timeout=10.0, skip_prompt=True, skip_special_tokens=True)
    stop_token_ids = [0]
    class StopOnTokens(StoppingCriteria):
        def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
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
        stopping_criteria=StoppingCriteriaList([stop])
    )


    t1 = Thread(target=model.generate, kwargs=generate_kwargs)
    t1.start()

    generator =  model.generate(**generate_kwargs)
    for output in generator:
        # new_tokens = len(output) - len(input_ids[0])
        decoded_output = tokenizer.decode(output)
        if output[-1] in [tokenizer.eos_token_id]:
            break

        out = decoded_output.split("### Response:")[-1].strip()

        yield out

