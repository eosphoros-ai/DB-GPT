from typing import List

import pytest

from dbgpt.core.interface.message import AIMessage, BaseMessage, HumanMessage
from dbgpt.core.operators import BufferedConversationMapperOperator


@pytest.fixture
def messages() -> List[BaseMessage]:
    return [
        HumanMessage(content="Hi", round_index=1),
        AIMessage(content="Hello!", round_index=1),
        HumanMessage(content="How are you?", round_index=2),
        AIMessage(content="I'm good, thanks!", round_index=2),
        HumanMessage(content="What's new today?", round_index=3),
        AIMessage(content="Lots of things!", round_index=3),
    ]


@pytest.mark.asyncio
async def test_buffered_conversation_keep_start_rounds(messages: List[BaseMessage]):
    # Test keep_start_rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=2,
        keep_end_rounds=None,
    )
    assert await operator.map_messages(messages) == [
        HumanMessage(content="Hi", round_index=1),
        AIMessage(content="Hello!", round_index=1),
        HumanMessage(content="How are you?", round_index=2),
        AIMessage(content="I'm good, thanks!", round_index=2),
    ]
    # Test keep start 0 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=0,
        keep_end_rounds=None,
    )
    assert await operator.map_messages(messages) == []

    # Test keep start 100 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=100,
        keep_end_rounds=None,
    )
    assert await operator.map_messages(messages) == messages

    # Test keep start -1 rounds
    with pytest.raises(ValueError):
        operator = BufferedConversationMapperOperator(
            keep_start_rounds=-1,
            keep_end_rounds=None,
        )
        await operator.map_messages(messages)


@pytest.mark.asyncio
async def test_buffered_conversation_keep_end_rounds(messages: List[BaseMessage]):
    # Test keep_end_rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=None,
        keep_end_rounds=2,
    )
    assert await operator.map_messages(messages) == [
        HumanMessage(content="How are you?", round_index=2),
        AIMessage(content="I'm good, thanks!", round_index=2),
        HumanMessage(content="What's new today?", round_index=3),
        AIMessage(content="Lots of things!", round_index=3),
    ]
    # Test keep end 0 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=0,
        keep_end_rounds=0,
    )
    assert await operator.map_messages(messages) == []

    # Test keep end 100 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=None,
        keep_end_rounds=100,
    )
    assert await operator.map_messages(messages) == messages

    # Test keep end -1 rounds
    with pytest.raises(ValueError):
        operator = BufferedConversationMapperOperator(
            keep_start_rounds=None,
            keep_end_rounds=-1,
        )
        await operator.map_messages(messages)


@pytest.mark.asyncio
async def test_buffered_conversation_keep_start_end_rounds(messages: List[BaseMessage]):
    # Test keep_start_rounds and keep_end_rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=1,
        keep_end_rounds=1,
    )
    assert await operator.map_messages(messages) == [
        HumanMessage(content="Hi", round_index=1),
        AIMessage(content="Hello!", round_index=1),
        HumanMessage(content="What's new today?", round_index=3),
        AIMessage(content="Lots of things!", round_index=3),
    ]
    # Test keep start 0 rounds and keep end 0 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=0,
        keep_end_rounds=0,
    )
    assert await operator.map_messages(messages) == []

    # Test keep start 0 rounds and keep end 1 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=0,
        keep_end_rounds=1,
    )
    assert await operator.map_messages(messages) == [
        HumanMessage(content="What's new today?", round_index=3),
        AIMessage(content="Lots of things!", round_index=3),
    ]

    # Test keep start 2 rounds and keep end 0 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=2,
        keep_end_rounds=0,
    )
    assert await operator.map_messages(messages) == [
        HumanMessage(content="Hi", round_index=1),
        AIMessage(content="Hello!", round_index=1),
        HumanMessage(content="How are you?", round_index=2),
        AIMessage(content="I'm good, thanks!", round_index=2),
    ]

    # Test keep start 100 rounds and keep end 100 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=100,
        keep_end_rounds=100,
    )
    assert await operator.map_messages(messages) == messages

    # Test keep start 2 round and keep end 2 rounds
    operator = BufferedConversationMapperOperator(
        keep_start_rounds=2,
        keep_end_rounds=2,
    )
    assert await operator.map_messages(messages) == messages

    # Test keep start -1 rounds and keep end -1 rounds
    with pytest.raises(ValueError):
        operator = BufferedConversationMapperOperator(
            keep_start_rounds=-1,
            keep_end_rounds=-1,
        )
        await operator.map_messages(messages)
