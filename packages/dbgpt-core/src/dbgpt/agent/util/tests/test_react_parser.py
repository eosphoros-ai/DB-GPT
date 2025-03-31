"""
Unit tests for the ReActOutputParser using pytest.
"""

from ..react_parser import ReActOutputParser


class TestReActOutputParser:
    """Test suite for the ReActOutputParser using pytest."""

    def test_basic_parsing(self):
        """Test basic parsing of a simple ReAct output."""
        parser = ReActOutputParser()
        text = """Thought: I should calculate 2+2.
Action: calculator
Action Input: {"operation": "add", "a": 2, "b": 2}"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I should calculate 2+2."
        assert steps[0].action == "calculator"
        assert steps[0].action_input == {"operation": "add", "a": 2, "b": 2}
        assert steps[0].observation is None
        assert steps[0].is_terminal is False

    def test_parsing_with_observation(self):
        """Test parsing with observation included."""
        parser = ReActOutputParser()
        text = """Thought: I should calculate 2+2.
Action: calculator
Action Input: {"operation": "add", "a": 2, "b": 2}
Observation: 4"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I should calculate 2+2."
        assert steps[0].action == "calculator"
        assert steps[0].action_input == {"operation": "add", "a": 2, "b": 2}
        assert steps[0].observation == "4"
        assert steps[0].is_terminal is False

    def test_terminal_action(self):
        """Test parsing of a terminal action."""
        parser = ReActOutputParser()
        text = """Thought: I've finished the calculation.
Action: terminate
Action Input: {"output": "The answer is 4"}"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I've finished the calculation."
        assert steps[0].action == "terminate"
        assert steps[0].action_input == {"output": "The answer is 4"}
        assert steps[0].is_terminal is True

        # Test get_final_output
        final_output = parser.get_final_output(steps)
        assert final_output == "The answer is 4"

    def test_multi_step_parsing(self):
        """Test parsing of multiple steps."""
        parser = ReActOutputParser()
        text = """Thought: I need to calculate 10 * 5.
Action: calculator
Action Input: {"operation": "multiply", "a": 10, "b": 5}
Observation: 50

Thought: Now I need to add 20 to the result.
Action: calculator
Action Input: {"operation": "add", "a": 50, "b": 20}
Observation: 70

Thought: The calculation is complete.
Action: terminate
Action Input: {"output": "10 * 5 + 20 = 70"}"""

        steps = parser.parse(text)

        assert len(steps) == 3

        # Check first step
        assert steps[0].thought == "I need to calculate 10 * 5."
        assert steps[0].action == "calculator"
        assert steps[0].action_input == {"operation": "multiply", "a": 10, "b": 5}
        assert steps[0].observation == "50"

        # Check second step
        assert steps[1].thought == "Now I need to add 20 to the result."
        assert steps[1].action == "calculator"
        assert steps[1].action_input == {"operation": "add", "a": 50, "b": 20}
        assert steps[1].observation == "70"

        # Check third step
        assert steps[2].thought == "The calculation is complete."
        assert steps[2].action == "terminate"
        assert steps[2].action_input == {"output": "10 * 5 + 20 = 70"}
        assert steps[2].is_terminal is True

        # Test get_final_output
        final_output = parser.get_final_output(steps)
        assert final_output == "10 * 5 + 20 = 70"

    def test_custom_prefixes(self):
        """Test parsing with custom prefixes."""
        parser = ReActOutputParser(
            thought_prefix="Think:",
            action_prefix="Do:",
            action_input_prefix="With:",
            observation_prefix="Result:",
            terminate_action="finish",
        )

        text = """Think: I should calculate 5 + 10.
Do: calculate
With: {"x": 5, "y": 10}
Result: 15

