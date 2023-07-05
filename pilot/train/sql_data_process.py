import os
import sys
import json
import re
import random
import sqlite3
import datasets
import traceback
import difflib
import functools
import re
import random
import numpy as np
from tqdm import tqdm
from copy import deepcopy
from rapidfuzz import fuzz
from os.path import isfile, isdir, join, split, exists, splitext
from typing import List, Optional, Tuple, Dict
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, field
from datasets.dataset_dict import DatasetDict
from datasets.arrow_dataset import Dataset
from transformers.training_args import TrainingArguments
from datasets.arrow_dataset import Dataset
from transformers.tokenization_utils_base import PreTrainedTokenizerBase


def convert_fk_index(data):
    fk_holder = []
    for fk in data["foreign_keys"]:
        tn, col, ref_tn, ref_col = fk[0][0], fk[0][1], fk[1][0], fk[1][1]
        ref_cid, cid = None, None
        try:
            tid = data["table_names_original"].index(tn)
            ref_tid = data["table_names_original"].index(ref_tn)

            for i, (tab_id, col_org) in enumerate(data["column_names_original"]):
                if tab_id == ref_tid and ref_col == col_org:
                    ref_cid = i
                elif tid == tab_id and col == col_org:
                    cid = i
            if ref_cid and cid:
                fk_holder.append([cid, ref_cid])
        except:
            traceback.print_exc()
            print("table_names_original: ", data["table_names_original"])
            print("finding tab name: ", tn, ref_tn)
            sys.exit()
    return fk_holder


def dump_db_json_schema(db, f):
    """read table and column info"""

    conn = sqlite3.connect(db)
    conn.execute("pragma foreign_keys=ON")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")

    data = {
        "db_id": f,
        "table_names_original": [],
        "table_names": [],
        "column_names_original": [(-1, "*")],
        "column_names": [(-1, "*")],
        "column_types": ["text"],
        "primary_keys": [],
        "foreign_keys": [],
    }

    fk_holder = []
    for i, item in enumerate(cursor.fetchall()):
        table_name = item[0]
        data["table_names_original"].append(table_name)
        data["table_names"].append(table_name.lower().replace("_", " "))
        fks = conn.execute(
            "PRAGMA foreign_key_list('{}') ".format(table_name)
        ).fetchall()
        # print("db:{} table:{} fks:{}".format(f,table_name,fks))
        fk_holder.extend([[(table_name, fk[3]), (fk[2], fk[4])] for fk in fks])
        cur = conn.execute("PRAGMA table_info('{}') ".format(table_name))
        for j, col in enumerate(cur.fetchall()):
            data["column_names_original"].append((i, col[1]))
            data["column_names"].append((i, col[1].lower().replace("_", " ")))
            # varchar, '' -> text, int, numeric -> integer,
            col_type = col[2].lower()
            if (
                "char" in col_type
                or col_type == ""
                or "text" in col_type
                or "var" in col_type
            ):
                data["column_types"].append("text")
            elif (
                "int" in col_type
                or "numeric" in col_type
                or "decimal" in col_type
                or "number" in col_type
                or "id" in col_type
                or "real" in col_type
                or "double" in col_type
                or "float" in col_type
            ):
                data["column_types"].append("number")
            elif "date" in col_type or "time" in col_type or "year" in col_type:
                data["column_types"].append("time")
            elif "boolean" in col_type:
                data["column_types"].append("boolean")
            else:
                data["column_types"].append("others")

            if col[5] == 1:
                data["primary_keys"].append(len(data["column_names"]) - 1)

    data["foreign_keys"] = fk_holder
    data["foreign_keys"] = convert_fk_index(data)

    return data

logger = datasets.logging.get_logger(__name__)

_CITATION = """\
@article{yu2018spider,
  title={Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-sql task},
  author={Yu, Tao and Zhang, Rui and Yang, Kai and Yasunaga, Michihiro and Wang, Dongxu and Li, Zifan and Ma, James and Li, Irene and Yao, Qingning and Roman, Shanelle and others},
  journal={arXiv preprint arXiv:1809.08887},
  year={2018}
}
"""


