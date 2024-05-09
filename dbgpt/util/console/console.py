"""Console utility functions for CLI."""

import dataclasses
import sys
from functools import lru_cache
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.theme import Theme


@dataclasses.dataclass
class Output:
    """Output file."""

    title: str
    file: str


def _get_theme():
    return Theme(
        {
            "success": "green",
            "info": "bright_blue",
            "warning": "bright_yellow",
            "error": "red",
        }
    )


@lru_cache(maxsize=None)
def get_console(output: Output | None = None) -> Console:
    return Console(
        force_terminal=True,
        color_system="standard",
        theme=_get_theme(),
        file=output.file if output else None,
    )


class CliLogger:
    def __init__(self, output: Output | None = None):
        self.console = get_console(output)

    def success(self, msg: str, **kwargs):
        self.console.print(f"[success]{msg}[/]", **kwargs)

    def info(self, msg: str, **kwargs):
        self.console.print(f"[info]{msg}[/]", **kwargs)

    def warning(self, msg: str, **kwargs):
        self.console.print(f"[warning]{msg}[/]", **kwargs)

    def error(self, msg: str, exit_code: int = 0, **kwargs):
        self.console.print(f"[error]{msg}[/]", **kwargs)
        if exit_code != 0:
            sys.exit(exit_code)

    def debug(self, msg: str, **kwargs):
        self.console.print(f"[cyan]{msg}[/]", **kwargs)

    def print(self, *objects: Any, sep: str = " ", end: str = "\n", **kwargs):
        self.console.print(*objects, sep=sep, end=end, **kwargs)

    def markdown(self, msg: str, **kwargs):
        md = Markdown(msg)
        self.console.print(md, **kwargs)

    def ask(self, msg: str, **kwargs):
        return Prompt.ask(msg, **kwargs)
