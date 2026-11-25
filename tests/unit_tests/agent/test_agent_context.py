"""Unit tests for agent context classes.

Tests for AgentContext, AgentGenerateContext, AgentMessage, and AgentReviewInfo
from dbgpt.agent.core.agent module.
"""

from unittest.mock import MagicMock

import pytest

from dbgpt.agent.core.action.base import ActionOutput
from dbgpt.agent.core.agent import (
    Agent,
    AgentContext,
    AgentGenerateContext,
    AgentMessage,
    AgentReviewInfo,
)
from dbgpt.core.interface.message import ModelMessageRoleType


class TestAgentContext:
    """Test suite for AgentContext class."""

    def test_initialization_with_defaults(self):
        """Test AgentContext initialization with default values."""
        context = AgentContext(conv_id="test_conv_123")

        assert context.conv_id == "test_conv_123"
        assert context.gpts_app_code is None
        assert context.gpts_app_name is None
        assert context.language is None
        assert context.max_chat_round == 100
        assert context.max_retry_round == 10
        assert context.max_new_tokens == 1024
        assert context.temperature == 0.5
        assert context.allow_format_str_template is False
        assert context.verbose is False
        assert context.app_link_start is False
        assert context.enable_vis_message is True

    def test_initialization_with_custom_values(self):
        """Test AgentContext initialization with custom values."""
        context = AgentContext(
            conv_id="custom_conv",
            gpts_app_code="app_001",
            gpts_app_name="TestApp",
            language="zh",
            max_chat_round=50,
            max_retry_round=5,
            max_new_tokens=2048,
            temperature=0.7,
            allow_format_str_template=True,
            verbose=True,
            app_link_start=True,
            enable_vis_message=False,
        )

        assert context.conv_id == "custom_conv"
        assert context.gpts_app_code == "app_001"
        assert context.gpts_app_name == "TestApp"
        assert context.language == "zh"
        assert context.max_chat_round == 50
        assert context.max_retry_round == 5
        assert context.max_new_tokens == 2048
        assert context.temperature == 0.7
        assert context.allow_format_str_template is True
        assert context.verbose is True
        assert context.app_link_start is True
        assert context.enable_vis_message is False

    def test_to_dict(self):
        """Test AgentContext.to_dict() method."""
        context = AgentContext(
            conv_id="test_conv",
            gpts_app_code="app_001",
            language="en",
            max_chat_round=50,
        )

        result = context.to_dict()

        assert isinstance(result, dict)
        assert result["conv_id"] == "test_conv"
        assert result["gpts_app_code"] == "app_001"
        assert result["language"] == "en"
        assert result["max_chat_round"] == 50
        assert "max_retry_round" in result
        assert "temperature" in result


