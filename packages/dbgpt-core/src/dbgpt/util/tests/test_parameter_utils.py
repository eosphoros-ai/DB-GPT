import argparse
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import List, Optional, Union

import pytest

from ..parameter_utils import (
    _extract_parameter_details,
    _get_parameter_descriptions,
)


def create_parser():
    parser = argparse.ArgumentParser()
    return parser


@pytest.mark.parametrize(
    "argument, expected_param_name, default_value, param_type, expected_param_type, "
    "description",
    [
        ("--option", "option", "value", str, "string", "An option argument"),
        ("-option", "option", "value", str, "string", "An option argument"),
        ("--num-gpu", "num_gpu", 1, int, "integer", "Number of GPUS"),
        ("--num_gpu", "num_gpu", 1, int, "integer", "Number of GPUS"),
    ],
)
def test_extract_parameter_details_option_argument(
    argument,
    expected_param_name,
    default_value,
    param_type,
    expected_param_type,
    description,
):
    parser = create_parser()
    parser.add_argument(
        argument, default=default_value, type=param_type, help=description
    )
    descriptions = _extract_parameter_details(parser)

    assert len(descriptions) == 1
    desc = descriptions[0]

    assert desc.param_name == expected_param_name
    assert desc.param_type == expected_param_type
    assert desc.default_value == default_value
    assert desc.description == description
    assert desc.required is False
    assert desc.valid_values is None


def test_extract_parameter_details_flag_argument():
    parser = create_parser()
    parser.add_argument("--flag", action="store_true", help="A flag argument")
    descriptions = _extract_parameter_details(parser)

    assert len(descriptions) == 1
    desc = descriptions[0]

    assert desc.param_name == "flag"
    assert desc.description == "A flag argument"
    assert desc.required is False


def test_extract_parameter_details_choice_argument():
    parser = create_parser()
    parser.add_argument("--choice", choices=["A", "B", "C"], help="A choice argument")
    descriptions = _extract_parameter_details(parser)

    assert len(descriptions) == 1
    desc = descriptions[0]

    assert desc.param_name == "choice"
    assert desc.valid_values == ["A", "B", "C"]


def test_extract_parameter_details_required_argument():
    parser = create_parser()
    parser.add_argument(
        "--required", required=True, type=int, help="A required argument"
    )
    descriptions = _extract_parameter_details(parser)

    assert len(descriptions) == 1
    desc = descriptions[0]

    assert desc.param_name == "required"
    assert desc.required is True


def test_extract_field_type():
    from ..parameter_utils import _get_parameter_descriptions

    @dataclass
    class TestBaseType:
        p1: str = field(metadata={"help": "p1 help"})
        p2: int = field(metadata={"help": "p2 help"})
        p3: float = field(metadata={"help": "p3 help"})
        p4: bool = field(metadata={"help": "p4 help"})

    field_dict = {}
    for f in fields(TestBaseType):
        field_dict[f.name] = f

    desc_list = _get_parameter_descriptions(TestBaseType)
    assert desc_list[0].param_name == "p1"
    assert desc_list[0].param_type == "string"
    assert desc_list[0].required is True
    assert desc_list[0].description == "p1 help"
    assert desc_list[1].param_name == "p2"
    assert desc_list[1].param_type == "integer"
    assert desc_list[1].required is True
    assert desc_list[1].description == "p2 help"
    assert desc_list[2].param_name == "p3"
    assert desc_list[2].param_type == "number"
    assert desc_list[2].required is True
    assert desc_list[2].description == "p3 help"
    assert desc_list[3].param_name == "p4"
    assert desc_list[3].param_type == "boolean"
    assert desc_list[3].required is True
    assert desc_list[3].description == "p4 help"


def test_extract_complex_field_type():
    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    @dataclass
    class NestedConfig:
        nested_str: str = field(metadata={"help": "nested string help"})
        nested_int: int = 42

    @dataclass
    class ComplexConfig:
        # Test field with default value
        str_with_default: str = field(
            default="str_with_default", metadata={"help": "string with default"}
        )

        # Test list type
        str_list: List[str] = field(
            default_factory=list, metadata={"help": "string list help"}
        )

        # Test optional type with typing.Optional
        optional_int: Optional[int] = field(
            default=None, metadata={"help": "optional integer"}
        )

        # Test enum type
        color: Color = field(default=Color.RED, metadata={"help": "color choice"})

        # Test nested dataclass
        nested: NestedConfig = field(
            default_factory=lambda: NestedConfig(nested_str="nested"),
            metadata={"help": "nested config"},
        )

    desc_list = _get_parameter_descriptions(ComplexConfig)

    # Test field with default value
    assert desc_list[0].param_name == "str_with_default"
    assert desc_list[0].param_type == "string"
    assert desc_list[0].required is False
    assert desc_list[0].description == "string with default"

    # Test list type
    assert desc_list[1].param_name == "str_list"
    assert desc_list[1].param_type == "string"
    assert desc_list[1].is_array is True
    assert desc_list[1].required is False

    # Test optional type
    assert desc_list[2].param_name == "optional_int"
    assert desc_list[2].param_type == "integer"
    assert desc_list[2].required is False

    # Test enum type
    assert desc_list[3].param_name == "color"
    assert desc_list[3].param_type == "Color"
    assert desc_list[3].required is False

    # Test nested dataclass field
    assert desc_list[4].param_name == "nested"
    assert desc_list[4].param_type == "NestedConfig"
    assert desc_list[4].required is False


