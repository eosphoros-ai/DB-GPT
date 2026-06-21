"""Unit tests for AWEL agent operators.

Tests for AWELAgentOperator, WrappedAgentOperator, and AgentBranchOperator
from dbgpt.agent.core.plan.awel.agent_operator module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dbgpt.agent.core.action.base import ActionOutput
from dbgpt.agent.core.agent import (
    Agent,
    AgentContext,
    AgentGenerateContext,
    AgentMessage,
)
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.core.memory.agent_memory import AgentMemory
from dbgpt.agent.core.plan.awel.agent_operator import (
    AgentBranchOperator,
    AWELAgentOperator,
    WrappedAgentOperator,
)
from dbgpt.agent.core.plan.awel.agent_operator_resource import AWELAgent
from dbgpt.core.interface.message import ModelMessageRoleType


@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = MagicMock(spec=Agent)
    agent.name = "TestAgent"
    agent.role = "test_role"
    agent.send = AsyncMock()
    agent.generate_reply = AsyncMock()
    return agent


@pytest.fixture
def mock_conversable_agent():
    """Create a mock ConversableAgent instance."""
    agent = MagicMock(spec=ConversableAgent)
    agent.name = "TestConversableAgent"
    agent.role = "conversable_role"
    agent.fixed_subgoal = None
    agent.send = AsyncMock()
    agent.generate_reply = AsyncMock()
    return agent


@pytest.fixture
def mock_agent_memory():
    """Create a mock AgentMemory instance."""
    memory = MagicMock(spec=AgentMemory)
    memory.structure_clone = MagicMock(return_value=memory)
    return memory


@pytest.fixture
def sample_agent_context():
    """Create a sample AgentContext."""
    return AgentContext(conv_id="test_conv", max_chat_round=10, temperature=0.5)


@pytest.fixture
def sample_message():
    """Create a sample AgentMessage."""
    return AgentMessage(content="Test message content", rounds=0, success=True)


@pytest.fixture
def sample_generate_context(mock_agent, sample_message, sample_agent_context):
    """Create a sample AgentGenerateContext."""
    return AgentGenerateContext(
        message=sample_message,
        sender=mock_agent,
        reviewer=None,
        silent=False,
        already_failed=False,
        rely_messages=[],
        agent_context=sample_agent_context,
        llm_client=None,
    )


@pytest.fixture
def mock_awel_agent():
    """Create a mock AWELAgent instance."""
    awel_agent = MagicMock(spec=AWELAgent)
    awel_agent.agent_profile = "TestAgentProfile"
    awel_agent.role_name = "TestRole"
    awel_agent.llm_config = None
    awel_agent.fixed_subgoal = None
    awel_agent.agent_prompt = None
    awel_agent.resources = []
    return awel_agent


class TestWrappedAgentOperator:
    """Test suite for WrappedAgentOperator class."""

    @pytest.mark.asyncio
    async def test_map_basic_execution(self, mock_agent, sample_message):
        """Test WrappedAgentOperator.map() with basic execution flow."""
        # Setup
        operator = WrappedAgentOperator(agent=mock_agent)
        rely_msg = AgentMessage(
            content="Previous message", role=ModelMessageRoleType.HUMAN
        )
        input_context = AgentGenerateContext(
            message=sample_message,
            sender=mock_agent,
            rely_messages=[rely_msg],
        )

        # Mock the agent's generate_reply to return a successful message
        reply_message = AgentMessage(
            content="Agent reply", success=True, role=ModelMessageRoleType.AI
        )
        mock_agent.generate_reply.return_value = reply_message

        # Execute
        result = await operator.map(input_context)

        # Verify
        assert isinstance(result, AgentGenerateContext)
        assert result.sender == mock_agent  # Sender is now the agent
        assert len(result.rely_messages) == 2  # Human message + AI reply
        assert result.rely_messages[0].role == ModelMessageRoleType.HUMAN
        assert result.rely_messages[1].role == ModelMessageRoleType.AI
        assert result.already_started is True
        assert result.last_speaker == mock_agent

        # Verify agent.send was called
        mock_agent.send.assert_called_once()

        # Verify agent.generate_reply was called
        mock_agent.generate_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_empty_message_raises_exception(self, mock_agent):
        """Test WrappedAgentOperator.map() raises ValueError when message is empty."""
        operator = WrappedAgentOperator(agent=mock_agent)
        input_context = AgentGenerateContext(message=None, sender=mock_agent)

        with pytest.raises(ValueError, match="The message is empty"):
            await operator.map(input_context)

    @pytest.mark.asyncio
    async def test_map_empty_sender_raises_exception(self, mock_agent, sample_message):
        """Test WrappedAgentOperator.map() raises ValueError when sender is empty."""
        operator = WrappedAgentOperator(agent=mock_agent)
        input_context = AgentGenerateContext(message=sample_message, sender=None)

        with pytest.raises(ValueError, match="The sender is empty"):
            await operator.map(input_context)

    @pytest.mark.asyncio
    async def test_map_unsuccessful_reply_raises_exception(
        self, mock_agent, sample_message
    ):
        """Test WrappedAgentOperator.map() raises exception on unsuccessful reply."""
        operator = WrappedAgentOperator(agent=mock_agent)
        input_context = AgentGenerateContext(message=sample_message, sender=mock_agent)

        # Mock the agent's generate_reply to return an unsuccessful message
        reply_message = AgentMessage(
            content="Failed to complete task",
            success=False,
            role=ModelMessageRoleType.AI,
        )
        mock_agent.generate_reply.return_value = reply_message

        with pytest.raises(
            ValueError,
            match="The task failed at step test_role and the attempt to repair it",
        ):
            await operator.map(input_context)

    @pytest.mark.asyncio
    async def test_map_with_memory(self, mock_agent, sample_message, mock_agent_memory):
        """Test WrappedAgentOperator.map() with memory handling."""
        operator = WrappedAgentOperator(agent=mock_agent)
        input_context = AgentGenerateContext(
            message=sample_message, sender=mock_agent, memory=mock_agent_memory
        )

        reply_message = AgentMessage(content="Reply", success=True)
        mock_agent.generate_reply.return_value = reply_message

        result = await operator.map(input_context)

        # Verify memory is cloned
        mock_agent_memory.structure_clone.assert_called_once()
        assert result.memory is not None

    @pytest.mark.asyncio
    async def test_map_current_goal_construction(self, mock_agent, sample_message):
        """Test WrappedAgentOperator.map() constructs current_goal correctly."""
        operator = WrappedAgentOperator(agent=mock_agent)
        input_context = AgentGenerateContext(message=sample_message, sender=mock_agent)

        reply_message = AgentMessage(content="Reply", success=True)
        mock_agent.generate_reply.return_value = reply_message

        await operator.map(input_context)

        # Verify the message passed to generate_reply has current_goal set
        call_args = mock_agent.generate_reply.call_args
        received_message = call_args.kwargs["received_message"]
        assert received_message.current_goal is not None
        assert received_message.current_goal.startswith("[TestAgent]:")


class TestAWELAgentOperator:
    """Test suite for AWELAgentOperator class."""

    @pytest.mark.asyncio
    async def test_map_returns_early_if_already_failed(
        self, mock_awel_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() returns early when already_failed is True."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)
        sample_generate_context.already_failed = True

        result = await operator.map(sample_generate_context)

        assert result == sample_generate_context
        assert result.already_failed is True

    @pytest.mark.asyncio
    async def test_map_empty_message_raises_exception(
        self, mock_awel_agent, mock_agent, sample_agent_context
    ):
        """Test AWELAgentOperator.map() raises ValueError when message is empty."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)
        input_context = AgentGenerateContext(
            message=None, sender=mock_agent, agent_context=sample_agent_context
        )

        with pytest.raises(ValueError, match="The message is empty"):
            await operator.map(input_context)

    @pytest.mark.asyncio
    async def test_map_empty_sender_raises_exception(
        self, mock_awel_agent, sample_message, sample_agent_context
    ):
        """Test AWELAgentOperator.map() raises ValueError when sender is empty."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)
        input_context = AgentGenerateContext(
            message=sample_message, sender=None, agent_context=sample_agent_context
        )

        # Need to mock get_agent to avoid issues
        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = MagicMock(spec=ConversableAgent)

            with pytest.raises(ValueError, match="The sender is empty"):
                await operator.map(input_context)

    @pytest.mark.asyncio
    async def test_map_normal_execution(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() normal execution flow."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        # Mock get_agent to return our conversable agent
        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            # Mock agent's generate_reply
            reply_message = AgentMessage(
                content="Agent response", success=True, role=ModelMessageRoleType.AI
            )
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(sample_generate_context)

            # Verify
            assert isinstance(result, AgentGenerateContext)
            assert result.sender == mock_conversable_agent
            assert len(result.rely_messages) == 2  # HUMAN + AI messages
            assert result.rely_messages[0].role == ModelMessageRoleType.HUMAN
            assert result.rely_messages[1].role == ModelMessageRoleType.AI
            assert result.already_started is True
            assert result.already_failed is False
            assert result.last_speaker == mock_conversable_agent

    @pytest.mark.asyncio
    async def test_map_with_fixed_subgoal(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() with fixed_subgoal."""
        mock_conversable_agent.fixed_subgoal = "Fixed goal for testing"
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            await operator.map(sample_generate_context)

            # Verify that fixed_subgoal overrides message content
            call_args = mock_conversable_agent.generate_reply.call_args
            received_message = call_args.kwargs["received_message"]
            assert received_message.content == "Fixed goal for testing"
            assert "Fixed goal for testing" in received_message.current_goal

    @pytest.mark.asyncio
    async def test_map_without_fixed_subgoal(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() without fixed_subgoal."""
        mock_conversable_agent.fixed_subgoal = None
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            await operator.map(sample_generate_context)

            # Verify that message content is used
            call_args = mock_conversable_agent.generate_reply.call_args
            received_message = call_args.kwargs["received_message"]
            assert received_message.content == "Test message content"

    @pytest.mark.asyncio
    async def test_map_failure_sets_already_failed(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() sets already_failed on unsuccessful reply."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            # Mock agent's generate_reply to return unsuccessful message
            reply_message = AgentMessage(
                content="Failed", success=False, role=ModelMessageRoleType.AI
            )
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(sample_generate_context)

            # Verify already_failed is set to True
            assert result.already_failed is True

    @pytest.mark.asyncio
    async def test_map_increments_rounds(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() increments message rounds."""
        sample_generate_context.message.rounds = 5
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            await operator.map(sample_generate_context)

            # Verify rounds are incremented
            call_args = mock_conversable_agent.generate_reply.call_args
            received_message = call_args.kwargs["received_message"]
            assert received_message.rounds == 6

    @pytest.mark.asyncio
    async def test_map_with_begin_agent_not_started(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() when begin_agent is set but not started."""
        sample_generate_context.begin_agent = "other_agent"
        sample_generate_context.already_started = False
        mock_conversable_agent.role = "test_role"
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            result = await operator.map(sample_generate_context)

            # Should return early without executing
            assert result == sample_generate_context
            mock_conversable_agent.generate_reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_map_with_begin_agent_matching(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() when begin_agent matches current agent."""
        sample_generate_context.begin_agent = "conversable_role"
        sample_generate_context.already_started = False
        mock_conversable_agent.role = "conversable_role"
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(sample_generate_context)

            # Should execute and set is_retry_chat=True
            assert result.sender == mock_conversable_agent
            mock_conversable_agent.generate_reply.assert_called_once()
            call_args = mock_conversable_agent.generate_reply.call_args
            assert call_args.kwargs.get("is_retry_chat") is True

    @pytest.mark.asyncio
    async def test_map_with_memory_clone(
        self,
        mock_awel_agent,
        mock_conversable_agent,
        sample_generate_context,
        mock_agent_memory,
    ):
        """Test AWELAgentOperator.map() clones memory."""
        sample_generate_context.memory = mock_agent_memory
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(sample_generate_context)

            # Verify memory is cloned
            mock_agent_memory.structure_clone.assert_called_once()
            assert result.memory is not None

    @pytest.mark.asyncio
    async def test_map_message_role_conversion(
        self, mock_awel_agent, mock_conversable_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.map() converts message roles correctly."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)

        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent

            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(sample_generate_context)

            # Check that roles are set correctly
            assert result.rely_messages[0].role == ModelMessageRoleType.HUMAN
            assert result.rely_messages[1].role == ModelMessageRoleType.AI

    @pytest.mark.asyncio
    async def test_get_agent_builds_agent(
        self, mock_awel_agent, sample_generate_context
    ):
        """Test AWELAgentOperator.get_agent() builds agent correctly."""
        operator = AWELAgentOperator(awel_agent=mock_awel_agent)
        operator.llm_client = MagicMock()

        # Mock the agent class and its builder pattern
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock(spec=ConversableAgent)
        mock_agent_instance.role = "test_role"

        # Setup the builder chain
        mock_builder = MagicMock()
        mock_builder.bind.return_value = mock_builder
        mock_builder.build = AsyncMock(return_value=mock_agent_instance)
        mock_agent_class.return_value = mock_builder

        with patch(
            "dbgpt.agent.core.plan.awel.agent_operator.get_agent_manager"
        ) as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_by_name.return_value = mock_agent_class
            mock_get_manager.return_value = mock_manager

            with patch(
                "dbgpt.agent.core.plan.awel.agent_operator.get_resource_manager"
            ) as mock_get_resource_manager:
                mock_resource_manager = MagicMock()
                mock_resource_manager.build_resource.return_value = None
                mock_get_resource_manager.return_value = mock_resource_manager

                result = await operator.get_agent(sample_generate_context)

                assert result == mock_agent_instance
                mock_manager.get_by_name.assert_called_once_with("TestAgentProfile")


class TestAgentBranchOperator:
    """Test suite for AgentBranchOperator class."""

    @pytest.mark.asyncio
    async def test_branches_returns_branch_map(self):
        """Test AgentBranchOperator.branches() returns correct branch map."""
        operator = AgentBranchOperator()

        # Create mock downstream AWELAgentOperator nodes
        mock_awel_agent1 = MagicMock(spec=AWELAgent)
        mock_awel_agent1.agent_profile = "Agent1"

        mock_awel_agent2 = MagicMock(spec=AWELAgent)
        mock_awel_agent2.agent_profile = "Agent2"

        mock_operator1 = MagicMock(spec=AWELAgentOperator)
        mock_operator1.awel_agent = mock_awel_agent1
        mock_operator1.node_name = "node1"

        mock_operator2 = MagicMock(spec=AWELAgentOperator)
        mock_operator2.awel_agent = mock_awel_agent2
        mock_operator2.node_name = "node2"

        # Mock downstream attribute
        operator.downstream = [mock_operator1, mock_operator2]

        result = await operator.branches()

        assert isinstance(result, dict)
        assert len(result) == 2

        # The keys should be functions and values should be node names
        list(result.keys())
        branch_targets = list(result.values())
        assert branch_targets == ["node1", "node2"]

    @pytest.mark.asyncio
    async def test_branch_function_checks_next_speakers(self):
        """Test that branch functions check action_report.next_speakers."""
        operator = AgentBranchOperator()

        mock_awel_agent = MagicMock(spec=AWELAgent)
        mock_awel_agent.agent_profile = "TargetAgent"

        mock_operator = MagicMock(spec=AWELAgentOperator)
        mock_operator.awel_agent = mock_awel_agent
        mock_operator.node_name = "target_node"

        operator.downstream = [mock_operator]

        branch_map = await operator.branches()
        branch_func = list(branch_map.keys())[0]

        # Test with matching next_speakers
        action_output = ActionOutput(
            content="Test", next_speakers=["TargetAgent", "OtherAgent"]
        )
        last_message = AgentMessage(content="Test", action_report=action_output)
        context = AgentGenerateContext(
            message=AgentMessage(content="Main"),
            sender=MagicMock(spec=Agent),
            rely_messages=[last_message],
        )

        result = branch_func(context)
        assert result is True

        # Test with non-matching next_speakers
        action_output2 = ActionOutput(content="Test", next_speakers=["OtherAgent"])
        last_message2 = AgentMessage(content="Test", action_report=action_output2)
        context2 = AgentGenerateContext(
            message=AgentMessage(content="Main"),
            sender=MagicMock(spec=Agent),
            rely_messages=[last_message2],
        )

        result2 = branch_func(context2)
        assert result2 is False

    @pytest.mark.asyncio
    async def test_branch_function_returns_false_without_action_report(self):
        """Test branch function returns False when action_report is None."""
        operator = AgentBranchOperator()

        mock_awel_agent = MagicMock(spec=AWELAgent)
        mock_awel_agent.agent_profile = "TargetAgent"

        mock_operator = MagicMock(spec=AWELAgentOperator)
        mock_operator.awel_agent = mock_awel_agent
        mock_operator.node_name = "target_node"

        operator.downstream = [mock_operator]

        branch_map = await operator.branches()
        branch_func = list(branch_map.keys())[0]

        # Test without action_report
        last_message = AgentMessage(content="Test", action_report=None)
        context = AgentGenerateContext(
            message=AgentMessage(content="Main"),
            sender=MagicMock(spec=Agent),
            rely_messages=[last_message],
        )

        result = branch_func(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_branch_function_returns_false_without_next_speakers(self):
        """Test branch function returns False when next_speakers is None."""
        operator = AgentBranchOperator()

        mock_awel_agent = MagicMock(spec=AWELAgent)
        mock_awel_agent.agent_profile = "TargetAgent"

        mock_operator = MagicMock(spec=AWELAgentOperator)
        mock_operator.awel_agent = mock_awel_agent
        mock_operator.node_name = "target_node"

        operator.downstream = [mock_operator]

        branch_map = await operator.branches()
        branch_func = list(branch_map.keys())[0]

        # Test with action_report but no next_speakers
        action_output = ActionOutput(content="Test", next_speakers=None)
        last_message = AgentMessage(content="Test", action_report=action_output)
        context = AgentGenerateContext(
            message=AgentMessage(content="Main"),
            sender=MagicMock(spec=Agent),
            rely_messages=[last_message],
        )

        result = branch_func(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_branches_filters_non_awel_operators(self):
        """Test branches() filters out non-AWELAgentOperator nodes."""
        operator = AgentBranchOperator()

        mock_awel_agent = MagicMock(spec=AWELAgent)
        mock_awel_agent.agent_profile = "Agent1"

        mock_operator1 = MagicMock(spec=AWELAgentOperator)
        mock_operator1.awel_agent = mock_awel_agent
        mock_operator1.node_name = "node1"

        # Add a non-AWELAgentOperator node
        mock_other_operator = MagicMock()

        operator.downstream = [mock_operator1, mock_other_operator]

        result = await operator.branches()

        # Should only include the AWELAgentOperator
        assert len(result) == 1


@pytest.mark.parametrize(
    "already_failed,should_execute",
    [
        (True, False),  # Should return early
        (False, True),  # Should execute
    ],
)
@pytest.mark.asyncio
async def test_awel_operator_already_failed_parametrized(
    already_failed, should_execute, mock_awel_agent, mock_conversable_agent
):
    """Parametrized test for AWELAgentOperator with already_failed flag."""
    operator = AWELAgentOperator(awel_agent=mock_awel_agent)
    message = AgentMessage(content="Test", rounds=0)
    mock_sender = MagicMock(spec=Agent)

    input_context = AgentGenerateContext(
        message=message,
        sender=mock_sender,
        already_failed=already_failed,
        agent_context=AgentContext(conv_id="test"),
    )

    if should_execute:
        with patch.object(
            operator, "get_agent", new_callable=AsyncMock
        ) as mock_get_agent:
            mock_get_agent.return_value = mock_conversable_agent
            reply_message = AgentMessage(content="Response", success=True)
            mock_conversable_agent.generate_reply.return_value = reply_message

            result = await operator.map(input_context)
            assert result.sender == mock_conversable_agent
    else:
        result = await operator.map(input_context)
        assert result == input_context


@pytest.mark.parametrize(
    "success,expected_already_failed",
    [
        (True, False),
        (False, True),
    ],
)
@pytest.mark.asyncio
async def test_awel_operator_success_flag_parametrized(
    success, expected_already_failed, mock_awel_agent, mock_conversable_agent
):
    """Parametrized test for AWELAgentOperator success handling."""
    operator = AWELAgentOperator(awel_agent=mock_awel_agent)
    message = AgentMessage(content="Test", rounds=0)
    mock_sender = MagicMock(spec=Agent)

    input_context = AgentGenerateContext(
        message=message,
        sender=mock_sender,
        agent_context=AgentContext(conv_id="test"),
    )

    with patch.object(operator, "get_agent", new_callable=AsyncMock) as mock_get_agent:
        mock_get_agent.return_value = mock_conversable_agent
        reply_message = AgentMessage(content="Response", success=success)
        mock_conversable_agent.generate_reply.return_value = reply_message

        result = await operator.map(input_context)
        assert result.already_failed == expected_already_failed