def generate_data(data_filepaths, db_path):
  raw_data = []
  schema_cache = dict()
  for data_filepath in data_filepaths:
    with open(data_filepath, encoding="utf-8") as f:
      spider = json.load(f)
      for  sample in spider:
          db_id = sample["db_id"]
          if db_id not in schema_cache:
            schema_cache[db_id] = dump_db_json_schema(db=os.path.join(db_path, db_id, f"{db_id}.sqlite"), f=db_id)
          schema = schema_cache[db_id]
          raw_data.append({
              "query": sample["query"],
              "question": sample["question"],
              "db_id": db_id,
              "db_path": db_path,
              "db_table_names": schema["table_names_original"],
              "db_column_names": [
                  {"table_id": table_id, "column_name": column_name}
                  for table_id, column_name in schema["column_names_original"]
              ],
              "db_column_types": schema["column_types"],
              "db_primary_keys": [{"column_id": column_id} for column_id in schema["primary_keys"]],
              "db_foreign_keys": [
                  {"column_id": column_id, "other_column_id": other_column_id}
                  for column_id, other_column_id in schema["foreign_keys"]
              ],
          })
  return raw_data



"""
    Wrap the raw dataset into the seq2seq one.
    And the raw dataset item is formatted as
    {
        "query": sample["query"],
        "question": sample["question"],
        "db_id": db_id,
        "db_path": db_path,
        "db_table_names": schema["table_names_original"],
        "db_column_names": [
            {"table_id": table_id, "column_name": column_name}
            for table_id, column_name in schema["column_names_original"]
        ],
        "db_column_types": schema["column_types"],
        "db_primary_keys": [{"column_id": column_id} for column_id in schema["primary_keys"]],
        "db_foreign_keys": [
            {"column_id": column_id, "other_column_id": other_column_id}
            for column_id, other_column_id in schema["foreign_keys"]
        ],
    }
    """


# fmt: off
_stopwords = {'who', 'ourselves', 'down', 'only', 'were', 'him', 'at', "weren't", 'has', 'few', "it's", 'm', 'again',
              'd', 'haven', 'been', 'other', 'we', 'an', 'own', 'doing', 'ma', 'hers', 'all', "haven't", 'in', 'but',
              "shouldn't", 'does', 'out', 'aren', 'you', "you'd", 'himself', "isn't", 'most', 'y', 'below', 'is',
              "wasn't", 'hasn', 'them', 'wouldn', 'against', 'this', 'about', 'there', 'don', "that'll", 'a', 'being',
              'with', 'your', 'theirs', 'its', 'any', 'why', 'now', 'during', 'weren', 'if', 'should', 'those', 'be',
              'they', 'o', 't', 'of', 'or', 'me', 'i', 'some', 'her', 'do', 'will', 'yours', 'for', 'mightn', 'nor',
              'needn', 'the', 'until', "couldn't", 'he', 'which', 'yourself', 'to', "needn't", "you're", 'because',
              'their', 'where', 'it', "didn't", 've', 'whom', "should've", 'can', "shan't", 'on', 'had', 'have',
              'myself', 'am', "don't", 'under', 'was', "won't", 'these', 'so', 'as', 'after', 'above', 'each', 'ours',
              'hadn', 'having', 'wasn', 's', 'doesn', "hadn't", 'than', 'by', 'that', 'both', 'herself', 'his',
              "wouldn't", 'into', "doesn't", 'before', 'my', 'won', 'more', 'are', 'through', 'same', 'how', 'what',
              'over', 'll', 'yourselves', 'up', 'mustn', "mustn't", "she's", 're', 'such', 'didn', "you'll", 'shan',
              'when', "you've", 'themselves', "mightn't", 'she', 'from', 'isn', 'ain', 'between', 'once', 'here',
              'shouldn', 'our', 'and', 'not', 'too', 'very', 'further', 'while', 'off', 'couldn', "hasn't", 'itself',
              'then', 'did', 'just', "aren't"}
# fmt: on

_commonwords = {"no", "yes", "many"}


def is_number(s: str) -> bool:
    try:
        float(s.replace(",", ""))
        return True
    except:
        return False


