from typing import List

import pytest

from dbgpt.core.interface.message import AIMessage, HumanMessage, StorageConversation
from dbgpt.core.interface.storage import QuerySpec
from dbgpt.storage.chat_history.chat_history_db import (
    ChatHistoryEntity,
    ChatHistoryMessageEntity,
)
from dbgpt.storage.chat_history.storage_adapter import (
    DBMessageStorageItemAdapter,
    DBStorageConversationItemAdapter,
)
from dbgpt.storage.metadata import db
from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
from dbgpt.util.pagination_utils import PaginationResult
from dbgpt.util.serialization.json_serialization import JsonSerializer


@pytest.fixture
def serializer():
    return JsonSerializer()


@pytest.fixture
def db_url():
    """Use in-memory SQLite database for testing"""
    return "sqlite:///:memory:"
    # return "sqlite:///test.db"


@pytest.fixture
def db_manager(db_url):
    db.init_db(db_url)
    db.create_all()
    return db


@pytest.fixture
def storage_adapter():
    return DBStorageConversationItemAdapter()


@pytest.fixture
def storage_message_adapter():
    return DBMessageStorageItemAdapter()


@pytest.fixture
def conv_storage(db_manager, serializer, storage_adapter):
    storage = SQLAlchemyStorage(
        db_manager,
        ChatHistoryEntity,
        storage_adapter,
        serializer,
    )
    return storage


@pytest.fixture
def message_storage(db_manager, serializer, storage_message_adapter):
    storage = SQLAlchemyStorage(
        db_manager,
        ChatHistoryMessageEntity,
        storage_message_adapter,
        serializer,
    )
    return storage


@pytest.fixture
def conversation(conv_storage, message_storage):
    return StorageConversation(
        "conv1",
        chat_mode="chat_normal",
        user_name="user1",
        conv_storage=conv_storage,
        message_storage=message_storage,
    )


@pytest.fixture
def four_round_conversation(conv_storage, message_storage):
    conversation = StorageConversation(
        "conv1",
        chat_mode="chat_normal",
        user_name="user1",
        conv_storage=conv_storage,
        message_storage=message_storage,
    )
    conversation.start_new_round()
    conversation.add_user_message("hello, this is first round")
    conversation.add_ai_message("hi")
    conversation.end_current_round()
    conversation.start_new_round()
    conversation.add_user_message("hello, this is second round")
    conversation.add_ai_message("hi")
    conversation.end_current_round()
    conversation.start_new_round()
    conversation.add_user_message("hello, this is third round")
    conversation.add_ai_message("hi")
    conversation.end_current_round()
    conversation.start_new_round()
    conversation.add_user_message("hello, this is fourth round")
    conversation.add_ai_message("hi")
    conversation.end_current_round()
    return conversation


@pytest.fixture
def conversation_list(request, conv_storage, message_storage):
    params = request.param if hasattr(request, "param") else {}
    conv_count = params.get("conv_count", 4)
    result = []
    for i in range(conv_count):
        conversation = StorageConversation(
            f"conv{i}",
            chat_mode="chat_normal",
            user_name="user1",
            conv_storage=conv_storage,
            message_storage=message_storage,
        )
        conversation.start_new_round()
        conversation.add_user_message("hello, this is first round")
        conversation.add_ai_message("hi")
        conversation.end_current_round()
        conversation.start_new_round()
        conversation.add_user_message("hello, this is second round")
        conversation.add_ai_message("hi")
        conversation.end_current_round()
        conversation.start_new_round()
        conversation.add_user_message("hello, this is third round")
        conversation.add_ai_message("hi")
        conversation.end_current_round()
        conversation.start_new_round()
        conversation.add_user_message("hello, this is fourth round")
        conversation.add_ai_message("hi")
        conversation.end_current_round()
        result.append(conversation)
    return result


def test_save_and_load(
    conversation: StorageConversation, conv_storage, message_storage
):
    conversation.start_new_round()
    conversation.add_user_message("hello")
    conversation.add_ai_message("hi")
    conversation.end_current_round()

    saved_conversation = StorageConversation(
        conv_uid=conversation.conv_uid,
        conv_storage=conv_storage,
        message_storage=message_storage,
    )
    assert saved_conversation.conv_uid == conversation.conv_uid
    assert len(saved_conversation.messages) == 2
    assert isinstance(saved_conversation.messages[0], HumanMessage)
    assert isinstance(saved_conversation.messages[1], AIMessage)
    assert saved_conversation.messages[0].content == "hello"
    assert saved_conversation.messages[0].round_index == 1
    assert saved_conversation.messages[1].content == "hi"
    assert saved_conversation.messages[1].round_index == 1


def test_query_message(
    conversation: StorageConversation, conv_storage, message_storage
):
    conversation.start_new_round()
    conversation.add_user_message("hello")
    conversation.add_ai_message("hi")
    conversation.end_current_round()

    saved_conversation = StorageConversation(
        conv_uid=conversation.conv_uid,
        conv_storage=conv_storage,
        message_storage=message_storage,
    )
    assert saved_conversation.conv_uid == conversation.conv_uid
    assert len(saved_conversation.messages) == 2

    query_spec = QuerySpec(conditions={"conv_uid": conversation.conv_uid})
    results = conversation.conv_storage.query(query_spec, StorageConversation)
    assert len(results) == 1


def test_complex_query(
    conversation_list: List[StorageConversation], conv_storage, message_storage
):
    query_spec = QuerySpec(conditions={"user_name": "user1"})
    results = conv_storage.query(query_spec, StorageConversation)
    assert len(results) == len(conversation_list)
    for i, result in enumerate(results):
        assert result.user_name == "user1"
        assert result.conv_uid == f"conv{i}"
        saved_conversation = StorageConversation(
            conv_uid=result.conv_uid,
            conv_storage=conv_storage,
            message_storage=message_storage,
        )
        assert len(saved_conversation.messages) == 8
        assert isinstance(saved_conversation.messages[0], HumanMessage)
        assert isinstance(saved_conversation.messages[1], AIMessage)
        assert saved_conversation.messages[0].content == "hello, this is first round"
        assert saved_conversation.messages[1].content == "hi"


def test_query_with_page(
    conversation_list: List[StorageConversation], conv_storage, message_storage
):
    query_spec = QuerySpec(conditions={"user_name": "user1"})
    page_result: PaginationResult = conv_storage.paginate_query(
        page=1, page_size=2, cls=StorageConversation, spec=query_spec
    )
    assert page_result.total_count == len(conversation_list)
    assert page_result.total_pages == 2
    assert page_result.page_size == 2
    assert len(page_result.items) == 2
    assert page_result.items[0].conv_uid == "conv0"
