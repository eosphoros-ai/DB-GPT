#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import transformers
from transformers import LlamaTokenizer, LlamaForCausalLM

from typing import List
from peft import (
    LoraConfig,
    get_peft_model,
    get_peft_model_state_dict,
    prepare_model_for_int8_training,
)

import torch
from datasets import load_dataset
import pandas as pd


from pilot.configs.model_config import DATA_DIR
device = "cuda" if torch.cuda.is_available() else "cpu"
CUTOFF = 50

df = pd.read_csv(os.path.join(DATA_DIR, "BTC_Tweets_Updated.csv"))