def is_stopword(s: str) -> bool:
    return s.strip() in _stopwords


def is_commonword(s: str) -> bool:
    return s.strip() in _commonwords


def is_common_db_term(s: str) -> bool:
    return s.strip() in ["id"]


class Match(object):
    def __init__(self, start: int, size: int) -> None:
        self.start = start
        self.size = size


def is_span_separator(c: str) -> bool:
    return c in "'\"()`,.?! "


def split(s: str) -> List[str]:
    return [c.lower() for c in s.strip()]


def prefix_match(s1: str, s2: str) -> bool:
    i, j = 0, 0
    for i in range(len(s1)):
        if not is_span_separator(s1[i]):
            break
    for j in range(len(s2)):
        if not is_span_separator(s2[j]):
            break
    if i < len(s1) and j < len(s2):
        return s1[i] == s2[j]
    elif i >= len(s1) and j >= len(s2):
        return True
    else:
        return False


def get_effective_match_source(s: str, start: int, end: int) -> Match:
    _start = -1

    for i in range(start, start - 2, -1):
        if i < 0:
            _start = i + 1
            break
        if is_span_separator(s[i]):
            _start = i
            break

    if _start < 0:
        return None

    _end = -1
    for i in range(end - 1, end + 3):
        if i >= len(s):
            _end = i - 1
            break
        if is_span_separator(s[i]):
            _end = i
            break

    if _end < 0:
        return None

    while _start < len(s) and is_span_separator(s[_start]):
        _start += 1
    while _end >= 0 and is_span_separator(s[_end]):
        _end -= 1

    return Match(_start, _end - _start + 1)


def get_matched_entries(
    s: str, field_values: List[str], m_theta: float = 0.85, s_theta: float = 0.85
) -> Optional[List[Tuple[str, Tuple[str, str, float, float, int]]]]:
    if not field_values:
        return None

    if isinstance(s, str):
        n_grams = split(s)
    else:
        n_grams = s

    matched = dict()
    for field_value in field_values:
        if not isinstance(field_value, str):
            continue
        fv_tokens = split(field_value)
        sm = difflib.SequenceMatcher(None, n_grams, fv_tokens)
        match = sm.find_longest_match(0, len(n_grams), 0, len(fv_tokens))
        if match.size > 0:
            source_match = get_effective_match_source(
                n_grams, match.a, match.a + match.size
            )
            if source_match and source_match.size > 1:
                match_str = field_value[match.b : match.b + match.size]
                source_match_str = s[
                    source_match.start : source_match.start + source_match.size
                ]
                c_match_str = match_str.lower().strip()
                c_source_match_str = source_match_str.lower().strip()
                c_field_value = field_value.lower().strip()
                if (
                    c_match_str
                    and not is_number(c_match_str)
                    and not is_common_db_term(c_match_str)
                ):
                    if (
                        is_stopword(c_match_str)
                        or is_stopword(c_source_match_str)
                        or is_stopword(c_field_value)
                    ):
                        continue
                    if c_source_match_str.endswith(c_match_str + "'s"):
                        match_score = 1.0
                    else:
                        if prefix_match(c_field_value, c_source_match_str):
                            match_score = (
                                fuzz.ratio(c_field_value, c_source_match_str) / 100
                            )
                        else:
                            match_score = 0
                    if (
                        is_commonword(c_match_str)
                        or is_commonword(c_source_match_str)
                        or is_commonword(c_field_value)
                    ) and match_score < 1:
                        continue
                    s_match_score = match_score
                    if match_score >= m_theta and s_match_score >= s_theta:
                        if field_value.isupper() and match_score * s_match_score < 1:
                            continue
                        matched[match_str] = (
                            field_value,
                            source_match_str,
                            match_score,
                            s_match_score,
                            match.size,
                        )

    if not matched:
        return None
    else:
        return sorted(
            matched.items(),
            key=lambda x: (1e16 * x[1][2] + 1e8 * x[1][3] + x[1][4]),
            reverse=True,
        )