def test_extract_union_field_type():
    @dataclass
    class ComplexConfig:
        # Test Union type with typing.Union
        union_field: Union[str, int] = field(
            default="union_field", metadata={"help": "union of string and int"}
        )

    desc_list = _get_parameter_descriptions(ComplexConfig)
    # Test union type
    assert desc_list[0].param_name == "union_field"
    assert desc_list[0].param_type == "string"
    assert desc_list[0].required is False


def test_python_type_hint_variations():
    """Test different Python syntax versions for type hints"""
    from dataclasses import dataclass, field
    from typing import Optional, Union

    @dataclass
    class TypeHintConfig:
        # Test typing.Optional syntax
        typing_optional: Optional[int] = field(
            default=None, metadata={"help": "using typing.Optional"}
        )

        # Test Python 3.10+ union syntax with |
        pipe_optional: int | None = field(
            default=None, metadata={"help": "using | None syntax"}
        )

        # Test typing.Union syntax
        typing_union: Union[str, int] = field(
            default="test", metadata={"help": "using typing.Union"}
        )

        # Test Python 3.10+ union syntax for multiple types
        pipe_union: str | int = field(
            default="test", metadata={"help": "using | for union"}
        )

        # Test nested Optional with Union
        nested_optional: Optional[Union[str, int]] = field(
            default=None, metadata={"help": "nested optional with union"}
        )

        # Test nested | syntax
        nested_pipe: (
            str | int
        ) | None = field(default=None, metadata={"help": "nested | syntax"})

    desc_list = _get_parameter_descriptions(TypeHintConfig)

    # Test typing.Optional handling
    assert desc_list[0].param_name == "typing_optional"
    assert desc_list[0].param_type == "integer"
    assert desc_list[0].required is False

    # Test | None syntax handling
    assert desc_list[1].param_name == "pipe_optional"
    assert desc_list[1].param_type == "integer"  # Should normalize to Optional[int]
    assert desc_list[1].required is False

    # Test typing.Union handling
    assert desc_list[2].param_name == "typing_union"
    assert desc_list[2].param_type == "string"

    assert desc_list[2].required is False

    # Test | union syntax handling
    assert desc_list[3].param_name == "pipe_union"
    assert (
        desc_list[3].param_type == "string, integer"
    )  # Should normalize to Union[str, int]
    assert desc_list[3].required is False

    # Test nested Optional with Union
    assert desc_list[4].param_name == "nested_optional"
    assert desc_list[4].param_type == "string"
    assert desc_list[4].required is False

    # Test nested | syntax
    assert desc_list[5].param_name == "nested_pipe"
    assert (
        desc_list[5].param_type == "string, integer"
    )  # Should normalize to Optional[Union]
    assert desc_list[5].required is False


def test_nested_dataclass_fields():
    """Test nested dataclass fields with different type hints"""

    @dataclass
    class Inner:
        required_field: str = field(metadata={"help": "required inner field"})
        optional_field_typing: Optional[int] = field(
            default=None, metadata={"help": "optional inner field with typing.Optional"}
        )
        optional_field_pipe: int | None = field(
            default=None, metadata={"help": "optional inner field with | syntax"}
        )

    @dataclass
    class Outer:
        outer_str: str = field(metadata={"help": "outer string"})
        inner_typing: Optional[Inner] = field(
            default=None, metadata={"help": "inner config with typing.Optional"}
        )
        inner_pipe: Inner | None = field(
            default=None, metadata={"help": "inner config with | syntax"}
        )
        list_inner: List[Inner] = field(
            default_factory=list, metadata={"help": "list of inner configs"}
        )

    desc_list = _get_parameter_descriptions(Outer)

    # Test outer required field
    assert desc_list[0].param_name == "outer_str"
    assert desc_list[0].param_type == "string"
    assert desc_list[0].required is True

    # Test nested Optional[Inner] field
    assert desc_list[1].param_name == "inner_typing"
    assert desc_list[1].param_type == "Inner"
    assert desc_list[1].required is False

    # Test nested Inner | None field
    assert desc_list[2].param_name == "inner_pipe"
    # Should normalize to Optional[Inner]
    assert desc_list[2].param_type == "Inner"
    assert desc_list[2].required is False

    # Test list of Inner configs
    assert desc_list[3].param_name == "list_inner"
    assert desc_list[3].param_type == "Inner"
    assert desc_list[3].is_array is True
