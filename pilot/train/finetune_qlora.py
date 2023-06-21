import copy
import json
import os

from dataclasses import dataclass, field
from typing import Optional, Dict, Sequence
import numpy as np
from tqdm import tqdm
import logging

import bitsandbytes as bnb
import pandas as pd

import torch
import transformers
from torch.nn.utils.rnn import pad_sequence
import argparse
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    set_seed,
    Seq2SeqTrainer,
    BitsAndBytesConfig,
    LlamaTokenizer
)

from datasets import load_dataset, Dataset

from peft import (
     prepare_model_for_kbit_training,
     LoraConfig,
     get_peft_config,
     PeftModel
)

from peft.tuners.lora import LoraLayer
from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR


torch.backends.cuda.matmul.allow_tf32 = True

logger = logging.getLogger(__name__)
IGNORE_INDEX = -100
DEFAULT_PAD_TOKEN = "[PAD]"

