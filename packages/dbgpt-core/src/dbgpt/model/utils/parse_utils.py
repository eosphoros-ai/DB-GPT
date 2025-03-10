import json
import re
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union

_DEFAULT_THINK_START_TOKEN = "<think>"
_DEFAULT_THINK_END_TOKEN = "</think>"


class StreamingEvent(NamedTuple):
    """Streaming event type, representing various events in the streaming parsing
    process
    """

    type: str
    """Event type: 'reasoning_start', 'reasoning_content', 'reasoning_end', 
    'tool_call_start', 'tool_call_content', 'tool_call_end', 'content'
    """
    content: str  # Event content


class ParsedChatMessage:
    """Universal chat message structure"""

    def __init__(self):
        self.role: str = "assistant"
        self.content: str = ""
        self.reasoning_content: str = ""
        self.tool_calls: List[Dict[str, Any]] = []
        # Streaming state tracking
        self.streaming_state: Dict[str, Any] = {
            "in_reasoning": False,
            "reasoning_pattern": None,
            "in_tool_call": False,
            "tool_call_pattern": None,
            # No longer using buffers, output events directly
        }


def string_strip(s: str) -> str:
    """Remove leading and trailing whitespace from a string"""
    return s.strip() if s else ""


def parse_json_tool_calls(
    tool_calls_text: str,
    default_name: Optional[str] = None,
    function_regex: Optional[re.Pattern] = None,
    close_regex: Optional[re.Pattern] = None,
) -> List[Dict[str, Any]]:
    """Parse JSON format tool calls"""
    tool_calls = []

    # Use default regex if not provided
    if function_regex is None:
        function_regex = re.compile(
            r'function\s*(?:name)?\s*[:=]?\s*["\']?([^"\'\n]+)["\']?\s*\n```(?:json)?\s*\n'  # noqa
        )

    if close_regex is None:
        close_regex = re.compile(r"```\s*")

    current_pos = 0
    remaining_text = tool_calls_text

    while current_pos < len(tool_calls_text):
        # Find the beginning of function call
        function_match = function_regex.search(remaining_text)
        if not function_match:
            break

        function_name = function_match.group(1).strip()
        start_json = function_match.end()

        # Find the end of JSON content
        close_match = close_regex.search(remaining_text[start_json:])
        if not close_match:
            break

        json_content = remaining_text[start_json : start_json + close_match.start()]

        try:
            args = json.loads(json_content)
            tool_call = {"name": function_name or default_name or "", "arguments": args}
            tool_calls.append(tool_call)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract raw text
            tool_call = {
                "name": function_name or default_name or "",
                "arguments": json_content.strip(),
            }
            tool_calls.append(tool_call)

        # Update position to continue searching
        current_pos += start_json + close_match.end()
        remaining_text = tool_calls_text[current_pos:]

    return tool_calls


