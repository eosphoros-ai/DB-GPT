import hashlib
import json
from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from .models import (
    AnswerExecuteModel,
    DataCompareResult,
    DataCompareResultEnum,
    DataCompareStrategyConfig,
)


def md5_list(values: List[str]) -> str:
    s = ",".join([v if v is not None else "" for v in values])
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def accurate_decimal(
    table: Dict[str, List[str]], scale: int = 2
) -> Dict[str, List[str]]:
    out = {}
    for k, col in table.items():
        new_col = []
        for v in col:
            if v is None:
                new_col.append("")
                continue
            vs = str(v)
            try:
                d = Decimal(vs)
                new_col.append(
                    str(d.quantize(Decimal("1." + "0" * scale), rounding=ROUND_HALF_UP))
                )
            except Exception as e:
                new_col.append(vs)
        out[k] = new_col
    return out


def sort_columns_by_key(
    table: Dict[str, List[str]], sort_key: str
) -> Dict[str, List[str]]:
    if sort_key not in table:
        raise ValueError(f"base col not exist: {sort_key}")
    base = table[sort_key]
    row_count = len(base)
    for k, col in table.items():
        if len(col) != row_count:
            raise ValueError(f"col length diff: {k}")
    indices = list(range(row_count))
    indices.sort(key=lambda i: "" if base[i] is None else str(base[i]))
    sorted_table = {}
    for k in table.keys():
        sorted_table[k] = [table[k][i] for i in indices]
    return sorted_table


class DataCompareService:
    def compare(
        self,
        standard_model: AnswerExecuteModel,
        target_result: Optional[Dict[str, List[str]]],
    ) -> DataCompareResult:
        if target_result is None:
            return DataCompareResult.failed("targetResult is null")
        cfg: DataCompareStrategyConfig = (
            standard_model.strategyConfig
            or DataCompareStrategyConfig(
                strategy="EXACT_MATCH", order_by=True, standard_result=None
            )
        )
        if not cfg.standard_result:
            return DataCompareResult.failed("leftResult is null")

        # 对每个标准答案都进行对比，只要包含了一个标准答案，即认为结果正确，否则结果错误
        for std in cfg.standard_result:
            if not isinstance(std, dict):
                continue
            std_fmt = accurate_decimal(deepcopy(std), 2)
            tgt_fmt = accurate_decimal(deepcopy(target_result), 2)
            if cfg.order_by:
                res = self._compare_ordered(std_fmt, cfg, tgt_fmt)
            else:
                res = self._compare_unordered(std_fmt, cfg, tgt_fmt)
            if res.compare_result == DataCompareResultEnum.RIGHT:
                return res
        return DataCompareResult.wrong("compareResult wrong!")

    def _compare_ordered(
        self,
        std: Dict[str, List[str]],
        cfg: DataCompareStrategyConfig,
        tgt: Dict[str, List[str]],
    ) -> DataCompareResult:
        try:
            std_md5 = set()
            for col_vals in std.values():
                lst = ["" if v is None else str(v) for v in col_vals]
                std_md5.add(md5_list(lst))

            tgt_md5 = set()
            for col_vals in tgt.values():
                lst = ["" if v is None else str(v) for v in col_vals]
                tgt_md5.add(md5_list(lst))

            tgt_size = len(tgt_md5)
            inter = tgt_md5.intersection(std_md5)

            if tgt_size == len(inter) and tgt_size == len(std_md5):
                return DataCompareResult.right("compareResult success!")

            if len(std_md5) == len(inter):
                if cfg.strategy == "EXACT_MATCH":
                    return DataCompareResult.failed("compareResult failed!")
                elif cfg.strategy == "CONTAIN_MATCH":
                    return DataCompareResult.right("compareResult success!")
            return DataCompareResult.wrong("compareResult wrong!")
        except Exception as e:
            return DataCompareResult.exception(f"compareResult Exception! {e}")

    def _compare_unordered(
        self,
        std: Dict[str, List[str]],
        cfg: DataCompareStrategyConfig,
        tgt: Dict[str, List[str]],
    ) -> DataCompareResult:
        try:
            tgt_md5 = []
            tgt_cols = []
            for k, col_vals in tgt.items():
                lst = ["" if v is None else str(v) for v in col_vals]
                lst.sort()
                tgt_md5.append(md5_list(lst))
                tgt_cols.append(k)

            for std_key, std_vals in std.items():
                std_list = ["" if v is None else str(v) for v in std_vals]
                std_list.sort()
                std_md5 = md5_list(std_list)
                if std_md5 not in tgt_md5:
                    return DataCompareResult.wrong("compareResult wrong!")

                idx = tgt_md5.index(std_md5)
                tgt_key = tgt_cols[idx]

                std_sorted = sort_columns_by_key(std, std_key)
                tgt_sorted = sort_columns_by_key(tgt, tgt_key)

                ordered_cfg = DataCompareStrategyConfig(
                    strategy=cfg.strategy,
                    order_by=True,
                    standard_result=cfg.standard_result,
                )
                res = self._compare_ordered(std_sorted, ordered_cfg, tgt_sorted)
                if res.compare_result == DataCompareResultEnum.RIGHT:
                    return res
            return DataCompareResult.wrong("compareResult wrong!")
        except Exception as e:
            return DataCompareResult.exception(f"compareResult Exception! {e}")

    def compare_json_by_config(
        self, standard_answer: str, answer: str, compare_config: Dict[str, str]
    ) -> DataCompareResult:
        try:
            if not standard_answer or not answer:
                return DataCompareResult.failed("standardAnswer or answer is null")
            ans = json.loads(answer)
            for k, strat in compare_config.items():
                if k not in ans:
                    return DataCompareResult.wrong("key missing")
                if strat in ("FULL_TEXT", "ARRAY"):
                    if str(ans[k]) != "ok":
                        return DataCompareResult.wrong("value mismatch")
                elif strat == "DAL":
                    return DataCompareResult.failed("DAL compare not supported in mock")
                else:
                    return DataCompareResult.failed(f"unknown strategy {strat}")
            return DataCompareResult.right("json compare success")
        except Exception as e:
            return DataCompareResult.exception(f"compareJsonByConfig Exception! {e}")
