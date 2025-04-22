import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ReActStep:
    """
    Dataclass representing a single step in the ReAct pattern.
    """

    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Any] = None
    observation: Optional[Any] = None
    is_terminal: bool = False


class ReActOutputParser:
    """
    Parser for ReAct format model outputs with configurable prefixes.

    This parser extracts structured information from language model outputs
    that follow the ReAct pattern: Thought -> Action -> Action Input -> Observation.
    """

    def __init__(
        self,
        thought_prefix: str = "Thought:",
        action_prefix: str = "Action:",
        action_input_prefix: str = "Action Input:",
        observation_prefix: str = "Observation:",
        terminate_action: str = "terminate",
    ):
        """
        Initialize the ReAct output parser with configurable prefixes.

        Args:
            thought_prefix: Prefix string that indicates the start of a thought.
            action_prefix: Prefix string that indicates the start of an action.
            action_input_prefix: Prefix string that indicates the start of action input.
            observation_prefix: Prefix string that indicates the start of an
                observation.
            terminate_action: String that indicates termination action.
        """
        self.thought_prefix = thought_prefix
        self.action_prefix = action_prefix
        self.action_input_prefix = action_input_prefix
        self.observation_prefix = observation_prefix
        self.terminate_action = terminate_action

        # Escape special regex characters in prefixes
        self.thought_prefix_escaped = re.escape(thought_prefix)
        self.action_prefix_escaped = re.escape(action_prefix)
        self.action_input_prefix_escaped = re.escape(action_input_prefix)
        self.observation_prefix_escaped = re.escape(observation_prefix)

    def parse(self, text: str) -> List[ReActStep]:
        """
        Parse the ReAct format output text into structured steps.

        Args:
            text: The text to parse, containing ReAct formatted content.

        Returns:
            List of ReActStep dataclasses, each containing thought, action,
                action_input, and observation.
        """
        # Split the text into steps based on thought prefix
        steps = []

        # Remove any leading/trailing whitespace
        text = text.strip()

        # Find all instances of the thought prefix
        thought_matches = list(re.finditer(rf"{self.thought_prefix_escaped}\s*", text))

        if not thought_matches:
            return []

        # Process each thought section
        for i, match in enumerate(thought_matches):
            start_pos = match.start()

            # Determine end position (either next thought or end of text)
            if i < len(thought_matches) - 1:
                end_pos = thought_matches[i + 1].start()
            else:
                end_pos = len(text)

            # Extract the current step's text
            step_text = text[start_pos:end_pos].strip()

            # Parse the step
            step_data = self._parse_step(step_text)
            if step_data:
                steps.append(step_data)

        return steps

    def _parse_step(self, step_text: str) -> Optional[ReActStep]:
        """
        Parse a single step of the ReAct format.

        Args:
            step_text: Text containing a single thought-action-input-observation
                sequence.

        Returns:
            ReActStep dataclass with thought, action, action_input, and observation,
                or None if parsing fails.
        """
        # Initialize the result
        thought = None
        action = None
        action_input = None
        observation = None
        is_terminal = False

        # Extract thought
        thought_match = re.search(
            rf"{self.thought_prefix_escaped}\s*(.*?)(?={self.action_prefix_escaped}|{self.observation_prefix_escaped}|$)",
            step_text,
            re.DOTALL,
        )
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract action
        action_match = re.search(
            rf"{self.action_prefix_escaped}\s*(.*?)(?={self.action_input_prefix_escaped}|{self.observation_prefix_escaped}|$)",
            step_text,
            re.DOTALL,
        )
        if action_match:
            action = action_match.group(1).strip()

            # Check if this is a terminate action
            is_terminal = action.lower() == self.terminate_action.lower()

        # Extract action input
        action_input_match = re.search(
            rf"{self.action_input_prefix_escaped}\s*(.*?)(?={self.observation_prefix_escaped}|{self.thought_prefix_escaped}|$)",
            step_text,
            re.DOTALL,
        )
        if action_input_match:
            action_input_text = action_input_match.group(1).strip()

            # Try to parse action input as JSON if it looks like JSON
            if (
                action_input_text.startswith("{") and action_input_text.endswith("}")
            ) or (
                action_input_text.startswith("[") and action_input_text.endswith("]")
            ):
                try:
                    action_input = json.loads(action_input_text)
                except json.JSONDecodeError:
                    action_input = action_input_text
            else:
                action_input = action_input_text

        # Extract observation
        observation_match = re.search(
            rf"{self.observation_prefix_escaped}\s*(.*?)(?={self.thought_prefix_escaped}|$)",
            step_text,
            re.DOTALL,
        )
        if observation_match:
            observation_text = observation_match.group(1).strip()

            # Try to parse observation as JSON if it looks like JSON
            if (
                observation_text.startswith("{") and observation_text.endswith("}")
            ) or (observation_text.startswith("[") and observation_text.endswith("]")):
                try:
                    observation = json.loads(observation_text)
                except json.JSONDecodeError:
                    observation = observation_text
            else:
                observation = observation_text

        # Only return if we have at least thought or action
        if thought or action:
            return ReActStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                is_terminal=is_terminal,
            )
        return None

    def get_final_output(self, steps: List[ReActStep]) -> Optional[str]:
        """
        Get the final output from a terminate action if it exists.

        Args:
            steps: List of parsed steps.

        Returns:
            The final output string or None if no terminate action is found.
        """
        for step in reversed(steps):  # Look from the end
            if step.is_terminal and step.action == self.terminate_action:
                if (
                    isinstance(step.action_input, dict)
                    and "output" in step.action_input
                ):
                    return step.action_input["output"]
        return None