def process_streaming_chunk(
    chunk: str,
    msg: ParsedChatMessage,
    reasoning_patterns: List[Dict[str, str]],
    tool_call_patterns: List[Dict[str, str]],
    extract_tool_calls: bool = True,
) -> List[StreamingEvent]:
    """
    Process a single chunk of streaming message, return a list of parsed events

    Parameters:
        chunk: Current received text block
        msg: ParsedChatMessage object to update
        reasoning_patterns: List of reasoning patterns
        tool_call_patterns: List of tool call patterns
        extract_tool_calls: Whether to extract tool calls

    Returns:
        List of events, each representing a parsed part of content
    """
    state = msg.streaming_state
    events = []
    remaining_chunk = chunk

    while remaining_chunk:
        # Currently in reasoning content
        if state["in_reasoning"]:
            end_marker = state["reasoning_pattern"]["end"]
            if end_marker in remaining_chunk:
                end_idx = remaining_chunk.find(end_marker)
                # Output reasoning content event
                # if end_idx > 0:
                reasoning_part = remaining_chunk[:end_idx]
                events.append(
                    StreamingEvent(type="reasoning_content", content=reasoning_part)
                )
                # Append reasoning content instead of replacing
                msg.reasoning_content += reasoning_part

                # Output reasoning end event
                events.append(StreamingEvent(type="reasoning_end", content=""))

                # Reset reasoning state
                state["in_reasoning"] = False
                state["reasoning_pattern"] = None

                # Process remaining content
                remaining_chunk = remaining_chunk[end_idx + len(end_marker) :]
            else:
                # The entire chunk is reasoning content
                events.append(
                    StreamingEvent(type="reasoning_content", content=remaining_chunk)
                )
                # Similarly, append instead of replace
                msg.reasoning_content += remaining_chunk
                remaining_chunk = ""
            continue

        # Currently in tool call
        if state["in_tool_call"] and extract_tool_calls:
            end_marker = state["tool_call_pattern"]["end"]
            if end_marker in remaining_chunk:
                end_idx = remaining_chunk.find(end_marker)
                # Output tool call content event
                if end_idx > 0:
                    tool_call_part = remaining_chunk[:end_idx]
                    events.append(
                        StreamingEvent(type="tool_call_content", content=tool_call_part)
                    )

                # Store content before end marker temporarily for parsing
                tool_call_text = (
                    state.get("tool_call_text", "") + remaining_chunk[:end_idx]
                )

                # Try to parse tool call content
                function_regex_patterns = [
                    re.compile(
                        r"<｜tool▁call▁begin｜>function<｜tool▁sep｜>([^\n]+)\n```json\n"
                    ),
                    re.compile(r"function\s*:\s*([^\n]+)\n```json\n"),
                    re.compile(r'function\s*name\s*=\s*"([^"]+)"\n```json\n'),
                ]

                close_regex_patterns = [
                    re.compile(r"```\s*<｜tool▁call▁end｜>"),
                    re.compile(r"```\s*"),
                ]

                # Try to parse tool calls
                for func_regex in function_regex_patterns:
                    for close_regex in close_regex_patterns:
                        tool_calls = parse_json_tool_calls(
                            tool_call_text, None, func_regex, close_regex
                        )
                        if tool_calls:
                            msg.tool_calls.extend(tool_calls)
                            break
                    if msg.tool_calls:
                        break

                # Output tool call end event
                events.append(StreamingEvent(type="tool_call_end", content=""))

                # Reset tool call state
                state["in_tool_call"] = False
                state["tool_call_pattern"] = None
                state.pop("tool_call_text", None)

                # Process remaining content
                remaining_chunk = remaining_chunk[end_idx + len(end_marker) :]
            else:
                # The entire chunk is tool call content
                events.append(
                    StreamingEvent(type="tool_call_content", content=remaining_chunk)
                )
                # Accumulate tool call text for later parsing
                state["tool_call_text"] = (
                    state.get("tool_call_text", "") + remaining_chunk
                )
                remaining_chunk = ""
            continue

        # Check for reasoning end markers without matching start markers
        # This is the special case to handle
        found_end_marker = False
        for pattern in reasoning_patterns:
            start_marker = pattern["start"]
            end_marker = pattern["end"]
            if end_marker in remaining_chunk and not state["in_reasoning"]:
                end_idx = remaining_chunk.find(end_marker)
                start_idx = 0
                if start_marker in remaining_chunk:
                    start_idx = remaining_chunk.find(start_marker) + len(start_marker)

                # This is content that should be treated as reasoning but didn't have a
                # start tag
                # if end_idx > 0:
                reasoning_part = remaining_chunk[start_idx:end_idx]
                # Clear regular content
                reasoning_part = msg.content + reasoning_part
                msg.content = ""

                # First, emit a reasoning_start event
                events.append(StreamingEvent(type="reasoning_start", content=""))

                # Then emit the content as reasoning content
                events.append(
                    StreamingEvent(type="reasoning_content", content=reasoning_part)
                )

                # Add to reasoning content
                msg.reasoning_content += reasoning_part

                # Emit the reasoning_end event
                events.append(StreamingEvent(type="reasoning_end", content=""))
                # Move past the end marker
                remaining_chunk = remaining_chunk[end_idx + len(end_marker) :]
                found_end_marker = True
                state["reasoning_pattern"] = None
                break

        # If we found an end marker, continue to the next iteration
        if found_end_marker:
            continue

        # Check for reasoning start markers
        reasoning_start_found = False
        for pattern in reasoning_patterns:
            start_marker = pattern["start"]
            if start_marker in remaining_chunk:
                start_idx = remaining_chunk.find(start_marker)

                # Output regular content before the marker
                # if start_idx > 0:
                content_part = remaining_chunk[:start_idx]
                events.append(StreamingEvent(type="content", content=content_part))
                msg.content += content_part

                # Output reasoning start event
                events.append(StreamingEvent(type="reasoning_start", content=""))

                # Set reasoning state
                state["in_reasoning"] = True
                state["reasoning_pattern"] = pattern

                # Process content after the marker
                remaining_chunk = remaining_chunk[start_idx + len(start_marker) :]
                reasoning_start_found = True
                break

        if reasoning_start_found:
            continue

        # Check for tool call start markers
        tool_call_start_found = False
        if extract_tool_calls:
            for pattern in tool_call_patterns:
                start_marker = pattern["start"]
                if start_marker in remaining_chunk:
                    start_idx = remaining_chunk.find(start_marker)

                    # Output regular content before the marker
                    # if start_idx > 0:
                    content_part = remaining_chunk[:start_idx]
                    events.append(StreamingEvent(type="content", content=content_part))
                    msg.content += content_part

                    # Output tool call start event
                    events.append(StreamingEvent(type="tool_call_start", content=""))

                    # Set tool call state
                    state["in_tool_call"] = True
                    state["tool_call_pattern"] = pattern
                    state["tool_call_text"] = ""

                    # Process content after the marker
                    remaining_chunk = remaining_chunk[start_idx + len(start_marker) :]
                    tool_call_start_found = True
                    break

        if tool_call_start_found:
            continue

        # If no special markers, current chunk is regular content
        events.append(StreamingEvent(type="content", content=remaining_chunk))
        msg.content += remaining_chunk
        remaining_chunk = ""

    return events


