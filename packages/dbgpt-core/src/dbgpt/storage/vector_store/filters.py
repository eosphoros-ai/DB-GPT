"""Vector Store Meta data filters."""

from enum import Enum
from typing import List, Union

from dbgpt._private.pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    """Meta data filter operator."""

    EQ = "=="
    GT = ">"
    LT = "<"
    NE = "!="
    GTE = ">="
    LTE = "<="
    IN = "in"
    NIN = "nin"
    EXISTS = "exists"


class FilterCondition(str, Enum):
    """Vector Store Meta data filter conditions."""

    AND = "and"
    OR = "or"


class MetadataFilter(BaseModel):
    """Meta data filter."""

    key: str = Field(
        ...,
        description="The key of metadata to filter.",
    )
    operator: FilterOperator = Field(
        default=FilterOperator.EQ,
        description="The operator of metadata filter.",
    )
    value: Union[str, int, float, List[str], List[int], List[float]] = Field(
        ...,
        description="The value of metadata to filter.",
    )


class MetadataFilters(BaseModel):
    """Meta data filters."""

    condition: FilterCondition = Field(
        default=FilterCondition.AND,
        description="The condition of metadata filters.",
    )
    filters: List[MetadataFilter] = Field(
        ...,
        description="The metadata filters.",
    )
