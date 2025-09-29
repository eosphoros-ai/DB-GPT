from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class BenchmarkModeTypeEnum(str, Enum):
    BUILD = "BUILD"
    EXECUTE = "EXECUTE"


@dataclass
class DataCompareStrategyConfig:
    strategy: str  # "EXACT_MATCH" | "CONTAIN_MATCH"
    order_by: bool = True
    standard_result: Optional[List[Dict[str, List[str]]]] = None  # 改为 list[dict]


class DataCompareResultEnum(str, Enum):
    RIGHT = "RIGHT"
    WRONG = "WRONG"
    FAILED = "FAILED"
    EXCEPTION = "EXCEPTION"


@dataclass
class DataCompareResult:
    compare_result: DataCompareResultEnum
    msg: str = ""

    @staticmethod
    def right(msg=""):
        return DataCompareResult(DataCompareResultEnum.RIGHT, msg)

    @staticmethod
    def wrong(msg=""):
        return DataCompareResult(DataCompareResultEnum.WRONG, msg)

    @staticmethod
    def failed(msg=""):
        return DataCompareResult(DataCompareResultEnum.FAILED, msg)

    @staticmethod
    def exception(msg=""):
        return DataCompareResult(DataCompareResultEnum.EXCEPTION, msg)


@dataclass
class BaseInputModel:
    serialNo: int
    analysisModelId: str
    question: str
    selfDefineTags: Optional[str] = None
    prompt: Optional[str] = None
    knowledge: Optional[str] = None


@dataclass
class AnswerExecuteModel:
    serialNo: int
    analysisModelId: str
    question: str
    llmOutput: Optional[str]
    executeResult: Optional[Dict[str, List[str]]]
    errorMsg: Optional[str] = None
    strategyConfig: Optional[DataCompareStrategyConfig] = None
    cotTokens: Optional[Any] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AnswerExecuteModel":
        cfg = d.get("strategyConfig")
        strategy_config = None
        if cfg:
            std_list = cfg.get("standard_result")
            strategy_config = DataCompareStrategyConfig(
                strategy=cfg.get("strategy"),
                order_by=cfg.get("order_by", True),
                standard_result=std_list if isinstance(std_list, list) else None,
            )
        return AnswerExecuteModel(
            serialNo=d["serialNo"],
            analysisModelId=d["analysisModelId"],
            question=d["question"],
            llmOutput=d.get("llmOutput"),
            executeResult=d.get("executeResult"),
            errorMsg=d.get("errorMsg"),
            strategyConfig=strategy_config,
            cotTokens=d.get("cotTokens"),
        )

    def to_dict(self) -> Dict[str, Any]:
        cfg = None
        if self.strategyConfig:
            cfg = dict(
                strategy=self.strategyConfig.strategy,
                order_by=self.strategyConfig.order_by,
                standard_result=self.strategyConfig.standard_result,
            )
        return dict(
            serialNo=self.serialNo,
            analysisModelId=self.analysisModelId,
            question=self.question,
            llmOutput=self.llmOutput,
            executeResult=self.executeResult,
            errorMsg=self.errorMsg,
            strategyConfig=cfg,
            cotTokens=self.cotTokens,
        )


@dataclass
class RoundAnswerConfirmModel:
    serialNo: int
    analysisModelId: str
    question: str
    selfDefineTags: Optional[str]
    prompt: Optional[str]
    standardAnswerSql: Optional[str] = None
    strategyConfig: Optional[DataCompareStrategyConfig] = None
    llmOutput: Optional[str] = None
    executeResult: Optional[Dict[str, List[str]]] = None
    errorMsg: Optional[str] = None
    compareResult: Optional[DataCompareResultEnum] = None


@dataclass
class BenchmarkExecuteConfig:
    benchmarkModeType: BenchmarkModeTypeEnum
    compareResultEnable: bool
    standardFilePath: Optional[str] = None
    compareConfig: Optional[Dict[str, str]] = None