@functools.lru_cache(maxsize=1000, typed=False)
def get_column_picklist(table_name: str, column_name: str, db_path: str) -> list:
    fetch_sql = "SELECT DISTINCT `{}` FROM `{}`".format(column_name, table_name)
    try:
        conn = sqlite3.connect(db_path)
        conn.text_factory = bytes
        c = conn.cursor()
        c.execute(fetch_sql)
        picklist = set()
        for x in c.fetchall():
            if isinstance(x[0], str):
                picklist.add(x[0].encode("utf-8"))
            elif isinstance(x[0], bytes):
                try:
                    picklist.add(x[0].decode("utf-8"))
                except UnicodeDecodeError:
                    picklist.add(x[0].decode("latin-1"))
            else:
                picklist.add(x[0])
        picklist = list(picklist)
    finally:
        conn.close()
    return picklist


def get_database_matches(
    question: str,
    table_name: str,
    column_name: str,
    db_path: str,
    top_k_matches: int = 2,
    match_threshold: float = 0.85,
) -> List[str]:
    picklist = get_column_picklist(
        table_name=table_name, column_name=column_name, db_path=db_path
    )
    matches = []
    if picklist and isinstance(picklist[0], str):
        matched_entries = get_matched_entries(
            s=question,
            field_values=picklist,
            m_theta=match_threshold,
            s_theta=match_threshold,
        )
        if matched_entries:
            num_values_inserted = 0
            for _match_str, (
                field_value,
                _s_match_str,
                match_score,
                s_match_score,
                _match_size,
            ) in matched_entries:
                if "name" in column_name and match_score * s_match_score < 1:
                    continue
                if table_name != "sqlite_sequence":  # Spider database artifact
                    matches.append(field_value)
                    num_values_inserted += 1
                    if num_values_inserted >= top_k_matches:
                        break
    return matches

