# AWEL Agent Unit Tests

This directory contains comprehensive unit tests for the DB-GPT AWEL (Agentic Workflow Expression Language) agent module.

## Test Files

### `test_agent_context.py`
Tests for agent context classes from `dbgpt.agent.core.agent`:
- **AgentContext**: Configuration and context for agent execution
  - Initialization with default and custom values
  - Dictionary serialization with `to_dict()`
- **AgentGenerateContext**: Input context for agent generation
  - Message and sender handling
  - Rely messages and message chain processing
  - Already_failed flag for error handling
  - Dictionary serialization
- **AgentMessage**: Message objects for agent communication
  - Message creation, copying, and serialization
  - Conversion to/from LLM message format
  - Action report serialization
  - Deep copy of context dictionaries
- **AgentReviewInfo**: Review information for agent messages
  - Approval and comments handling
  - Serialization methods

### `test_awel_agent_operator.py`
Tests for AWEL agent operators from `dbgpt.agent.core.plan.awel.agent_operator`:
- **AWELAgentOperator**: Main agent operator for AWEL workflows
  - Normal execution flow with message passing
  - Early return when `already_failed` is True
  - Exception handling for empty messages/senders
  - Fixed subgoal processing
  - Message role conversion (HUMAN/AI)
  - Failure scenario handling
  - Agent building and configuration
  - Memory cloning
  - Begin agent matching and retry logic
- **WrappedAgentOperator**: Agent wrapper for simple workflows
  - Basic message passing and agent reply generation
  - Empty message exception handling
  - Current goal construction
  - Memory handling
- **AgentBranchOperator**: Branch operator for agent routing
  - Branch map generation from downstream operators
  - Next speakers routing logic
  - Action report checking
  - Filtering of non-AWEL operators

## Running the Tests

### Prerequisites
The tests require the following packages to be installed:
- pytest
- pytest-asyncio
- pytest-mock
- dbgpt-core package and its dependencies

### Installation
```bash
# Install dbgpt-core package in development mode
cd packages/dbgpt-core
pip install -e .

# Or install test dependencies
pip install pytest pytest-asyncio pytest-mock
```

### Running Tests
```bash
# Run all agent tests
pytest tests/unit_tests/agent/ -v

# Run specific test file
pytest tests/unit_tests/agent/test_agent_context.py -v
pytest tests/unit_tests/agent/test_awel_agent_operator.py -v

# Run specific test class
pytest tests/unit_tests/agent/test_agent_context.py::TestAgentContext -v

# Run specific test method
pytest tests/unit_tests/agent/test_agent_context.py::TestAgentContext::test_initialization_with_defaults -v

# Run with coverage
pytest tests/unit_tests/agent/ --cov=dbgpt.agent --cov-report=html
```

## Test Coverage

The test suite covers:
- ✅ Normal execution flows
- ✅ Error handling and exceptions
- ✅ Edge cases and boundary conditions
- ✅ Message passing and transformations
- ✅ Configuration and initialization
- ✅ Serialization and deserialization
- ✅ Mock-based isolation of external dependencies

## Test Patterns

### Using Fixtures
Tests use pytest fixtures for common test data:
```python
@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = MagicMock(spec=Agent)
    agent.name = "TestAgent"
    return agent
```

### Async Testing
Async tests use the `pytest.mark.asyncio` decorator:
```python
@pytest.mark.asyncio
async def test_async_method(self, mock_agent):
    result = await operator.map(context)
    assert result is not None
```

### Parametrized Tests
Common scenarios are tested with parametrization:
```python
@pytest.mark.parametrize(
    "already_failed,should_execute",
    [(True, False), (False, True)],
)
@pytest.mark.asyncio
async def test_parametrized(already_failed, should_execute):
    # Test implementation
```

## Mocking Strategy

The tests use mocking to isolate external dependencies:
- **Agent classes**: Mocked with `MagicMock(spec=Agent)`
- **LLM clients**: Mocked to avoid actual API calls
- **Resource managers**: Mocked to avoid database/file access
- **Agent builders**: Mocked with builder pattern chains

## Contributing

When adding new tests:
1. Follow the existing test structure and naming conventions
2. Use descriptive docstrings for test methods
3. Mock external dependencies appropriately
4. Ensure tests are isolated and can run independently
5. Format code with `ruff format tests/unit_tests/agent/`
6. Check code style with `ruff check tests/unit_tests/agent/`

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [DB-GPT Agent Documentation](../../packages/dbgpt-core/src/dbgpt/agent/README.md)