class TestAgentGenerateContext:
    """Test suite for AgentGenerateContext class."""

    def test_initialization_with_minimal_values(self):
        """Test AgentGenerateContext with minimal required values."""
        mock_agent = MagicMock(spec=Agent)
        mock_message = AgentMessage(content="test message")

        context = AgentGenerateContext(message=mock_message, sender=mock_agent)

        assert context.message == mock_message
        assert context.sender == mock_agent
        assert context.reviewer is None
        assert context.silent is False
        assert context.already_failed is False
        assert context.last_speaker is None
        assert context.already_started is False
        assert context.begin_agent is None
        assert context.rely_messages == []
        assert context.final is True
        assert context.memory is None
        assert context.agent_context is None
        assert context.llm_client is None
        assert context.round_index is None

    def test_initialization_with_full_values(self):
        """Test AgentGenerateContext with all values."""
        mock_sender = MagicMock(spec=Agent)
        mock_reviewer = MagicMock(spec=Agent)
        mock_last_speaker = MagicMock(spec=Agent)
        mock_message = AgentMessage(content="test message")
        rely_msg1 = AgentMessage(content="rely message 1")
        rely_msg2 = AgentMessage(content="rely message 2")
        mock_agent_context = AgentContext(conv_id="test_conv")

        context = AgentGenerateContext(
            message=mock_message,
            sender=mock_sender,
            reviewer=mock_reviewer,
            silent=True,
            already_failed=True,
            last_speaker=mock_last_speaker,
            already_started=True,
            begin_agent="begin_agent_name",
            rely_messages=[rely_msg1, rely_msg2],
            final=False,
            agent_context=mock_agent_context,
            round_index=5,
        )

        assert context.message == mock_message
        assert context.sender == mock_sender
        assert context.reviewer == mock_reviewer
        assert context.silent is True
        assert context.already_failed is True
        assert context.last_speaker == mock_last_speaker
        assert context.already_started is True
        assert context.begin_agent == "begin_agent_name"
        assert len(context.rely_messages) == 2
        assert context.rely_messages[0] == rely_msg1
        assert context.rely_messages[1] == rely_msg2
        assert context.final is False
        assert context.agent_context == mock_agent_context
        assert context.round_index == 5

    def test_rely_messages_handling(self):
        """Test AgentGenerateContext handling of rely_messages."""
        mock_agent = MagicMock(spec=Agent)
        mock_message = AgentMessage(content="main message")
        rely_msg1 = AgentMessage(content="rely 1", role=ModelMessageRoleType.HUMAN)
        rely_msg2 = AgentMessage(content="rely 2", role=ModelMessageRoleType.AI)

        context = AgentGenerateContext(
            message=mock_message,
            sender=mock_agent,
            rely_messages=[rely_msg1, rely_msg2],
        )

        assert len(context.rely_messages) == 2
        assert context.rely_messages[0].content == "rely 1"
        assert context.rely_messages[1].content == "rely 2"

    def test_already_failed_flag(self):
        """Test AgentGenerateContext already_failed flag."""
        mock_agent = MagicMock(spec=Agent)
        mock_message = AgentMessage(content="test")

        # Test with already_failed=False (default)
        context1 = AgentGenerateContext(message=mock_message, sender=mock_agent)
        assert context1.already_failed is False

        # Test with already_failed=True
        context2 = AgentGenerateContext(
            message=mock_message, sender=mock_agent, already_failed=True
        )
        assert context2.already_failed is True

    def test_to_dict(self):
        """Test AgentGenerateContext.to_dict() method."""
        mock_agent = MagicMock(spec=Agent)
        mock_message = AgentMessage(content="test message")
        mock_agent_context = AgentContext(conv_id="test_conv")

        context = AgentGenerateContext(
            message=mock_message,
            sender=mock_agent,
            agent_context=mock_agent_context,
            round_index=3,
        )

        result = context.to_dict()

        assert isinstance(result, dict)
        assert "message" in result
        assert "sender" in result
        assert "agent_context" in result
        assert "round_index" in result
        assert result["round_index"] == 3