def parse_chat_message(
    input_text: str,
    extract_reasoning: bool = True,
    extract_tool_calls: bool = False,
    is_streaming: bool = False,
    reasoning_patterns: Optional[List[Dict[str, str]]] = None,
    tool_call_patterns: Optional[List[Dict[str, str]]] = None,
    streaming_state: Optional[ParsedChatMessage] = None,
) -> Union[ParsedChatMessage, Tuple[ParsedChatMessage, List[StreamingEvent]]]:
    """
    Universal chat message parsing function

    Parameters:
        input_text: Input text
        extract_reasoning: Whether to extract reasoning content
        extract_tool_calls: Whether to extract tool calls
        is_streaming: Whether to process as streaming message
        reasoning_patterns: Custom list of reasoning patterns, each pattern is a
            dictionary containing start and end markers
        tool_call_patterns: Custom list of tool call patterns, each pattern is a
            dictionary containing start and end markers
        streaming_state: State object passed in when processing streaming messages,
            used to track progress

    Returns:
        If is_streaming=False, returns the parsed ParsedChatMessage object
        If is_streaming=True, returns (ParsedChatMessage, events) tuple, where events
            is the list of parsed events
    """
    # Default reasoning patterns
    if reasoning_patterns is None:
        reasoning_patterns = [
            {"start": _DEFAULT_THINK_START_TOKEN, "end": _DEFAULT_THINK_END_TOKEN},
            {"start": "<reasoning>", "end": "</reasoning>"},
            {"start": "<思考>", "end": "</思考>"},
        ]

    # Default tool call patterns
    if tool_call_patterns is None:
        tool_call_patterns = [
            {"start": "<｜tool▁calls▁begin｜>", "end": "<｜tool▁calls▁end｜>"},
            {"start": "<｜tool_calls_begin｜>", "end": "<｜tool_calls_end｜>"},
            {"start": "<｜tool calls begin｜>", "end": "<｜tool calls end｜>"},
            {"start": "<｜tool\\_calls\\_begin｜>", "end": "<｜tool\\_calls\\_end｜>"},
            {"start": "<tool_calls>", "end": "</tool_calls>"},
            {"start": "<tools>", "end": "</tools>"},
        ]

    # Streaming processing mode
    if is_streaming:
        # Use provided state or create new one
        msg = streaming_state or ParsedChatMessage()

        # Process current text block and get events
        events = process_streaming_chunk(
            input_text, msg, reasoning_patterns, tool_call_patterns, extract_tool_calls
        )

        return msg, events

    # Non-streaming processing mode (original logic)
    msg = ParsedChatMessage()

    # Parse reasoning content
    reasoning_content = ""
    content = input_text

    # First check for the normal case with proper start and end markers
    for pattern in reasoning_patterns:
        start_marker = pattern["start"]
        end_marker = pattern["end"]

        if start_marker in content and end_marker in content:
            start_idx = content.find(start_marker)
            end_idx = content.find(end_marker, start_idx + len(start_marker))

            if start_idx >= 0 and end_idx >= 0:
                reasoning_text = content[start_idx + len(start_marker) : end_idx]
                reasoning_content = string_strip(reasoning_text)

                # Remove reasoning part from original content
                if extract_reasoning:
                    content = content[:start_idx] + content[end_idx + len(end_marker) :]
                break

    # If no reasoning content was found with the standard pattern, check for the
    # special case
    # where content starts with reasoning but has no start marker
    if not reasoning_content:
        for pattern in reasoning_patterns:
            start_marker = pattern["start"]
            end_marker = pattern["end"]

            if end_marker in content:
                # Check if this is at the beginning of the content or
                # if there's no matching start marker before it
                end_idx = content.find(end_marker)
                start_marker = pattern["start"]
                start_idx = content.find(start_marker)

                # If no start marker or end marker appears before start marker
                if start_idx == -1 or end_idx < start_idx:
                    # This is our special case - treat the content up to the end marker
                    # as reasoning
                    reasoning_content = string_strip(content[:end_idx])

                    # Remove reasoning part from original content
                    if extract_reasoning:
                        content = content[end_idx + len(end_marker) :]
                    break
            elif start_marker in content:
                # If there's a start marker but no end marker, treat the content
                # as reasoning content
                start_idx = content.find(start_marker)
                reasoning_content = string_strip(
                    content[start_idx + len(start_marker) :]
                )

                # Remove reasoning part from original content
                if extract_reasoning:
                    content = ""
                break

    # Parse tool calls
    tool_calls_text = ""

    if extract_tool_calls:
        for pattern in tool_call_patterns:
            start_marker = pattern["start"]
            end_marker = pattern["end"]

            if start_marker in content and end_marker in content:
                start_idx = content.find(start_marker)
                end_idx = content.find(end_marker, start_idx + len(start_marker))

                if start_idx >= 0 and end_idx >= 0:
                    tool_calls_text = content[start_idx + len(start_marker) : end_idx]

                    # Remove tool call part from original content
                    content = content[:start_idx] + content[end_idx + len(end_marker) :]
                    break

        # Process function calls
        function_regex_patterns = [
            re.compile(
                r"<｜tool▁call▁begin｜>function<｜tool▁sep｜>([^\n]+)\n```json\n"
            ),
            re.compile(r"function\s*:\s*([^\n]+)\n```json\n"),
            re.compile(r'function\s*name\s*=\s*"([^"]+)"\n```json\n'),
        ]

        close_regex_patterns = [
            re.compile(r"```\s*<｜tool▁call▁end｜>"),
            re.compile(r"```\s*"),
        ]

        if tool_calls_text:
            for func_regex in function_regex_patterns:
                for close_regex in close_regex_patterns:
                    tool_calls = parse_json_tool_calls(
                        tool_calls_text, None, func_regex, close_regex
                    )
                    if tool_calls:
                        msg.tool_calls = tool_calls
                        break
                if msg.tool_calls:
                    break

    # Set final content
    msg.content = string_strip(content)
    if extract_reasoning:
        msg.reasoning_content = reasoning_content

    return msg
