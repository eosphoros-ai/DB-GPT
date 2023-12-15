import pytest

from dbgpt.core.interface.tests.conftest import in_memory_storage
from dbgpt.core.interface.message import *


@pytest.fixture
def basic_conversation():
    return OnceConversation(chat_mode="chat_normal", user_name="user1", sys_code="sys1")


@pytest.fixture
def human_message():
    return HumanMessage(content="Hello")


@pytest.fixture
def ai_message():
    return AIMessage(content="Hi there")


@pytest.fixture
def system_message():
    return SystemMessage(content="System update")


@pytest.fixture
def view_message():
    return ViewMessage(content="View this")


@pytest.fixture
def conversation_identifier():
    return ConversationIdentifier("conv1")


@pytest.fixture
def message_identifier():
    return MessageIdentifier("conv1", 1)


@pytest.fixture
def message_storage_item():
    message = HumanMessage(content="Hello", index=1)
    message_detail = message.to_dict()
    return MessageStorageItem("conv1", 1, message_detail)


@pytest.fixture
def storage_conversation():
    return StorageConversation("conv1", chat_mode="chat_normal", user_name="user1")


@pytest.fixture
def conversation_with_messages():
    conv = OnceConversation(chat_mode="chat_normal", user_name="user1")
    conv.start_new_round()
    conv.add_user_message("Hello")
    conv.add_ai_message("Hi")
    conv.end_current_round()

    conv.start_new_round()
    conv.add_user_message("How are you?")
    conv.add_ai_message("I'm good, thanks")
    conv.end_current_round()

    return conv


def test_init(basic_conversation):
    assert basic_conversation.chat_mode == "chat_normal"
    assert basic_conversation.user_name == "user1"
    assert basic_conversation.sys_code == "sys1"
    assert basic_conversation.messages == []
    assert basic_conversation.start_date == ""
    assert basic_conversation.chat_order == 0
    assert basic_conversation.model_name == ""
    assert basic_conversation.param_type == ""
    assert basic_conversation.param_value == ""
    assert basic_conversation.cost == 0
    assert basic_conversation.tokens == 0
    assert basic_conversation._message_index == 0


def test_add_user_message(basic_conversation, human_message):
    basic_conversation.add_user_message(human_message.content)
    assert len(basic_conversation.messages) == 1
    assert isinstance(basic_conversation.messages[0], HumanMessage)


def test_add_ai_message(basic_conversation, ai_message):
    basic_conversation.add_ai_message(ai_message.content)
    assert len(basic_conversation.messages) == 1
    assert isinstance(basic_conversation.messages[0], AIMessage)


def test_add_system_message(basic_conversation, system_message):
    basic_conversation.add_system_message(system_message.content)
    assert len(basic_conversation.messages) == 1
    assert isinstance(basic_conversation.messages[0], SystemMessage)


def test_add_view_message(basic_conversation, view_message):
    basic_conversation.add_view_message(view_message.content)
    assert len(basic_conversation.messages) == 1
    assert isinstance(basic_conversation.messages[0], ViewMessage)


def test_set_start_time(basic_conversation):
    now = datetime.now()
    basic_conversation.set_start_time(now)
    assert basic_conversation.start_date == now.strftime("%Y-%m-%d %H:%M:%S")


def test_clear_messages(basic_conversation, human_message):
    basic_conversation.add_user_message(human_message.content)
    basic_conversation.clear()
    assert len(basic_conversation.messages) == 0


def test_get_latest_user_message(basic_conversation, human_message):
    basic_conversation.add_user_message(human_message.content)
    latest_message = basic_conversation.get_latest_user_message()
    assert latest_message == human_message


def test_get_system_messages(basic_conversation, system_message):
    basic_conversation.add_system_message(system_message.content)
    system_messages = basic_conversation.get_system_messages()
    assert len(system_messages) == 1
    assert system_messages[0] == system_message


def test_from_conversation(basic_conversation):
    new_conversation = OnceConversation(chat_mode="chat_advanced", user_name="user2")
    basic_conversation.from_conversation(new_conversation)
    assert basic_conversation.chat_mode == "chat_advanced"
    assert basic_conversation.user_name == "user2"


def test_get_messages_by_round(conversation_with_messages):
    # Test first round
    round1_messages = conversation_with_messages.get_messages_by_round(1)
    assert len(round1_messages) == 2
    assert round1_messages[0].content == "Hello"
    assert round1_messages[1].content == "Hi"

    # Test not existing round
    no_messages = conversation_with_messages.get_messages_by_round(3)
    assert len(no_messages) == 0


def test_get_latest_round(conversation_with_messages):
    latest_round_messages = conversation_with_messages.get_latest_round()
    assert len(latest_round_messages) == 2
    assert latest_round_messages[0].content == "How are you?"
    assert latest_round_messages[1].content == "I'm good, thanks"