class TestAgentMessage:
    """Test suite for AgentMessage class."""

    def test_initialization_with_defaults(self):
        """Test AgentMessage initialization with default values."""
        message = AgentMessage()

        assert message.content is None
        assert message.name is None
        assert message.rounds == 0
        assert message.context is None
        assert message.action_report is None
        assert message.review_info is None
        assert message.current_goal is None
        assert message.model_name is None
        assert message.role is None
        assert message.success is True
        assert message.resource_info is None

    def test_initialization_with_custom_values(self):
        """Test AgentMessage initialization with custom values."""
        action_report = ActionOutput(content="Action result", is_exe_success=True)
        review_info = AgentReviewInfo(approve=True, comments="Looks good")

        message = AgentMessage(
            content="Test content",
            name="TestAgent",
            rounds=3,
            context={"key": "value"},
            action_report=action_report,
            review_info=review_info,
            current_goal="Test goal",
            model_name="gpt-4",
            role=ModelMessageRoleType.AI,
            success=False,
            resource_info={"resource": "data"},
        )

        assert message.content == "Test content"
        assert message.name == "TestAgent"
        assert message.rounds == 3
        assert message.context == {"key": "value"}
        assert message.action_report == action_report
        assert message.review_info == review_info
        assert message.current_goal == "Test goal"
        assert message.model_name == "gpt-4"
        assert message.role == ModelMessageRoleType.AI
        assert message.success is False
        assert message.resource_info == {"resource": "data"}

    def test_copy(self):
        """Test AgentMessage.copy() method."""
        action_report = ActionOutput(content="Action result")
        review_info = AgentReviewInfo(approve=True, comments="Good")
        original = AgentMessage(
            content="Original content",
            name="Agent1",
            rounds=2,
            context={"key": "value"},
            action_report=action_report,
            review_info=review_info,
            current_goal="Goal",
            model_name="gpt-3.5",
            role=ModelMessageRoleType.HUMAN,
            success=True,
            resource_info={"res": "info"},
        )

        copied = original.copy()

        # Check that values are copied
        assert copied.content == original.content
        assert copied.name == original.name
        assert copied.rounds == original.rounds
        assert copied.current_goal == original.current_goal
        assert copied.model_name == original.model_name
        assert copied.role == original.role
        assert copied.success == original.success
        assert copied.action_report == original.action_report
        assert copied.resource_info == original.resource_info

        # Check that context is deep copied (for dict)
        assert copied.context == original.context
        assert copied.context is not original.context  # Different objects

        # Check review_info is copied
        assert copied.review_info.approve == original.review_info.approve
        assert copied.review_info.comments == original.review_info.comments

    def test_copy_with_string_context(self):
        """Test AgentMessage.copy() with string context."""
        original = AgentMessage(content="Test", context="string context")
        copied = original.copy()

        assert copied.context == original.context
        # String context is immutable, so it's the same object
        assert copied.context is original.context

    def test_to_dict(self):
        """Test AgentMessage.to_dict() method."""
        action_report = ActionOutput(
            content="Action result", is_exe_success=True, view="chart"
        )
        message = AgentMessage(
            content="Test content",
            name="Agent1",
            rounds=2,
            action_report=action_report,
            role=ModelMessageRoleType.AI,
        )

        result = message.to_dict()

        assert isinstance(result, dict)
        assert result["content"] == "Test content"
        assert result["name"] == "Agent1"
        assert result["rounds"] == 2
        assert result["role"] == ModelMessageRoleType.AI
        assert "action_report" in result
        assert isinstance(result["action_report"], dict)
        assert result["action_report"]["content"] == "Action result"
        assert result["action_report"]["is_exe_success"] is True

    def test_to_dict_without_action_report(self):
        """Test AgentMessage.to_dict() without action_report."""
        message = AgentMessage(content="Simple message", rounds=1)
        result = message.to_dict()

        assert result["content"] == "Simple message"
        assert result["rounds"] == 1
        assert result["action_report"] is None

    def test_to_llm_message(self):
        """Test AgentMessage.to_llm_message() method."""
        message = AgentMessage(
            content="Test content",
            context={"key": "value"},
            role=ModelMessageRoleType.HUMAN,
            name="Agent1",
            rounds=5,
        )

        result = message.to_llm_message()

        assert isinstance(result, dict)
        assert result["content"] == "Test content"
        assert result["context"] == {"key": "value"}
        assert result["role"] == ModelMessageRoleType.HUMAN
        # to_llm_message only returns content, context, and role
        assert "name" not in result
        assert "rounds" not in result

    def test_from_llm_message(self):
        """Test AgentMessage.from_llm_message() factory method."""
        llm_msg = {
            "content": "Test content",
            "context": {"key": "value"},
            "role": ModelMessageRoleType.AI,
            "rounds": 3,
        }

        message = AgentMessage.from_llm_message(llm_msg)

        assert message.content == "Test content"
        assert message.context == {"key": "value"}
        assert message.role == ModelMessageRoleType.AI
        assert message.rounds == 3

    def test_from_llm_message_with_missing_fields(self):
        """Test AgentMessage.from_llm_message() with missing fields."""
        llm_msg = {"content": "Just content"}

        message = AgentMessage.from_llm_message(llm_msg)

        assert message.content == "Just content"
        assert message.context is None
        assert message.role is None
        assert message.rounds == 0  # Default value

    def test_from_messages(self):
        """Test AgentMessage.from_messages() factory method."""
        messages_data = [
            {
                "content": "Message 1",
                "role": ModelMessageRoleType.HUMAN,
                "rounds": 1,
                "name": "User",
            },
            {
                "content": "Message 2",
                "role": ModelMessageRoleType.AI,
                "rounds": 2,
                "name": "Agent",
                "success": False,
            },
            {"content": "Message 3"},
        ]

        messages = AgentMessage.from_messages(messages_data)

        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[0].role == ModelMessageRoleType.HUMAN
        assert messages[0].rounds == 1
        assert messages[0].name == "User"
        assert messages[1].content == "Message 2"
        assert messages[1].role == ModelMessageRoleType.AI
        assert messages[1].success is False
        assert messages[2].content == "Message 3"

    def test_from_messages_filters_unknown_fields(self):
        """Test that from_messages filters out unknown fields."""
        messages_data = [
            {
                "content": "Message 1",
                "unknown_field": "should be ignored",
                "another_unknown": 123,
            }
        ]

        messages = AgentMessage.from_messages(messages_data)

        assert len(messages) == 1
        assert messages[0].content == "Message 1"
        # Unknown fields should not cause errors

    def test_action_report_serialization(self):
        """Test action_report is properly serialized in to_dict()."""
        action_report = ActionOutput(
            content="Action completed",
            is_exe_success=True,
            thoughts="I thought about it",
            observations="I observed this",
            next_speakers=["Agent2", "Agent3"],
        )
        message = AgentMessage(content="Test", action_report=action_report)

        result = message.to_dict()

        assert isinstance(result["action_report"], dict)
        assert result["action_report"]["content"] == "Action completed"
        assert result["action_report"]["is_exe_success"] is True
        assert result["action_report"]["thoughts"] == "I thought about it"
        assert result["action_report"]["observations"] == "I observed this"
        assert result["action_report"]["next_speakers"] == ["Agent2", "Agent3"]

    def test_context_deep_copy_dict(self):
        """Test that dict context is deep copied."""
        original_context = {"key": "value", "nested": {"inner": "data"}}
        original = AgentMessage(content="Test", context=original_context)

        copied = original.copy()

        # Modify the copied context
        copied.context["key"] = "modified"
        copied.context["nested"]["inner"] = "modified_data"

        # Original should not be affected
        assert original.context["key"] == "value"
        assert original.context["nested"]["inner"] == "data"

    def test_get_dict_context(self):
        """Test AgentMessage.get_dict_context() method."""
        # Test with dict context
        message1 = AgentMessage(content="Test", context={"key": "value"})
        result1 = message1.get_dict_context()
        assert result1 == {"key": "value"}

        # Test with string context
        message2 = AgentMessage(content="Test", context="string context")
        result2 = message2.get_dict_context()
        assert result2 == {}

        # Test with None context
        message3 = AgentMessage(content="Test", context=None)
        result3 = message3.get_dict_context()
        assert result3 == {}


