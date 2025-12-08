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
    """
    Standard answer, each dict in the list represents a reference answer
    containing multiple columns of data. If any reference answer is matched,
    the result is considered correct
    """
    standard_result: Optional[List[Dict[str, List[str]]]] = None


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
    llm_code: Optional[str] = None
    knowledge: Optional[str] = None
    prompt: Optional[str] = None

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
            llm_code=d.get("llm_code"),
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
            llm_code=self.llm_code,
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
    llmCode: Optional[str] = None


class FileParseTypeEnum(Enum):
    """文件解析类型枚举"""

    OSS = "OSS"
    YU_QUE = "YU_QUE"
    EXCEL = "EXCEL"
    GITHUB = "GITHUB"


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


class BenchmarkInvokeType(str, Enum):
    LLM = "LLM"
    AGENT = "AGENT"


class HttpMethod(str, Enum):
    """HTTP method enumeration."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ResponseParseStrategy(str, Enum):
    """Response parsing strategy enumeration."""

    JSON_PATH = "JSON_PATH"  # Use JSON path to extract content
    DIRECT = "DIRECT"  # Directly use response as content


@dataclass
class AgentApiConfig:
    """Agent API configuration.

    This class holds the configuration for calling remote agent APIs,
    including endpoint URL, request parameters, headers, and response parsing rules.
    """

    # API endpoint configuration
    api_url: str
    http_method: HttpMethod = HttpMethod.POST
    timeout: int = 300  # Default timeout 300 seconds for agent tasks

    # Request configuration
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, Any] = field(default_factory=dict)

    # Response parsing configuration
    parse_strategy: ResponseParseStrategy = ResponseParseStrategy.JSON_PATH

    # JSON path expressions for extracting response fields
    # Example: {"content": "$.data.result", "tokens": "$.data.usage.total_tokens"}
    response_mapping: Dict[str, str] = field(default_factory=dict)

    # Retry configuration
    max_retries: int = 3
    retry_delay: int = 1  # seconds

    # Additional configuration
    verify_ssl: bool = True
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.api_url:
            raise ValueError("api_url is required")

        # Set default headers
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json; charset=UTF-8"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "api_url": self.api_url,
            "http_method": self.http_method.value,
            "timeout": self.timeout,
            "headers": self.headers,
            "query_params": self.query_params,
            "parse_strategy": self.parse_strategy.value,
            "response_mapping": self.response_mapping,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "verify_ssl": self.verify_ssl,
            "extra_config": self.extra_config,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AgentApiConfig":
        """Create configuration from dictionary."""
        return cls(
            api_url=config_dict.get("api_url", ""),
            http_method=HttpMethod(config_dict.get("http_method", "POST")),
            timeout=config_dict.get("timeout", 300),
            headers=config_dict.get("headers", {}),
            query_params=config_dict.get("query_params", {}),
            parse_strategy=ResponseParseStrategy(
                config_dict.get("parse_strategy", "JSON_PATH")
            ),
            response_mapping=config_dict.get("response_mapping", {}),
            max_retries=config_dict.get("max_retries", 3),
            retry_delay=config_dict.get("retry_delay", 1),
            verify_ssl=config_dict.get("verify_ssl", True),
            extra_config=config_dict.get("extra_config", {}),
        )


@dataclass
class BenchmarkExecuteConfig:
    """
    Benchmark Execute Config
    """

    # base config
    file_parse_type: FileParseTypeEnum = FileParseTypeEnum.EXCEL
    format_type: FormatTypeEnum = FormatTypeEnum.TEXT
    content_type: ContentTypeEnum = ContentTypeEnum.SQL
    benchmark_mode_type: BenchmarkModeTypeEnum = BenchmarkModeTypeEnum.EXECUTE

    # file path config
    output_file_path: Optional[str] = None
    standard_file_path: str = None
    input_file_path: Optional[str] = None

    # runtime execute config

    # current only support 1 round to execute benchmark
    round_time: int = 1
    generate_ratio: int = 5
    execute_llm_result: bool = True
    invoke_llm: bool = True
    thread_num: Optional[int] = None
    invoke_type: BenchmarkInvokeType = BenchmarkInvokeType.LLM

    # llm thread config
    llm_thread_map: Dict[str, int] = field(default=None)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # compare result config
    compare_result_enable: bool = True
    compare_config: Dict[str, str] = field(default=None)

    # user config
    user_id: Optional[str] = None

    # task config
    evaluate_code: Optional[str] = None
    scene_key: Optional[str] = None

    # agent config
    agent_config: AgentApiConfig = None

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
            "evaluate_code": self.evaluate_code,
            "scene_key": self.scene_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
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
            evaluate_code=config_dict.get("evaluate_code"),
            scene_key=config_dict.get("scene_key"),
            temperature=config_dict.get("temperature"),
            max_tokens=config_dict.get("max_tokens"),
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial_no": self.serial_no,
            "analysis_model_id": self.analysis_model_id,
            "question": self.question,
            "self_define_tags": self.self_define_tags,
            "knowledge": self.knowledge,
            "llm_output": self.llm_output,
            "llm_code": self.llm_code,
            "prompt": self.prompt,
        }


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


@dataclass
class AgentCompletionRequest:
    """benchmark Agent request entity."""

    model: Optional[str] = None
    messages: Optional[List[dict]] = (None,)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = None
    user: Optional[str] = None
    app_name: str = "dbgpt"