def test_get_messages_with_round(conversation_with_messages):
    # Test last round
    last_round_messages = conversation_with_messages.get_messages_with_round(1)
    assert len(last_round_messages) == 2
    assert last_round_messages[0].content == "How are you?"
    assert last_round_messages[1].content == "I'm good, thanks"

    # Test last two rounds
    last_two_rounds_messages = conversation_with_messages.get_messages_with_round(2)
    assert len(last_two_rounds_messages) == 4
    assert last_two_rounds_messages[0].content == "Hello"
    assert last_two_rounds_messages[1].content == "Hi"


def test_get_model_messages(conversation_with_messages):
    model_messages = conversation_with_messages.get_model_messages()
    assert len(model_messages) == 4
    assert all(isinstance(msg, ModelMessage) for msg in model_messages)
    assert model_messages[0].content == "Hello"
    assert model_messages[1].content == "Hi"
    assert model_messages[2].content == "How are you?"
    assert model_messages[3].content == "I'm good, thanks"


def test_conversation_identifier(conversation_identifier):
    assert conversation_identifier.conv_uid == "conv1"
    assert conversation_identifier.identifier_type == "conversation"
    assert conversation_identifier.str_identifier == "conversation:conv1"
    assert conversation_identifier.to_dict() == {
        "conv_uid": "conv1",
        "identifier_type": "conversation",
    }


def test_message_identifier(message_identifier):
    assert message_identifier.conv_uid == "conv1"
    assert message_identifier.index == 1
    assert message_identifier.identifier_type == "message"
    assert message_identifier.str_identifier == "message___conv1___1"
    assert message_identifier.to_dict() == {
        "conv_uid": "conv1",
        "index": 1,
        "identifier_type": "message",
    }


def test_message_storage_item(message_storage_item):
    assert message_storage_item.conv_uid == "conv1"
    assert message_storage_item.index == 1
    assert message_storage_item.message_detail == {
        "type": "human",
        "data": {
            "content": "Hello",
            "index": 1,
            "round_index": 0,
            "additional_kwargs": {},
            "example": False,
        },
        "index": 1,
        "round_index": 0,
    }

    assert isinstance(message_storage_item.identifier, MessageIdentifier)
    assert message_storage_item.to_dict() == {
        "conv_uid": "conv1",
        "index": 1,
        "message_detail": {
            "type": "human",
            "index": 1,
            "data": {
                "content": "Hello",
                "index": 1,
                "round_index": 0,
                "additional_kwargs": {},
                "example": False,
            },
            "round_index": 0,
        },
    }

    assert isinstance(message_storage_item.to_message(), BaseMessage)


def test_storage_conversation_init(storage_conversation):
    assert storage_conversation.conv_uid == "conv1"
    assert storage_conversation.chat_mode == "chat_normal"
    assert storage_conversation.user_name == "user1"


def test_storage_conversation_add_user_message(storage_conversation):
    storage_conversation.add_user_message("Hi")
    assert len(storage_conversation.messages) == 1
    assert isinstance(storage_conversation.messages[0], HumanMessage)


def test_storage_conversation_add_ai_message(storage_conversation):
    storage_conversation.add_ai_message("Hello")
    assert len(storage_conversation.messages) == 1
    assert isinstance(storage_conversation.messages[0], AIMessage)


def test_save_to_storage(storage_conversation, in_memory_storage):
    # Set storage
    storage_conversation.conv_storage = in_memory_storage
    storage_conversation.message_storage = in_memory_storage

    # Add messages
    storage_conversation.add_user_message("User message")
    storage_conversation.add_ai_message("AI response")

    # Save to storage
    storage_conversation.save_to_storage()

    # Create a new StorageConversation instance to load the data
    saved_conversation = StorageConversation(
        storage_conversation.conv_uid,
        conv_storage=in_memory_storage,
        message_storage=in_memory_storage,
    )

    assert saved_conversation.conv_uid == storage_conversation.conv_uid
    assert len(saved_conversation.messages) == 2
    assert isinstance(saved_conversation.messages[0], HumanMessage)
    assert isinstance(saved_conversation.messages[1], AIMessage)


def test_load_from_storage(storage_conversation, in_memory_storage):
    # Set storage
    storage_conversation.conv_storage = in_memory_storage
    storage_conversation.message_storage = in_memory_storage

    # Add messages and save to storage
    storage_conversation.add_user_message("User message")
    storage_conversation.add_ai_message("AI response")
    storage_conversation.save_to_storage()

    # Create a new StorageConversation instance to load the data
    new_conversation = StorageConversation(
        "conv1", conv_storage=in_memory_storage, message_storage=in_memory_storage
    )

    # Check if the data is loaded correctly
    assert new_conversation.conv_uid == storage_conversation.conv_uid
    assert len(new_conversation.messages) == 2
    assert new_conversation.messages[0].content == "User message"
    assert new_conversation.messages[1].content == "AI response"
    assert isinstance(new_conversation.messages[0], HumanMessage)
    assert isinstance(new_conversation.messages[1], AIMessage)
