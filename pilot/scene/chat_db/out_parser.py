import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from pilot.out_parser.base import BaseOutputParser


class SqlAction(NamedTuple):
    SQL: str
    thoughts: Dict


class DbChatOutputParser(BaseOutputParser):

    def parse(self, text: str) -> SqlAction:
        cleaned_output = text.rstrip()
        if "```json" in cleaned_output:
            _, cleaned_output = cleaned_output.split("```json")
        if "```" in cleaned_output:
            cleaned_output, _ = cleaned_output.split("```")
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output[len("```json"):]
        if cleaned_output.startswith("```"):
            cleaned_output = cleaned_output[len("```"):]
        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output[: -len("```")]
        cleaned_output = cleaned_output.strip()
        response = json.loads(cleaned_output)
        sql, thoughts = response["SQL"], response["thoughts"]

        return SqlAction(sql, thoughts)

    @property
    def _type(self) -> str:
        return "sql_chat"
