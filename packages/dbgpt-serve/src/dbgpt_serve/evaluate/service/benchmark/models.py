# app/services/models.py
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

# 定义类型变量
InputType = TypeVar("InputType", bound="BaseInputModel")
OutputType = TypeVar("OutputType", bound="AnswerExecuteModel")


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
    cost_time: Optional[int] = None

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
            cost_time=d.get("cost_time"),
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
            cost_time=self.cost_time,
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


class FileParseTypeEnum(Enum):
    """文件解析类型枚举"""

    OSS = "OSS"
    YU_QUE = "YU_QUE"
    EXCEL = "EXCEL"


class FormatTypeEnum(Enum):
    """Output format type enumeration"""

    TEXT = "TEXT"
    JSON = "JSON"
    XML = ("xml",)
    CSV = "CSV"
    EXCEL = "EXCEL"


class ContentTypeEnum(Enum):
    """Output content type enumeration"""

    SQL = "SQL"
    JSON = "JSON"


@dataclass
class BenchmarkExecuteConfig:
    """
    Benchmark Execute Config
    """

    # base config
    file_parse_type: FileParseTypeEnum = FileParseTypeEnum.OSS
    format_type: FormatTypeEnum = FormatTypeEnum.TEXT
    content_type: ContentTypeEnum = ContentTypeEnum.SQL
    benchmark_mode_type: BenchmarkModeTypeEnum = BenchmarkModeTypeEnum.EXECUTE

    # file path config
    output_file_path: Optional[str] = None
    standard_file_path: Optional[str] = None

    # runtime execute config
    round_time: int = 1
    generate_ratio: int = 5
    execute_llm_result: bool = True
    invoke_llm: bool = True
    thread_num: Optional[int] = None

    # llm thread config
    llm_thread_map: Dict[str, int] = field(default=None)

    # compare result config
    compare_result_enable: bool = True
    compare_config: Dict[str, str] = field(default=None)

    # user config
    user_id: Optional[str] = None

    def get_llm_thread(self, llm_code: str) -> int:
        return self.llm_thread_map.get(llm_code, 1)

    def add_llm_thread_config(self, llm_code: str, thread_count: int) -> None:
        if thread_count <= 0:
            raise ValueError("thread_count must be positive")
        self.llm_thread_map[llm_code] = thread_count

    def has_valid_file_paths(self) -> bool:
        return bool(self.output_file_path) and bool(self.standard_file_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_parse_type": self.file_parse_type.value,
            "format_type": self.format_type.value,
            "content_type": self.content_type.value,
            "benchmark_mode_type": self.benchmark_mode_type.value,
            "output_file_path": self.output_file_path,
            "standard_file_path": self.standard_file_path,
            "round_time": self.round_time,
            "generate_ratio": self.generate_ratio,
            "execute_llm_result": self.execute_llm_result,
            "invoke_llm": self.invoke_llm,
            "llm_thread_map": self.llm_thread_map,
            "compare_result_enable": self.compare_result_enable,
            "compare_config": self.compare_config,
            "thread_num": self.thread_num,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BenchmarkExecuteConfig":
        """从字典创建配置实例"""
        return cls(
            file_parse_type=FileParseTypeEnum(
                config_dict.get("file_parse_type", "OSS")
            ),
            format_type=FormatTypeEnum(config_dict.get("format_type", "TEXT")),
            content_type=ContentTypeEnum(config_dict.get("content_type", "SQL")),
            benchmark_mode_type=BenchmarkModeTypeEnum(
                config_dict.get("benchmark_mode_type", "BUILD")
            ),
            output_file_path=config_dict.get("output_file_path"),
            standard_file_path=config_dict.get("standard_file_path"),
            round_time=config_dict.get("round_time", 1),
            generate_ratio=config_dict.get("generate_ratio", 5),
            execute_llm_result=config_dict.get("execute_llm_result", False),
            invoke_llm=config_dict.get("invoke_llm", True),
            llm_thread_map=config_dict.get("llm_thread_map", {}),
            compare_result_enable=config_dict.get("compare_result_enable", True),
            compare_config=config_dict.get("compare_config", {}),
            thread_num=config_dict.get("thread_num"),
            user_id=config_dict.get("user_id"),
        )


@dataclass
class BaseInputModel:
    serial_no: int = 0
    analysis_model_id: str = ""
    question: str = ""
    self_define_tags: str = ""
    knowledge: str = ""
    llm_output: str = ""
    llm_code: str = ""
    prompt: str = ""


@dataclass
class BenchmarkDataSets(Generic[InputType]):
    data_list: List[InputType] = None

    def __post_init__(self):
        if self.data_list is None:
            self.data_list = []


@dataclass
class BenchmarkTaskResult(Generic[OutputType]):
    trace_id: str = ""
    task_id: str = ""
    start_time: Optional[datetime.datetime] = None
    benchmark_data_sets: BenchmarkDataSets[InputType] = None

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.datetime.now()
        if self.benchmark_data_sets is None:
            self.benchmark_data_sets = BenchmarkDataSets()


@dataclass
class BenchmarkPromptModel:
    prompt: Optional[str] = None
    ext_info: Optional[Dict[str, str]] = field(default_factory=dict)

    @staticmethod
    def of_prompt(prompt: str) -> "BenchmarkPromptModel":
        return BenchmarkPromptModel(prompt=prompt, ext_info={})


@dataclass
class ReasoningResponse:
    cot_tokens: int = 0
    think: Optional[str] = None
    content: Optional[str] = None
    model: Optional[str] = None
    duration: float = 0.0

    def __init__(
        self,
        cot_tokens: int = 0,
        think: Optional[str] = None,
        content: Optional[str] = None,
    ):
        self.cot_tokens = cot_tokens
        self.think = think
        self.content = content