Think: Now I'm done.
Do: finish
With: {"output": "The sum is 15"}"""

        steps = parser.parse(text)

        assert len(steps) == 2

        # Check first step
        assert steps[0].thought == "I should calculate 5 + 10."
        assert steps[0].action == "calculate"
        assert steps[0].action_input == {"x": 5, "y": 10}
        assert steps[0].observation == "15"
        assert steps[0].is_terminal is False

        # Check second step
        assert steps[1].thought == "Now I'm done."
        assert steps[1].action == "finish"
        assert steps[1].action_input == {"output": "The sum is 15"}
        assert steps[1].is_terminal is True

        # Test get_final_output
        final_output = parser.get_final_output(steps)
        assert final_output == "The sum is 15"

    def test_non_json_action_input(self):
        """Test parsing of non-JSON action inputs."""
        parser = ReActOutputParser()
        text = """Thought: I'll search for information.
Action: search
Action Input: python programming language"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I'll search for information."
        assert steps[0].action == "search"
        assert steps[0].action_input == "python programming language"

    def test_non_json_observation(self):
        """Test parsing of non-JSON observations."""
        parser = ReActOutputParser()
        text = """Thought: I'll search for information.
Action: search
Action Input: {"query": "python programming language"}
Observation: Python is a high-level, general-purpose programming language."""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I'll search for information."
        assert steps[0].action == "search"
        assert steps[0].action_input == {"query": "python programming language"}
        assert (
            steps[0].observation
            == "Python is a high-level, general-purpose programming language."
        )

    def test_missing_components(self):
        """Test parsing when some components are missing."""
        parser = ReActOutputParser()

        # Missing action input
        text1 = """Thought: I'll search for information.
Action: search"""

        steps = parser.parse(text1)
        assert len(steps) == 1
        assert steps[0].thought == "I'll search for information."
        assert steps[0].action == "search"
        assert steps[0].action_input is None

        # Only thought
        text2 = """Thought: I'm thinking about what to do next."""

        steps = parser.parse(text2)
        assert len(steps) == 1
        assert steps[0].thought == "I'm thinking about what to do next."
        assert steps[0].action is None

    def test_invalid_json_handling(self):
        """Test parsing when JSON is invalid."""
        parser = ReActOutputParser()
        text = """Thought: I'll do a calculation.
Action: calculator
Action Input: {"operation": "add", "a": 2, "b": 3,}"""  # Invalid JSON (extra comma)

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I'll do a calculation."
        assert steps[0].action == "calculator"
        # Should keep as string when JSON parsing fails
        assert steps[0].action_input == """{"operation": "add", "a": 2, "b": 3,}"""

    def test_multiple_json_blocks(self):
        """Test parsing when multiple JSON objects are in the text."""
        parser = ReActOutputParser()
        text = """Thought: I need to check multiple values.
Action: check_values
Action Input: [{"name": "first", "value": 100}, {"name": "second", "value": 200}]"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I need to check multiple values."
        assert steps[0].action == "check_values"
        assert isinstance(steps[0].action_input, list)
        assert len(steps[0].action_input) == 2
        assert steps[0].action_input[0]["name"] == "first"
        assert steps[0].action_input[1]["value"] == 200

    def test_empty_input(self):
        """Test parsing with empty input."""
        parser = ReActOutputParser()
        text = ""

        steps = parser.parse(text)
        assert len(steps) == 0

    def test_no_thought_prefix(self):
        """Test parsing when there's no thought prefix."""
        parser = ReActOutputParser()
        text = """This is some text without any prefixes"""

        steps = parser.parse(text)
        assert len(steps) == 0

    def test_multiline_content(self):
        """Test parsing when content spans multiple lines."""
        parser = ReActOutputParser()
        text = """Thought: I need to analyze this data.
The data seems to have multiple entries.
I should process each one.
Action: process_data
Action Input: {
    "entries": [
        {"id": 1, "value": "first"},
        {"id": 2, "value": "second"}
    ],
    "options": {
        "sort": true,
        "filter": false
    }
}"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought.startswith("I need to analyze this data.")
        assert "multiple entries" in steps[0].thought
        assert steps[0].action == "process_data"
        assert isinstance(steps[0].action_input, dict)
        assert len(steps[0].action_input["entries"]) == 2
        assert steps[0].action_input["options"]["sort"] is True

    def test_whitespace_handling(self):
        """Test parsing with various whitespace patterns."""
        parser = ReActOutputParser()
        text = """   Thought:    I need to calculate something.   
   Action:    calculator   
   Action Input:    {"a": 1, "b": 2}   

   Observation:    3   """

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I need to calculate something."
        assert steps[0].action == "calculator"
        assert steps[0].action_input == {"a": 1, "b": 2}
        assert steps[0].observation == "3"

    def test_get_final_output_without_terminate(self):
        """Test get_final_output when there's no terminate action."""
        parser = ReActOutputParser()
        text = """Thought: I need to check the weather.
Action: weather_api
Action Input: {"location": "New York"}
Observation: Sunny, 75°F"""

        steps = parser.parse(text)

        final_output = parser.get_final_output(steps)
        assert final_output is None

    def test_custom_terminate_action(self):
        """Test with a custom terminate action."""
        parser = ReActOutputParser(terminate_action="end_task")
        text = """Thought: I'm finished with the calculation.
Action: end_task
Action Input: {"output": "The result is 42"}"""

        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].is_terminal is True

        final_output = parser.get_final_output(steps)
        assert final_output == "The result is 42"

    def test_example_in_prompt(self):
        """Test the specific example provided in the prompt."""
        parser = ReActOutputParser()
        text = """Thought: First, I need to calculate the product of 10 and 99 using \
the simple_calculator tool.
Action: simple_calculator
Action Input: {"first_number": 10, "second_number": 99, "operator": "*"}
Observation: 990
Thought: Now that I have the product, I need to count the number of files in the /tmp directory.
Action: count_directory_files
Action Input: {"path": "/tmp"}
Observation: 42
Thought: I have successfully calculated the product and counted the files in /tmp. The task is complete.
Action: terminate
Action Input: {"output": "The product of 10 and 99 is 990, and there are 42 files in /tmp."}"""  # noqa

        steps = parser.parse(text)

        assert len(steps) == 3

        # First step
        assert (
            steps[0].thought
            == "First, I need to calculate the product of 10 and 99 using the simple_calculator tool."  # noqa
        )
        assert steps[0].action == "simple_calculator"
        assert steps[0].action_input == {
            "first_number": 10,
            "second_number": 99,
            "operator": "*",
        }
        assert steps[0].observation == "990"

        # Second step
        assert (
            steps[1].thought
            == "Now that I have the product, I need to count the number of files in the /tmp directory."  # noqa
        )
        assert steps[1].action == "count_directory_files"
        assert steps[1].action_input == {"path": "/tmp"}
        assert steps[1].observation == "42"

        # Third step
        assert (
            steps[2].thought
            == "I have successfully calculated the product and counted the files in /tmp. The task is complete."  # noqa
        )
        assert steps[2].action == "terminate"
        assert steps[2].action_input == {
            "output": "The product of 10 and 99 is 990, and there are 42 files in /tmp."
        }
        assert steps[2].is_terminal is True

        # Final output
        final_output = parser.get_final_output(steps)
        assert (
            final_output
            == "The product of 10 and 99 is 990, and there are 42 files in /tmp."
        )

    def test_file_create(self):
        """Test parsing with file creation."""
        parser = ReActOutputParser()
        text = """Thought: I need to create a new file. 
Action: CreateFile
Action Input: CreateFile(filepath="hello_world.py"):
```
print("Hello, world!")
```"""
        steps = parser.parse(text)

        assert len(steps) == 1
        assert steps[0].thought == "I need to create a new file."
        assert steps[0].action == "CreateFile"
        assert (
            steps[0].action_input
            == """CreateFile(filepath="hello_world.py"):
```
print("Hello, world!")
```"""
        )
        assert steps[0].observation is None
        assert steps[0].is_terminal is False