@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """

    overwrite_cache: bool = field(
        default=False,
        metadata={"help": "Overwrite the cached training and evaluation sets"},
    )
    preprocessing_num_workers: Optional[int] = field(
        default=None,
        metadata={"help": "The number of processes to use for the preprocessing."},
    )
    max_source_length: Optional[int] = field(
        default=512,
        metadata={
            "help": "The maximum total input sequence length after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded."
        },
    )
    max_target_length: Optional[int] = field(
        default=512,
        metadata={
            "help": "The maximum total sequence length for target text after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded."
        },
    )
    val_max_target_length: Optional[int] = field(
        default=None,
        metadata={
            "help": "The maximum total sequence length for validation target text after tokenization. Sequences longer "
            "than this will be truncated, sequences shorter will be padded. Will default to `max_target_length`."
            "This argument is also used to override the ``max_length`` param of ``model.generate``, which is used "
            "during ``evaluate`` and ``predict``."
        },
    )
    val_max_time: Optional[int] = field(
        default=None,
        metadata={
            "help": "The maximum allowed time in seconds for generation of one example. This setting can be used to stop "
            "generation whenever the full generation exceeds the specified amount of time."
        },
    )
    max_train_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of training examples to this "
            "value if set."
        },
    )
    max_val_samples: Optional[int] = field(
        default=None,
        metadata={
            "help": "For debugging purposes or quicker training, truncate the number of validation or test examples to this "
            "value if set."
        },
    )
    num_beams: int = field(
        default=1,
        metadata={
            "help": "Number of beams to use for evaluation. This argument will be passed to ``model.generate``, "
            "which is used during ``evaluate`` and ``predict``."
        },
    )
    num_beam_groups: int = field(
        default=1,
        metadata={
            "help": "Number of beam groups to use for evaluation. This argument will be passed to ``model.generate``, "
            "which is used during ``evaluate`` and ``predict``."
        },
    )
    diversity_penalty: Optional[float] = field(
        default=None,
        metadata={
            "help": "Diversity penalty to use for evaluation. This argument will be passed to ``model.generate``, "
            "which is used during ``evaluate`` and ``predict``."
        },
    )
    num_return_sequences: Optional[int] = field(
        default=None,
        metadata={
            "help": "The number of sequences to generate during evaluation. This argument will be passed to "
            "``model.generate``, which is used during ``evaluate`` and ``predict``."
        },
    )
    ignore_pad_token_for_loss: bool = field(
        default=True,
        metadata={
            "help": "Whether or not to ignore the tokens corresponding to padded labels in the loss computation or not."
        },
    )
    source_prefix: Optional[str] = field(
        default=None,
        metadata={"help": "A prefix to add before every source text (useful for T5 models)."},
    )
    schema_serialization_type: str = field(
        default="peteshaw",
        metadata={"help": "Choose between ``verbose`` and ``peteshaw`` schema serialization."},
    )
    schema_serialization_randomized: bool = field(
        default=False,
        metadata={"help": "Whether or not to randomize the order of tables."},
    )
    schema_serialization_with_db_id: bool = field(
        default=True,
        metadata={"help": "Whether or not to add the database id to the context. Needed for Picard."},
    )
    schema_serialization_with_db_content: bool = field(
        default=True,
        metadata={"help": "Whether or not to use the database content to resolve field matches."},
    )
    normalize_query: bool = field(default=True, metadata={"help": "Whether to normalize the SQL queries."})
    target_with_db_id: bool = field(
        default=True,
        metadata={"help": "Whether or not to add the database id to the target. Needed for Picard."},
    )

    def __post_init__(self):
        if self.val_max_target_length is None:
            self.val_max_target_length = self.max_target_length


@dataclass
class DataArguments:
    dataset: str = field(
        metadata={"help": "The dataset to be used. Choose between ``spider``, ``cosql``, or ``cosql+spider``, or ``spider_realistic``, or ``spider_syn``, or ``spider_dk``."},
    )
    dataset_paths: Dict[str, str] = field(
        default_factory=lambda: {
            "spider": "./seq2seq/datasets/spider",
            "cosql": "./seq2seq/datasets/cosql",
            "spider_realistic": "./seq2seq/datasets/spider_realistic",
            "spider_syn": "./seq2seq/datasets/spider_syn",
            "spider_dk": "./seq2seq/datasets/spider_dk"

        },
        metadata={"help": "Paths of the dataset modules."},
    )
    metric_config: str = field(
        default="both",
        metadata={"help": "Choose between ``exact_match``, ``test_suite``, or ``both``."},
    )
    #we are referencing spider_realistic to spider metrics only as both use the main spider dataset as base.
    metric_paths: Dict[str, str] = field(
        default_factory=lambda: {
            "spider": "./seq2seq/metrics/spider",
            "spider_realistic" : "./seq2seq/metrics/spider",
            "cosql": "./seq2seq/metrics/cosql",
            "spider_syn":"./seq2seq/metrics/spider",
            "spider_dk":"./seq2seq/metrics/spider"
        },
        metadata={"help": "Paths of the metric modules."},
    )
    test_suite_db_dir: Optional[str] = field(
        default=None,
        metadata={"help": "Path to the test-suite databases."})
    data_config_file : Optional[str] = field(
        default=None,
        metadata={"help": "Path to data configuration file (specifying the database splits)"}
    )
    test_sections : Optional[List[str]] = field(
        default=None,
        metadata={"help": "Sections from the data config to use for testing"}
    )


@dataclass
class TrainSplit(object):
    dataset: Dataset
    schemas: Dict[str, dict]


@dataclass
class EvalSplit(object):
    dataset: Dataset
    examples: Dataset
    schemas: Dict[str, dict]


@dataclass
class DatasetSplits(object):
    train_split: Optional[TrainSplit]
    eval_split: Optional[EvalSplit]
    test_splits: Optional[Dict[str, EvalSplit]]
    schemas: Dict[str, dict]


def _get_schemas(examples: Dataset) -> Dict[str, dict]:
    schemas: Dict[str, dict] = dict()
    for ex in examples:
        if ex["db_id"] not in schemas:
            schemas[ex["db_id"]] = {
                "db_table_names": ex["db_table_names"],
                "db_column_names": ex["db_column_names"],
                "db_column_types": ex["db_column_types"],
                "db_primary_keys": ex["db_primary_keys"],
                "db_foreign_keys": ex["db_foreign_keys"],
            }
    return schemas


def _prepare_train_split(
    dataset: Dataset,
    data_training_args: DataTrainingArguments,
    add_serialized_schema: Callable[[dict], dict],
    pre_process_function: Callable[[dict, Optional[int], Optional[int]], dict],
) -> TrainSplit:
    schemas = _get_schemas(examples=dataset)
    dataset = dataset.map(
        add_serialized_schema,
        batched=False,
        num_proc=data_training_args.preprocessing_num_workers,
        load_from_cache_file=not data_training_args.overwrite_cache,
    )
    if data_training_args.max_train_samples is not None:
        dataset = dataset.select(range(data_training_args.max_train_samples))
    column_names = dataset.column_names
    dataset = dataset.map(
        lambda batch: pre_process_function(
            batch=batch,
            max_source_length=data_training_args.max_source_length,
            max_target_length=data_training_args.max_target_length,
        ),
        batched=True,
        num_proc=data_training_args.preprocessing_num_workers,
        remove_columns=column_names,
        load_from_cache_file=not data_training_args.overwrite_cache,
    )
    return TrainSplit(dataset=dataset, schemas=schemas)


def _prepare_eval_split(
    dataset: Dataset,
    data_training_args: DataTrainingArguments,
    add_serialized_schema: Callable[[dict], dict],
    pre_process_function: Callable[[dict, Optional[int], Optional[int]], dict],
) -> EvalSplit:
    if (data_training_args.max_val_samples is not None
            and data_training_args.max_val_samples < len(dataset)):
        eval_examples = dataset.select(range(data_training_args.max_val_samples))
    else:
        eval_examples = dataset
    schemas = _get_schemas(examples=eval_examples)
    eval_dataset = eval_examples.map(
        add_serialized_schema,
        batched=False,
        num_proc=data_training_args.preprocessing_num_workers,
        load_from_cache_file=not data_training_args.overwrite_cache,
    )
    column_names = eval_dataset.column_names
    eval_dataset = eval_dataset.map(
        lambda batch: pre_process_function(
            batch=batch,
            max_source_length=data_training_args.max_source_length,
            max_target_length=data_training_args.val_max_target_length,
        ),
        batched=True,
        num_proc=data_training_args.preprocessing_num_workers,
        remove_columns=column_names,
        load_from_cache_file=not data_training_args.overwrite_cache,
    )
    return EvalSplit(dataset=eval_dataset, examples=eval_examples, schemas=schemas)


def prepare_splits(
    dataset_dict: DatasetDict,
    data_args: DataArguments,
    training_args: TrainingArguments,
    data_training_args: DataTrainingArguments,
    add_serialized_schema: Callable[[dict], dict],
    pre_process_function: Callable[[dict, Optional[int], Optional[int]], dict],
) -> DatasetSplits:
    train_split, eval_split, test_splits = None, None, None

    if training_args.do_train:
        train_split = _prepare_train_split(
            dataset_dict["train"],
            data_training_args=data_training_args,
            add_serialized_schema=add_serialized_schema,
            pre_process_function=pre_process_function,
        )

    if training_args.do_eval:
        eval_split = _prepare_eval_split(
            dataset_dict["validation"],
            data_training_args=data_training_args,
            add_serialized_schema=add_serialized_schema,
            pre_process_function=pre_process_function,
        )

    if training_args.do_predict:
        test_splits = {
            section: _prepare_eval_split(
                dataset_dict[section],
                data_training_args=data_training_args,
                add_serialized_schema=add_serialized_schema,
                pre_process_function=pre_process_function,
            )
            for section in data_args.test_sections
        }
        test_split_schemas = {}
        for split in test_splits.values():
            test_split_schemas.update(split.schemas)

    schemas = {
        **(train_split.schemas if train_split is not None else {}),
        **(eval_split.schemas if eval_split is not None else {}),
        **(test_split_schemas if test_splits is not None else {}),
    }

    return DatasetSplits(
        train_split=train_split,
        eval_split=eval_split,
        test_splits=test_splits,
        schemas=schemas
    )


def normalize(query: str) -> str:
    def comma_fix(s):
        # Remove spaces in front of commas
        return s.replace(" , ", ", ")

    def white_space_fix(s):
        # Remove double and triple spaces
        return " ".join(s.split())

    def lower(s):
        # Convert everything except text between (single or double) quotation marks to lower case
        return re.sub(r"\b(?<!['\"])(\w+)(?!['\"])\b", lambda match: match.group(1).lower(), s)

    return comma_fix(white_space_fix(lower(query)))


def serialize_schema(
    question: str,
    db_path: str,
    db_id: str,
    db_column_names: Dict[str, str],
    db_table_names: List[str],
    schema_serialization_type: str = "peteshaw",
    schema_serialization_randomized: bool = False,
    schema_serialization_with_db_id: bool = True,
    schema_serialization_with_db_content: bool = False,
    normalize_query: bool = True,
) -> str:
    if schema_serialization_type == "verbose":
        db_id_str = "Database: {db_id}. "
        table_sep = ". "
        table_str = "Table: {table}. Columns: {columns}"
        column_sep = ", "
        column_str_with_values = "{column} ({values})"
        column_str_without_values = "{column}"
        value_sep = ", "
    elif schema_serialization_type == "peteshaw":
        # see https://github.com/google-research/language/blob/master/language/nqg/tasks/spider/append_schema.py#L42
        db_id_str = " | {db_id}"
        table_sep = ""
        table_str = " | {table} : {columns}"
        column_sep = " , "
        column_str_with_values = "{column} ( {values} )"
        column_str_without_values = "{column}"
        value_sep = " , "
    else:
        raise NotImplementedError

    def get_column_str(table_name: str, column_name: str) -> str:
        column_name_str = column_name.lower() if normalize_query else column_name
        if schema_serialization_with_db_content:
            matches = get_database_matches(
                question=question,
                table_name=table_name,
                column_name=column_name,
                db_path=(db_path + "/" + db_id + "/" + db_id + ".sqlite"),
            )
            if matches:
                return column_str_with_values.format(column=column_name_str, values=value_sep.join(matches))
            else:
                return column_str_without_values.format(column=column_name_str)
        else:
            return column_str_without_values.format(column=column_name_str)

    tables = [
        table_str.format(
            table=table_name.lower() if normalize_query else table_name,
            columns=column_sep.join(
                map(
                    lambda y: get_column_str(table_name=table_name, column_name=y[1]),
                    filter(
                        lambda y: y[0] == table_id,
                        zip(
                            db_column_names["table_id"],
                            db_column_names["column_name"],
                        ),
                    ),
                )
            ),
        )
        for table_id, table_name in enumerate(db_table_names)
    ]
    if schema_serialization_randomized:
        random.shuffle(tables)
    if schema_serialization_with_db_id:
        serialized_schema = db_id_str.format(db_id=db_id) + table_sep.join(tables)
    else:
        serialized_schema = table_sep.join(tables)
    return serialized_schema

def serialize_schema_natural_language(
        question: str,
        db_path: str,
        db_id: str,
        db_column_names: Dict[str, str],
        db_table_names: List[str],
        db_primary_keys,
        db_foreign_keys,
        schema_serialization_with_db_content: bool = False,
        normalize_query: bool = True,
) -> str:
    overall_description = f'{db_id} contains tables such as ' \
                          f'{", ".join([table_name.lower() if normalize_query else table_name for table_name in db_table_names])}.'
    table_description_primary_key_template = lambda table_name, primary_key: \
        f'{primary_key} is the primary key.'
    table_description = lambda table_name, column_names: \
        f'Table {table_name} has columns such as {", ".join(column_names)}.'
    value_description = lambda column_value_pairs: \
        f'{"".join(["The {} contains values such as {}.".format(column, value) for column, value in column_value_pairs])}'
    foreign_key_description = lambda table_1, column_1, table_2, column_2: \
        f'The {column_1} of {table_1} is the foreign key of {column_2} of {table_2}.'

    db_primary_keys = [x["column_id"] for x in db_primary_keys]
    db_foreign_keys = list(zip([x["column_id"] for x in db_foreign_keys], [x["other_column_id"] for x in db_foreign_keys]))


    descriptions = [overall_description]
    db_table_name_strs = []
    db_column_name_strs = []
    value_sep = ", "
    for table_id, table_name in enumerate(db_table_names):
        table_name_str = table_name.lower() if normalize_query else table_name
        db_table_name_strs.append(table_name_str)
        columns = []
        column_value_pairs = []
        primary_keys = []
        for column_id, (x, y) in enumerate(zip([x["table_id"] for x in db_column_names], [x["column_name"] for x in db_column_names])):
            if column_id == 0:
                continue
            column_str = y.lower() if normalize_query else y
            db_column_name_strs.append(column_str)
            if x == table_id:
                columns.append(column_str)
                if column_id in db_primary_keys:
                    primary_keys.append(column_str)
                if schema_serialization_with_db_content:
                    matches = get_database_matches(
                        question=question,
                        table_name=table_name,
                        column_name=y,
                        db_path=(db_path + "/" + db_id + "/" + db_id + ".sqlite"),
                    )
                    if matches:
                        column_value_pairs.append((column_str, value_sep.join(matches)))

        table_description_columns_str = table_description(table_name_str, columns)
        descriptions.append(table_description_columns_str)
        table_description_primary_key_str = table_description_primary_key_template(table_name_str, ", ".join(primary_keys))
        descriptions.append(table_description_primary_key_str)
        if len(column_value_pairs) > 0:
            value_description_str = value_description(column_value_pairs)
            descriptions.append(value_description_str)


    for x, y in db_foreign_keys:
        # get the table and column of x
        db_column_names_table_id =[x["table_id"] for x in db_column_names]
        x_table_name = db_table_name_strs[db_column_names_table_id[x]]
        x_column_name = db_column_name_strs[x]
        # get the table and column of y
        y_table_name = db_table_name_strs[db_column_names_table_id[y]]
        y_column_name = db_column_name_strs[y]
        foreign_key_description_str = foreign_key_description(x_table_name, x_column_name, y_table_name, y_column_name)
        descriptions.append(foreign_key_description_str)
    return " ".join(descriptions)

def spider_get_input(
    question: str,
    serialized_schema: str,
    prefix: str,
) -> str:
    return prefix + question.strip() + " " + serialized_schema.strip()


def spider_get_target(
    query: str,
    db_id: str,
    normalize_query: bool,
    target_with_db_id: bool,
) -> str:
    _normalize = normalize if normalize_query else (lambda x: x)
    return f"{db_id} | {_normalize(query)}" if target_with_db_id else _normalize(query)

def spider_add_serialized_schema(ex: dict) -> dict:

    serialized_schema = serialize_schema_natural_language(
            question=ex["question"],
            db_path=ex["db_path"],
            db_id=ex["db_id"],
            db_column_names=ex["db_column_names"],
            db_table_names=ex["db_table_names"],
            db_primary_keys=ex["db_primary_keys"],
            db_foreign_keys=ex["db_foreign_keys"],
            schema_serialization_with_db_content=True,
            normalize_query=True,
        )

    return {"serialized_schema": serialized_schema}

def spider_pre_process_one_function(item: dict):
    prefix = ""

    seq_out = spider_get_target(
        query=item["query"],
        db_id=item["db_id"],
        normalize_query=True,
        target_with_db_id=True,
    )

    return prefix + item["question"].strip(), seq_out


if __name__ == "__main__" :

    data_filepaths = ["data/spider/train_spider.json","data/spider/train_others.json"]
    raw_datasets  = generate_data(data_filepaths,"data/spider/database")
    sql_fintune_data = []
    fields = ["instruction","input","response"]
    for raw_data in tqdm(raw_datasets):
        extend_data = deepcopy(raw_data)
        extend_data.update(spider_add_serialized_schema(extend_data))
        question, seq_out = spider_pre_process_one_function(extend_data)
        extend_data.update({"instruction": extend_data["serialized_schema"].strip(),
                "input": question,
                "output": seq_out})
        extended_data = {}
        extended_data.update({key: value for key, value in extend_data.items() if key in fields})
        sql_fintune_data.append(extended_data)
        sql_fintune_data
    with open('sql_fintune_data.json', 'w') as f:
      json.dump(sql_fintune_data, f)
    print("The raw datasets has been generated")