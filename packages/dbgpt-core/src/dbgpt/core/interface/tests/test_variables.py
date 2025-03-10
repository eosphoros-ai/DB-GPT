import base64
import os
from itertools import product

from cryptography.fernet import Fernet

from ..variables import (
    FernetEncryption,
    InMemoryStorage,
    SimpleEncryption,
    StorageVariables,
    StorageVariablesProvider,
    VariablesIdentifier,
    build_variable_string,
    parse_variable,
)


def test_fernet_encryption():
    key = Fernet.generate_key()
    encryption = FernetEncryption(key)
    new_encryption = FernetEncryption(key)
    data = "test_data"
    salt = "test_salt"

    encrypted_data = encryption.encrypt(data, salt)
    assert encrypted_data != data

    decrypted_data = encryption.decrypt(encrypted_data, salt)
    assert decrypted_data == data
    assert decrypted_data == new_encryption.decrypt(encrypted_data, salt)


def test_simple_encryption():
    key = base64.b64encode(os.urandom(32)).decode()
    encryption = SimpleEncryption(key)
    data = "test_data"
    salt = "test_salt"

    encrypted_data = encryption.encrypt(data, salt)
    assert encrypted_data != data

    decrypted_data = encryption.decrypt(encrypted_data, salt)
    assert decrypted_data == data


def test_storage_variables_provider():
    storage = InMemoryStorage()
    encryption = SimpleEncryption()
    provider = StorageVariablesProvider(storage, encryption)

    full_key = "${key:name@global}"
    value = "secret_value"
    value_type = "str"
    label = "test_label"

    id = VariablesIdentifier.from_str_identifier(full_key)
    provider.save(
        StorageVariables.from_identifier(
            id, value, value_type, label, category="secret"
        )
    )

    loaded_variable_value = provider.get(full_key)
    assert loaded_variable_value == value


def test_variables_identifier():
    full_key = "${key:name@global:scope_key#sys_code%user_name}"
    identifier = VariablesIdentifier.from_str_identifier(full_key)

    assert identifier.key == "key"
    assert identifier.name == "name"
    assert identifier.scope == "global"
    assert identifier.scope_key == "scope_key"
    assert identifier.sys_code == "sys_code"
    assert identifier.user_name == "user_name"

    str_identifier = identifier.str_identifier
    assert str_identifier == full_key


def test_storage_variables():
    key = "test_key"
    name = "test_name"
    label = "test_label"
    value = "test_value"
    value_type = "str"
    category = "common"
    scope = "global"

    storage_variable = StorageVariables(
        key=key,
        name=name,
        label=label,
        value=value,
        value_type=value_type,
        category=category,
        scope=scope,
    )

    assert storage_variable.key == key
    assert storage_variable.name == name
    assert storage_variable.label == label
    assert storage_variable.value == value
    assert storage_variable.value_type == value_type
    assert storage_variable.category == category
    assert storage_variable.scope == scope

    dict_representation = storage_variable.to_dict()
    assert dict_representation["key"] == key
    assert dict_representation["name"] == name
    assert dict_representation["label"] == label
    assert dict_representation["value"] == value
    assert dict_representation["value_type"] == value_type
    assert dict_representation["category"] == category
    assert dict_representation["scope"] == scope


def generate_test_cases(enable_escape=False):
    # Define possible values for each field, including special characters for escaping
    _EMPTY_ = "___EMPTY___"
    fields = {
        "name": [
            None,
            "test_name",
            "test:name" if enable_escape else _EMPTY_,
            "test::name" if enable_escape else _EMPTY_,
            "test#name" if enable_escape else _EMPTY_,
            "test##name" if enable_escape else _EMPTY_,
            "test::@@@#22name" if enable_escape else _EMPTY_,
        ],
        "scope": [
            None,
            "test_scope",
            "test@scope" if enable_escape else _EMPTY_,
            "test@@scope" if enable_escape else _EMPTY_,
            "test:scope" if enable_escape else _EMPTY_,
            "test:#:scope" if enable_escape else _EMPTY_,
        ],
        "scope_key": [
            None,
            "test_scope_key",
            "test:scope_key" if enable_escape else _EMPTY_,
        ],
        "sys_code": [
            None,
            "test_sys_code",
            "test#sys_code" if enable_escape else _EMPTY_,
        ],
        "user_name": [
            None,
            "test_user_name",
            "test%user_name" if enable_escape else _EMPTY_,
        ],
    }
    # Remove empty values
    fields = {k: [v for v in values if v != _EMPTY_] for k, values in fields.items()}

    # Generate all possible combinations
    combinations = product(*fields.values())

    test_cases = []
    for combo in combinations:
        name, scope, scope_key, sys_code, user_name = combo

        var_str = build_variable_string(
            {
                "key": "test_key",
                "name": name,
                "scope": scope,
                "scope_key": scope_key,
                "sys_code": sys_code,
                "user_name": user_name,
            },
            enable_escape=enable_escape,
        )

        # Construct the expected output
        expected = {
            "key": "test_key",
            "name": name,
            "scope": scope,
            "scope_key": scope_key,
            "sys_code": sys_code,
            "user_name": user_name,
        }

        test_cases.append((var_str, expected, enable_escape))

    return test_cases


