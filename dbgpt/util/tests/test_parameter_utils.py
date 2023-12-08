import argparse
import pytest
from dbgpt.util.parameter_utils import _extract_parameter_details


def create_parser():
    parser = argparse.ArgumentParser()
    return parser


@pytest.mark.parametrize(
    "argument, expected_param_name, default_value, param_type, expected_param_type, description",
    [
        ("--option", "option", "value", str, "str", "An option argument"),
        ("-option", "option", "value", str, "str", "An option argument"),
        ("--num-gpu", "num_gpu", 1, int, "int", "Number of GPUS"),
        ("--num_gpu", "num_gpu", 1, int, "int", "Number of GPUS"),
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
    assert desc.required == False
    assert desc.valid_values is None


def test_extract_parameter_details_flag_argument():
    parser = create_parser()
    parser.add_argument("--flag", action="store_true", help="A flag argument")
    descriptions = _extract_parameter_details(parser)

    assert len(descriptions) == 1
    desc = descriptions[0]

    assert desc.param_name == "flag"
    assert desc.description == "A flag argument"
    assert desc.required == False


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
    assert desc.required == True
