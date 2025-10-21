import pytest
from dbgpt.util.string_utils import str_to_bool


def test_str_to_bool_positive():
    assert str_to_bool("true") is True
    assert str_to_bool("t") is True
    assert str_to_bool("1") is True
    assert str_to_bool("yes") is True
    assert str_to_bool("y") is True


def test_str_to_bool_negative():
    assert str_to_bool("false") is False
    assert str_to_bool("f") is False
    assert str_to_bool("0") is False
    assert str_to_bool("no") is False
    assert str_to_bool("n") is False


def test_str_to_bool_edge_cases():
    with pytest.raises(ValueError):
        str_to_bool("true_dat")
    with pytest.raises(ValueError):
        str_to_bool("false_dat")
    with pytest.raises(ValueError):
        str_to_bool("t_rue")
    with pytest.raises(ValueError):
        str_to_bool("f_alse")
    with pytest.raises(ValueError):
        str_to_bool("")
