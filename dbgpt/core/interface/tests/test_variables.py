import base64
import os

from cryptography.fernet import Fernet

from ..variables import (
    FernetEncryption,
    InMemoryStorage,
    SimpleEncryption,
    StorageVariables,
    StorageVariablesProvider,
    VariablesIdentifier,
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

    full_key = "key@name@global"
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
    full_key = "key@name@global@scope_key@sys_code@user_name"
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