def test_parse_variables():
    # Run test cases without escape
    test_cases = generate_test_cases(enable_escape=False)
    for i, (input_str, expected_output, enable_escape) in enumerate(test_cases, 1):
        result = parse_variable(input_str, enable_escape=enable_escape)
        assert result == expected_output, f"Test case {i} failed without escape"

    # Run test cases with escape
    test_cases = generate_test_cases(enable_escape=True)
    for i, (input_str, expected_output, enable_escape) in enumerate(test_cases, 1):
        print(f"input_str: {input_str}, expected_output: {expected_output}")
        result = parse_variable(input_str, enable_escape=enable_escape)
        assert result == expected_output, f"Test case {i} failed with escape"


def generate_build_test_cases(enable_escape=False):
    # Define possible values for each field, including special characters for escaping
    _EMPTY_ = "___EMPTY___"
    fields = {
        "name": [
            None,
            "test_name",
            "test:name" if enable_escape else _EMPTY_,
            "test::name" if enable_escape else _EMPTY_,
            "test\name" if enable_escape else _EMPTY_,
            "test\\name" if enable_escape else _EMPTY_,
            "test\:\#\@\%name" if enable_escape else _EMPTY_,
            "test\::\###\@@\%%name" if enable_escape else _EMPTY_,
            "test\\::\\###\\@@\\%%name" if enable_escape else _EMPTY_,
            "test\:#:name" if enable_escape else _EMPTY_,
        ],
        "scope": [None, "test_scope", "test@scope" if enable_escape else _EMPTY_],
        "scope_key": [
            None,
            "test_scope_key",
            "test:scope_key" if enable_escape else _EMPTY_,
        ],
        "sys_code": [
            None,
            "test_sys_code",
            "test#sys_code" if enable_escape else _EMPTY_,
        ],
        "user_name": [
            None,
            "test_user_name",
            "test%user_name" if enable_escape else _EMPTY_,
        ],
    }
    # Remove empty values
    fields = {k: [v for v in values if v != _EMPTY_] for k, values in fields.items()}

    # Generate all possible combinations
    combinations = product(*fields.values())

    test_cases = []

    def escape_special_chars(s):
        if not enable_escape or s is None:
            return s
        return (
            s.replace(":", "\\:")
            .replace("@", "\\@")
            .replace("%", "\\%")
            .replace("#", "\\#")
        )

    for combo in combinations:
        name, scope, scope_key, sys_code, user_name = combo

        # Construct the input dictionary
        input_dict = {
            "key": "test_key",
            "name": name,
            "scope": scope,
            "scope_key": scope_key,
            "sys_code": sys_code,
            "user_name": user_name,
        }
        input_dict_with_escape = {
            k: escape_special_chars(v) for k, v in input_dict.items()
        }

        # Construct the expected variable string
        expected_str = "${test_key"
        if name:
            expected_str += f":{input_dict_with_escape['name']}"
        if scope or scope_key:
            expected_str += "@"
            if scope:
                expected_str += input_dict_with_escape["scope"]
            if scope_key:
                expected_str += f":{input_dict_with_escape['scope_key']}"
        if sys_code:
            expected_str += f"#{input_dict_with_escape['sys_code']}"
        if user_name:
            expected_str += f"%{input_dict_with_escape['user_name']}"
        expected_str += "}"

        test_cases.append((input_dict, expected_str, enable_escape))

    return test_cases


def test_build_variable_string():
    # Run test cases without escape
    test_cases = generate_build_test_cases(enable_escape=False)
    for i, (input_dict, expected_str, enable_escape) in enumerate(test_cases, 1):
        result = build_variable_string(input_dict, enable_escape=enable_escape)
        assert result == expected_str, f"Test case {i} failed without escape"

    # Run test cases with escape
    test_cases = generate_build_test_cases(enable_escape=True)
    for i, (input_dict, expected_str, enable_escape) in enumerate(test_cases, 1):
        print(f"input_dict: {input_dict}, expected_str: {expected_str}")
        result = build_variable_string(input_dict, enable_escape=enable_escape)
        assert result == expected_str, f"Test case {i} failed with escape"


def test_variable_string_round_trip():
    # Run test cases without escape
    test_cases = generate_test_cases(enable_escape=False)
    for i, (input_str, expected_output, enable_escape) in enumerate(test_cases, 1):
        parsed_result = parse_variable(input_str, enable_escape=enable_escape)
        built_result = build_variable_string(parsed_result, enable_escape=enable_escape)
        assert built_result == input_str, (
            f"Round trip test case {i} failed without escape"
        )

    # Run test cases with escape
    test_cases = generate_test_cases(enable_escape=True)
    for i, (input_str, expected_output, enable_escape) in enumerate(test_cases, 1):
        parsed_result = parse_variable(input_str, enable_escape=enable_escape)
        built_result = build_variable_string(parsed_result, enable_escape=enable_escape)
        assert built_result == input_str, f"Round trip test case {i} failed with escape"
