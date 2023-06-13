#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import threading
import sys
import time


def gpt4all_generate_stream(model, tokenizer, params, device, max_position_embeddings):
    stop = params.get("stop", "###")
    prompt = params["prompt"]
    role, query = prompt.split(stop)[1].split(":")
    print(f"gpt4all, role: {role}, query: {query}")

    def worker():
        model.generate(prompt=query, streaming=True)

    t = threading.Thread(target=worker)
    t.start()

    while t.is_alive():
        yield sys.stdout.output
        time.sleep(0.01)
    t.join()