class TestAgentReviewInfo:
    """Test suite for AgentReviewInfo class."""

    def test_initialization_with_defaults(self):
        """Test AgentReviewInfo initialization with default values."""
        review = AgentReviewInfo()

        assert review.approve is False
        assert review.comments is None

    def test_initialization_with_custom_values(self):
        """Test AgentReviewInfo initialization with custom values."""
        review = AgentReviewInfo(approve=True, comments="Excellent work!")

        assert review.approve is True
        assert review.comments == "Excellent work!"

    def test_copy(self):
        """Test AgentReviewInfo.copy() method."""
        original = AgentReviewInfo(approve=True, comments="Good job")
        copied = original.copy()

        assert copied.approve == original.approve
        assert copied.comments == original.comments

        # Modify copied
        copied.approve = False
        copied.comments = "Needs improvement"

        # Original should not be affected
        assert original.approve is True
        assert original.comments == "Good job"

    def test_to_dict(self):
        """Test AgentReviewInfo.to_dict() method."""
        review = AgentReviewInfo(approve=True, comments="Looks good")
        result = review.to_dict()

        assert isinstance(result, dict)
        assert result["approve"] is True
        assert result["comments"] == "Looks good"

    def test_to_dict_with_defaults(self):
        """Test AgentReviewInfo.to_dict() with default values."""
        review = AgentReviewInfo()
        result = review.to_dict()

        assert isinstance(result, dict)
        assert result["approve"] is False
        assert result["comments"] is None


@pytest.mark.parametrize(
    "conv_id,max_chat_round,temperature",
    [
        ("conv_1", 50, 0.5),
        ("conv_2", 100, 0.7),
        ("conv_3", 200, 0.3),
    ],
)
def test_agent_context_parametrized(conv_id, max_chat_round, temperature):
    """Parametrized test for AgentContext with different values."""
    context = AgentContext(
        conv_id=conv_id, max_chat_round=max_chat_round, temperature=temperature
    )

    assert context.conv_id == conv_id
    assert context.max_chat_round == max_chat_round
    assert context.temperature == temperature


@pytest.mark.parametrize(
    "content,rounds,success",
    [
        ("Message 1", 1, True),
        ("Message 2", 5, False),
        ("Message 3", 10, True),
    ],
)
def test_agent_message_parametrized(content, rounds, success):
    """Parametrized test for AgentMessage with different values."""
    message = AgentMessage(content=content, rounds=rounds, success=success)

    assert message.content == content
    assert message.rounds == rounds
    assert message.success == success
