import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional

from dbgpt.vis.tags.vis_thinking import VisThinking


@dataclass
class ReActStep:
    """
    Dataclass representing a single step in the ReAct pattern.
    """

    thought: Optional[str] = None
    phase: Optional[str] = None
    action_intention: Optional[str] = None
    action_reason: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Any] = None
    observation: Optional[Any] = None
    is_terminal: bool = False


class ReActOutputParser:
    """
    Parser for ReAct format model outputs with configurable prefixes.
    This parser extracts structured information from language model outputs
    that follow the ReAct pattern: Thought -> Phase -> Action -> Action Input
    -> Observation.
    """

    def __init__(
        self,
        thought_prefix: str = "Thought:",
        phase_prefix: str = "Phase:",
        action_intention_prefix: str = "Action Intention:",
        action_reason_prefix: str = "Action Reason:",
        action_prefix: str = "Action:",
        action_input_prefix: str = "Action Input:",
        observation_prefix: str = "Observation:",
        terminate_action: str = "terminate",
    ):
        """
        Initialize the ReAct output parser with configurable prefixes.

        Args:
            thought_prefix: Prefix string that indicates the start of a thought.
            phase_prefix: Prefix string that indicates the start of a phase.
            action_intention_prefix: Prefix string that indicates the start of
                an action intention.
            action_reason_prefix: Prefix string that indicates the start of an
                action reason.
            action_prefix: Prefix string that indicates the start of an action.
            action_input_prefix: Prefix string that indicates the start of action input.
            observation_prefix: Prefix string that indicates the start of an
                observation.
            terminate_action: String that indicates termination action.
        """
        self.thought_prefix = thought_prefix
        self.phase_prefix = phase_prefix
        self.action_intention_prefix = action_intention_prefix
        self.action_reason_prefix = action_reason_prefix
        self.action_prefix = action_prefix
        self.action_input_prefix = action_input_prefix
        self.observation_prefix = observation_prefix
        self.terminate_action = terminate_action

        # Escape special regex characters in prefixes
        self.thought_prefix_escaped = re.escape(thought_prefix)
        self.phase_prefix_escaped = re.escape(phase_prefix)
        self.action_intention_prefix_escaped = re.escape(action_intention_prefix)
        self.action_reason_prefix_escaped = re.escape(action_reason_prefix)
        self.action_prefix_escaped = re.escape(action_prefix)
        self.action_input_prefix_escaped = re.escape(action_input_prefix)
        self.observation_prefix_escaped = re.escape(observation_prefix)

    def _prefix_line_pattern(self, escaped_prefix: str) -> str:
        """Build a regex for a ReAct prefix at the start of a logical line."""
        return rf"^[ \t]*{escaped_prefix}\s*"

    def _markdown_fence_spans(self, text: str) -> List[tuple[int, int]]:
        """Return markdown fenced-code spans so ReAct labels inside are ignored."""
        fence_pattern = re.compile(
            r"^[ \t]*(```+|~~~+)[^\n]*\n.*?^[ \t]*\1[ \t]*$",
            re.DOTALL | re.MULTILINE,
        )
        return [match.span() for match in fence_pattern.finditer(text)]

    @staticmethod
    def _is_in_spans(pos: int, spans: List[tuple[int, int]]) -> bool:
        return any(start <= pos < end for start, end in spans)

    def _find_prefix_matches(self, text: str, escaped_prefix: str) -> List[re.Match]:
        """Find line-start ReAct prefix matches outside markdown code fences."""
        pattern = re.compile(
            self._prefix_line_pattern(escaped_prefix), re.MULTILINE
        )
        fence_spans = self._markdown_fence_spans(text)
        return [
            match
            for match in pattern.finditer(text)
            if not self._is_in_spans(match.start(), fence_spans)
        ]

    def _mask_prefixes_in_fences(self, text: str) -> str:
        """Mask ReAct labels inside code fences while preserving string offsets."""
        chars = list(text)
        escaped_prefixes = (
            self.thought_prefix_escaped,
            self.phase_prefix_escaped,
            self.action_intention_prefix_escaped,
            self.action_reason_prefix_escaped,
            self.action_prefix_escaped,
            self.action_input_prefix_escaped,
            self.observation_prefix_escaped,
        )
        for start, end in self._markdown_fence_spans(text):
            fenced_text = text[start:end]
            for escaped_prefix in escaped_prefixes:
                pattern = re.compile(
                    self._prefix_line_pattern(escaped_prefix), re.MULTILINE
                )
                for match in pattern.finditer(fenced_text):
                    prefix_start = start + match.start()
                    while prefix_start < end and chars[prefix_start] in (" ", "\t"):
                        prefix_start += 1
                    if prefix_start < end:
                        chars[prefix_start] = "_"
        return "".join(chars)

    def _strip_vis_thinking_blocks(self, text: str) -> str:
        """Remove vis-thinking wrappers produced by reasoning model output."""
        fence = "`" * 6
        pattern = (
            rf"{re.escape(fence)}{re.escape(VisThinking.vis_tag())}"
            rf"\s*\n.*?\n{re.escape(fence)}\s*"
        )
        return re.sub(pattern, "", text, flags=re.DOTALL)

    def _strip_markdown_code_fence(self, text: str) -> str:
        """Remove a markdown fence that wraps the whole ReAct response."""
        stripped = text.strip()
        match = re.fullmatch(r"```[a-zA-Z0-9_-]*\s*\n(.*?)\n```", stripped, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def _normalize_react_text(self, text: str) -> str:
        """Normalize common wrappers before ReAct parsing."""
        if not text:
            return text

        text = self._strip_vis_thinking_blocks(text)
        text = self._strip_markdown_code_fence(text)
        stripped = text.lstrip()
        fence = "`" * 6
        opening = f"{fence}{VisThinking.vis_tag()}"
        if not stripped.startswith(opening):
            return text

        lines = stripped.splitlines()
        if len(lines) < 3 or lines[0].strip() != opening:
            return text

        closing_index = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == fence:
                trailing_content = "\n".join(lines[idx + 1 :]).lstrip()
                if not trailing_content or trailing_content.startswith(
                    self.thought_prefix
                ):
                    closing_index = idx
                    break

        if closing_index is None:
            return text

        return "\n".join(lines[closing_index + 1 :]).lstrip()

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
        text = self._normalize_react_text(text).strip()

        # Find all line-start instances of the thought prefix outside code fences.
        thought_matches = self._find_prefix_matches(
            text, self.thought_prefix_escaped
        )

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

    def parse_current_step(self, text: str) -> List[ReActStep]:
        """Parse the single step that should be executed in the current round.

        Some reasoning models incorrectly emit a whole ReAct trajectory in one
        response. DB-GPT executes one action per round, so callers that are about
        to run tools should use only the first actionable step while preserving
        ``parse()`` for history and diagnostics.
        """
        steps = self.parse(text)
        if len(steps) <= 1:
            return steps
        for step in steps:
            if step.action:
                return [step]
        return [steps[0]]

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
        phase = None
        action_intention = None
        action_reason = None
        action = None
        action_input = None
        observation = None
        is_terminal = False
        match_text = self._mask_prefixes_in_fences(step_text)

        # Extract thought
        thought_line = self._prefix_line_pattern(self.thought_prefix_escaped)
        phase_line = self._prefix_line_pattern(self.phase_prefix_escaped)
        action_intention_line = self._prefix_line_pattern(
            self.action_intention_prefix_escaped
        )
        action_reason_line = self._prefix_line_pattern(
            self.action_reason_prefix_escaped
        )
        action_line = self._prefix_line_pattern(self.action_prefix_escaped)
        action_input_line = self._prefix_line_pattern(
            self.action_input_prefix_escaped
        )
        observation_line = self._prefix_line_pattern(
            self.observation_prefix_escaped
        )

        thought_match = re.search(
            rf"{thought_line}(.*?)(?={phase_line}|{action_intention_line}|"
            rf"{action_reason_line}|{action_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if thought_match:
            thought = step_text[thought_match.start(1) : thought_match.end(1)].strip()

        # Extract phase (optional, between thought and action)
        phase_match = re.search(
            rf"{phase_line}(.*?)(?={action_intention_line}|{action_reason_line}|"
            rf"{action_line}|{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if phase_match:
            phase = step_text[phase_match.start(1) : phase_match.end(1)].strip() or None

        # Extract action intention (optional, short user-facing intent)
        action_intention_match = re.search(
            rf"{action_intention_line}(.*?)(?={action_reason_line}|{action_line}|"
            rf"{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_intention_match:
            action_intention = (
                step_text[
                    action_intention_match.start(1) : action_intention_match.end(1)
                ].strip()
                or None
            )

        # Extract action reason (optional, short user-facing reason)
        action_reason_match = re.search(
            rf"{action_reason_line}(.*?)(?={action_intention_line}|{action_line}|"
            rf"{action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_reason_match:
            action_reason = (
                step_text[
                    action_reason_match.start(1) : action_reason_match.end(1)
                ].strip()
                or None
            )

        # Extract action
        action_match = re.search(
            rf"{action_line}(.*?)(?={action_input_line}|{observation_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_match:
            action = step_text[action_match.start(1) : action_match.end(1)].strip()

            # Check if this is a terminate action
            is_terminal = action.lower() == self.terminate_action.lower()

        # Extract action input
        action_input_match = re.search(
            rf"{action_input_line}(.*?)(?={observation_line}|{thought_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if action_input_match:
            action_input_text = step_text[
                action_input_match.start(1) : action_input_match.end(1)
            ].strip()

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
            rf"{observation_line}(.*?)(?={thought_line}|\Z)",
            match_text,
            re.DOTALL | re.MULTILINE,
        )
        if observation_match:
            observation_text = step_text[
                observation_match.start(1) : observation_match.end(1)
            ].strip()

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
                phase=phase,
                action_intention=action_intention,
                action_reason=action_reason,
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
                    and "result" in step.action_input
                ):
                    return step.action_input["result"]
                if (
                    isinstance(step.action_input, dict)
                    and "output" in step.action_input
                ):
                    return step.action_input["output"]
        return None
