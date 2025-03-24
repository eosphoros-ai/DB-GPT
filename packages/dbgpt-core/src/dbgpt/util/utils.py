import asyncio
import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass, field
from typing import Any, List, Optional, cast

from dbgpt.configs.model_config import resolve_root_path
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


server_error_msg = (
    "**NETWORK ERROR DUE TO HIGH TRAFFIC. PLEASE REGENERATE OR REFRESH THIS PAGE.**"
)

handler = None


def _get_logging_level() -> str:
    return os.getenv("DBGPT_LOG_LEVEL", "INFO")


@dataclass
class LoggingParameters(BaseParameters):
    """Logging parameters."""

    __cfg_type__ = "utils"

    level: Optional[str] = field(
        default="${env:DBGPT_LOG_LEVEL:-INFO}",
        metadata={
            "help": _(
                "Logging level, just support FATAL, ERROR, WARNING, INFO, DEBUG, NOTSET"
            ),
            "valid_values": [
                "FATAL",
                "ERROR",
                "WARNING",
                "WARNING",
                "INFO",
                "DEBUG",
                "NOTSET",
            ],
        },
    )
    file: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The filename to store logs"),
        },
    )

    def get_real_log_file(self) -> Optional[str]:
        """Get the real log file path.

        It will resolve the root path if the log file is not None.
        """
        if self.file:
            return resolve_root_path(self.file)
        return None


def setup_logging_level(
    logging_level: Optional[str] = None, logger_name: Optional[str] = None
):
    if not logging_level:
        logging_level = _get_logging_level()
    if type(logging_level) is str:
        logging_level = logging.getLevelName(logging_level.upper())
    if logger_name:
        logger = logging.getLogger(logger_name)
        logger.setLevel(cast(str, logging_level))
    else:
        logging.basicConfig(level=logging_level, encoding="utf-8")


def setup_logging(
    logger_name: str,
    log_config: Optional[LoggingParameters] = None,
    default_logger_level: Optional[str] = None,
    default_logger_filename: Optional[str] = None,
    redirect_stdio: bool = False,
):
    if log_config:
        logging_level = log_config.level or default_logger_level
        logger_filename = log_config.get_real_log_file() or default_logger_filename
    else:
        logging_level = default_logger_level
        logger_filename = default_logger_filename
    if not logging_level:
        logging_level = _get_logging_level()
    logger_filename = resolve_root_path(logger_filename)
    logger = _build_logger(logger_name, logging_level, logger_filename, redirect_stdio)
    try:
        import coloredlogs

        color_level = logging_level if logging_level else "INFO"
        coloredlogs.install(level=color_level, logger=logger)
    except ImportError:
        pass


def get_gpu_memory(max_gpus=None):
    import torch

    gpu_memory = []
    num_gpus = (
        torch.cuda.device_count()
        if max_gpus is None
        else min(max_gpus, torch.cuda.device_count())
    )
    for gpu_id in range(num_gpus):
        with torch.cuda.device(gpu_id):
            device = torch.cuda.current_device()
            gpu_properties = torch.cuda.get_device_properties(device)
            total_memory = gpu_properties.total_memory / (1024**3)
            allocated_memory = torch.cuda.memory_allocated() / (1024**3)
            available_memory = total_memory - allocated_memory
            gpu_memory.append(available_memory)
    return gpu_memory


def _build_logger(
    logger_name,
    logging_level: Optional[str] = None,
    logger_filename: Optional[str] = None,
    redirect_stdio: bool = False,
):
    global handler

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the format of root handlers
    if not logging.getLogger().handlers:
        setup_logging_level(logging_level=logging_level)
    logging.getLogger().handlers[0].setFormatter(formatter)

    # Add a file handler for all loggers
    if handler is None and logger_filename:
        logger_dir = os.path.dirname(logger_filename)
        os.makedirs(logger_dir, exist_ok=True)
        handler = logging.handlers.TimedRotatingFileHandler(
            logger_filename, when="D", utc=True, encoding="utf-8"
        )
        handler.setFormatter(formatter)

        # Ensure the handler level is set correctly
        if logging_level is not None:
            handler.setLevel(logging_level)
        logging.getLogger().addHandler(handler)
        for name, item in logging.root.manager.loggerDict.items():
            if isinstance(item, logging.Logger):
                item.addHandler(handler)
                item.propagate = True
                logging.getLogger(name).debug(f"Added handler to logger: {name}")
            else:
                logging.getLogger(name).debug(f"Skipping non-logger: {name}")

        if redirect_stdio:
            stdout_handler = logging.StreamHandler(sys.stdout, encoding="utf-8")
            stdout_handler.setFormatter(formatter)
            stderr_handler = logging.StreamHandler(sys.stderr, encoding="utf-8")
            stderr_handler.setFormatter(formatter)

            root_logger = logging.getLogger()
            root_logger.addHandler(stdout_handler)
            root_logger.addHandler(stderr_handler)
            logging.getLogger().debug("Added stdout and stderr handlers to root logger")
    logger = logging.getLogger(logger_name)

    setup_logging_level(logging_level=logging_level, logger_name=logger_name)

    # Debugging to print all handlers
    logging.getLogger(logger_name).debug(
        f"Logger {logger_name} handlers: {logger.handlers}"
    )
    logging.getLogger(logger_name).debug(f"Global handler: {handler}")

    return logger


def get_or_create_event_loop() -> asyncio.BaseEventLoop:
    loop = None
    try:
        loop = asyncio.get_event_loop()
        assert loop is not None
        return cast(asyncio.BaseEventLoop, loop)
    except RuntimeError as e:
        if "no running event loop" not in str(e) and "no current event loop" not in str(
            e
        ):
            raise e
        logging.warning("Cant not get running event loop, create new event loop now")
    return cast(asyncio.BaseEventLoop, asyncio.get_event_loop_policy().new_event_loop())


def logging_str_to_uvicorn_level(log_level_str):
    level_str_mapping = {
        "CRITICAL": "critical",
        "ERROR": "error",
        "WARNING": "warning",
        "INFO": "info",
        "DEBUG": "debug",
        "NOTSET": "info",
    }
    return level_str_mapping.get(log_level_str.upper(), "info")


class EndpointFilter(logging.Filter):
    """Disable access log on certain endpoint

    source: https://github.com/encode/starlette/issues/864#issuecomment-1254987630
    """

    def __init__(
        self,
        path: str,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find(self._path) == -1


def setup_http_service_logging(exclude_paths: Optional[List[str]] = None):
    """Setup http service logging

    Now just disable some logs

    Args:
        exclude_paths (List[str]): The paths to disable log
    """
    if not exclude_paths:
        # Not show heartbeat log
        exclude_paths = ["/api/controller/heartbeat", "/api/health"]
    uvicorn_logger = logging.getLogger("uvicorn.access")
    if uvicorn_logger:
        for path in exclude_paths:
            uvicorn_logger.addFilter(EndpointFilter(path=path))
    httpx_logger = logging.getLogger("httpx")
    if httpx_logger:
        httpx_logger.setLevel(logging.WARNING)
