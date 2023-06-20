#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os

import pandas as pd
import torch
import transformers
from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    get_peft_model_state_dict,
    prepare_model_for_int8_training,
)
from transformers import LlamaForCausalLM, LlamaTokenizer

from pilot.configs.config import Config
from pilot.configs.model_config import DATA_DIR, LLM_MODEL_CONFIG

device = "cuda" if torch.cuda.is_available() else "cpu"
CUTOFF_LEN = 50

df = pd.read_csv(os.path.join(DATA_DIR, "BTC_Tweets_Updated.csv"))

CFG = Config()


def sentiment_score_to_name(score: float):
    if score > 0:
        return "Positive"
    elif score < 0:
        return "Negative"
    return "Neutral"


dataset_data = [
    {
        "instruction": "Detect the sentiment of the tweet.",
        "input": row_dict["Tweet"],
        "output": sentiment_score_to_name(row_dict["New_Sentiment_State"]),
    }
    for row_dict in df.to_dict(orient="records")
]

with open(os.path.join(DATA_DIR, "alpaca-bitcoin-sentiment-dataset.json"), "w") as f:
    json.dump(dataset_data, f)


data = load_dataset(
    "json", data_files=os.path.join(DATA_DIR, "alpaca-bitcoin-sentiment-dataset.json")
)
print(data["train"])

BASE_MODEL = LLM_MODEL_CONFIG[CFG.LLM_MODEL]
model = LlamaForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
    offload_folder=os.path.join(DATA_DIR, "vicuna-lora"),
)

tokenizer = LlamaTokenizer.from_pretrained(BASE_MODEL)
tokenizer.pad_token_id = 0
tokenizer.padding_side = "left"


def generate_prompt(data_point):
    return f"""Blow is an instruction that describes a task, paired with an input that provide future context.
    Write a response that appropriately completes the request. #noqa:

    ### Instruct:
    {data_point["instruction"]}
    ### Input
    {data_point["input"]}
    ### Response
    {data_point["output"]}
    """


def tokenize(prompt, add_eos_token=True):
    result = tokenizer(
        prompt,
        truncation=True,
        max_length=CUTOFF_LEN,
        padding=False,
        return_tensors=None,
    )

    if (
        result["input_ids"][-1] != tokenizer.eos_token_id
        and len(result["input_ids"]) < CUTOFF_LEN
        and add_eos_token
    ):
        result["input_ids"].append(tokenizer.eos_token_id)
        result["attention_mask"].append(1)

    result["labels"] = result["input_ids"].copy()
    return result


def generate_and_tokenize_prompt(data_point):
    full_prompt = generate_prompt(data_point)
    tokenized_full_prompt = tokenize(full_prompt)
    return tokenized_full_prompt


train_val = data["train"].train_test_split(test_size=200, shuffle=True, seed=42)

train_data = train_val["train"].map(generate_and_tokenize_prompt)

val_data = train_val["test_py"].map(generate_and_tokenize_prompt)

# Training
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = [
    "q_proj",
    "v_proj",
]

BATCH_SIZE = 128
MICRO_BATCH_SIZE = 4
GRADIENT_ACCUMULATION_STEPS = BATCH_SIZE // MICRO_BATCH_SIZE
LEARNING_RATE = 3e-4
TRAIN_STEPS = 300
OUTPUT_DIR = "experiments"

# We can now prepare model for training
model = prepare_model_for_int8_training(model)
config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=LORA_TARGET_MODULES,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, config)
model.print_trainable_parameters()

training_arguments = transformers.TrainingArguments(
    per_device_train_batch_size=MICRO_BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
    warmup_steps=100,
    max_steps=TRAIN_STEPS,
    no_cuda=True,
    learning_rate=LEARNING_RATE,
    logging_steps=10,
    optim="adamw_torch",
    evaluation_strategy="steps",
    save_strategy="steps",
    eval_steps=50,
    save_steps=50,
    output_dir=OUTPUT_DIR,
    save_total_limit=3,
    load_best_model_at_end=True,
    report_to="tensorboard",
)

data_collector = transformers.DataCollatorForSeq2Seq(
    tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True
)

trainer = transformers.Trainer(
    model=model,
    train_dataset=train_data,
    eval_dataset=val_data,
    args=training_arguments,
    data_collector=data_collector,
)

model.config.use_cache = False
old_state_dict = model.state_dict
model.state_dict = (
    lambda self, *_, **__: get_peft_model_state_dict(self, old_state_dict())
).__get__(model, type(model))

trainer.train()
model.save_pretrained(OUTPUT_DIR)
