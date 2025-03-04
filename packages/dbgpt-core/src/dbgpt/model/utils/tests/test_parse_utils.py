from ..parse_utils import parse_chat_message


# Non-streaming processing tests
def test_parse_deepseek_format():
    """Test parsing DeepSeek format messages"""
    input_text = """<think>I need to analyze the user's request and call the \
appropriate function to get information.</think>
The user is requesting weather information, I will call the weather API to get data.

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>get_weather
```json
{
    "location": "Beijing",
    "date": "2023-05-20"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    result = parse_chat_message(input_text, extract_tool_calls=True)

    assert result.role == "assistant"
    assert "requesting weather information" in result.content
    assert "analyze the user's request" in result.reasoning_content
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "get_weather"
    assert result.tool_calls[0]["arguments"]["location"] == "Beijing"
    assert result.tool_calls[0]["arguments"]["date"] == "2023-05-20"


def test_parse_chinese_format():
    """Test parsing Chinese content messages"""
    input_text = """<think>我需要解析用户的请求并调用适当的函数来获取信息。</think>
用户请求的是天气信息，我将调用天气API获取数据。

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>get_weather
```json
{
    "location": "北京",
    "date": "2023-05-20"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    result = parse_chat_message(input_text, extract_tool_calls=True)

    assert result.role == "assistant"
    assert "用户请求的是天气信息" in result.content
    assert "我需要解析用户的请求" in result.reasoning_content
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "get_weather"
    assert result.tool_calls[0]["arguments"]["location"] == "北京"
    assert result.tool_calls[0]["arguments"]["date"] == "2023-05-20"


def test_parse_custom_format():
    """Test parsing custom format messages"""
    input_text = """<reasoning>I need to check the current stock price for AAPL.\
</reasoning>
I'll look up the stock price for Apple Inc.

<tools>
function name="get_stock_price"
```json
{
    "symbol": "AAPL",
    "market": "NASDAQ"
}
```
</tools>"""

    custom_reasoning = [{"start": "<reasoning>", "end": "</reasoning>"}]
    custom_tools = [{"start": "<tools>", "end": "</tools>"}]

    result = parse_chat_message(
        input_text,
        reasoning_patterns=custom_reasoning,
        tool_call_patterns=custom_tools,
        extract_tool_calls=True,
    )

    assert "I'll look up the stock price" in result.content
    assert "I need to check the current stock price" in result.reasoning_content
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "get_stock_price"
    assert result.tool_calls[0]["arguments"]["symbol"] == "AAPL"


def test_extract_reasoning_option():
    """Test the extract_reasoning option"""
    input_text = "<think>This is reasoning content</think>This is regular content"

    # Don't extract reasoning content
    result1 = parse_chat_message(input_text, extract_reasoning=False)
    assert (
        "<think>This is reasoning content</think>This is regular content"
        == result1.content
    )
    assert "" == result1.reasoning_content

    # Extract reasoning content
    result2 = parse_chat_message(input_text, extract_reasoning=True)
    assert "This is regular content" == result2.content
    assert "This is reasoning content" == result2.reasoning_content


def test_extract_tool_calls_option():
    """Test the extract_tool_calls option"""
    input_text = """I'll look up information for you.

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>get_data
```json
{
    "query": "test"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    # Don't extract tool calls
    result1 = parse_chat_message(input_text, extract_tool_calls=False)
    assert input_text == result1.content
    assert len(result1.tool_calls) == 0

    # Extract tool calls
    result2 = parse_chat_message(input_text, extract_tool_calls=True)
    assert "I'll look up information for you." in result2.content
    assert len(result2.tool_calls) == 1
    assert result2.tool_calls[0]["name"] == "get_data"
    assert result2.tool_calls[0]["arguments"]["query"] == "test"


def test_extract_both_options():
    """Test both extract_reasoning and extract_tool_calls options together"""
    input_text = """<think>I need to search for data</think>I'll search for information.

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>search
```json
{
    "query": "test"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    # Extract neither
    result1 = parse_chat_message(
        input_text, extract_reasoning=False, extract_tool_calls=False
    )
    assert input_text == result1.content
    assert "" == result1.reasoning_content
    assert len(result1.tool_calls) == 0

    # Extract both
    result2 = parse_chat_message(
        input_text, extract_reasoning=True, extract_tool_calls=True
    )
    assert "I'll search for information." in result2.content
    assert "I need to search for data" == result2.reasoning_content
    assert len(result2.tool_calls) == 1

    # Extract only reasoning
    result3 = parse_chat_message(
        input_text, extract_reasoning=True, extract_tool_calls=False
    )
    assert "<｜tool▁calls▁begin｜>" in result3.content
    assert "I need to search for data" == result3.reasoning_content
    assert len(result3.tool_calls) == 0

    # Extract only tool calls
    result4 = parse_chat_message(
        input_text, extract_reasoning=False, extract_tool_calls=True
    )
    assert (
        "<think>I need to search for data</think>I'll search for information."
        == result4.content
    )
    assert "" == result4.reasoning_content
    assert len(result4.tool_calls) == 1


def test_multiple_reasoning_patterns():
    """Test different reasoning marker patterns"""
    input_texts = [
        "<think>Reasoning content 1</think>Regular content",
        "<reasoning>Reasoning content 2</reasoning>Regular content",
        "<思考>推理内容3</思考>普通内容",
    ]

    for i, text in enumerate(input_texts, 1):
        result = parse_chat_message(text)
        if i == 3:
            assert "推理内容3" == result.reasoning_content
            assert "普通内容" == result.content
        else:
            assert f"Reasoning content {i}" == result.reasoning_content
            assert "Regular content" == result.content


def test_mixed_language_content():
    """Test parsing messages with mixed language content"""
    input_text = """<think>I need to analyze 用户的请求 and provide information.</think>
I will help 查询天气 for the specified location.

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>get_weather
```json
{
    "location": "Shanghai 上海",
    "date": "2023-05-20"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    result = parse_chat_message(input_text, extract_tool_calls=True)

    assert "I will help 查询天气" in result.content
    assert "I need to analyze 用户的请求" in result.reasoning_content
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["arguments"]["location"] == "Shanghai 上海"


def test_no_special_markers():
    """Test parsing plain text without any special markers"""
    input_text = "This is a regular text with no special markers."
    result = parse_chat_message(input_text)

    assert input_text == result.content
    assert "" == result.reasoning_content
    assert len(result.tool_calls) == 0


def test_malformed_json():
    """Test handling of malformed JSON in tool calls"""
    input_text = """<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>broken_function
```json
{
    "query": "test",
    missing_quotes: value,
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    result = parse_chat_message(input_text, extract_tool_calls=True)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "broken_function"
    assert isinstance(
        result.tool_calls[0]["arguments"], str
    )  # Should contain the raw string


# Streaming processing tests
def test_streaming_mode_reasoning():
    """Test processing reasoning content in streaming mode"""
    chunks = [
        "I will help you ",
        "with your query.<think>",
        "I need to analyze ",
        "the user's request.</think>",
        "Processing your request now.",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(chunk, is_streaming=True, streaming_state=msg)
        all_events.extend(events)

    # Verify final message
    assert "I will help you with your query.Processing your request now." == msg.content
    assert "I need to analyze the user's request." == msg.reasoning_content

    # Verify event sequence
    event_types = [e.type for e in all_events]
    expected_types = [
        "content",  # "I will help you "
        "content",  # "with your query."
        "reasoning_start",  # <think> marker
        "reasoning_content",  # "I need to analyze "
        "reasoning_content",  # "the user's request."
        "reasoning_end",  # </think> marker
        "content",  # "Processing your request now."
    ]

    assert expected_types == event_types


def test_streaming_mode_tool_call():
    """Test processing tool calls in streaming mode"""
    chunks = [
        "I will search ",
        "for information.<｜tool▁calls▁begin｜>",
        "<｜tool▁call▁begin｜>function<｜tool▁sep｜>search_data",
        "\n```json\n{",
        '"query": "test data",',
        '"limit": 10',
        "}\n```",
        "<｜tool▁call▁end｜>",
        "<｜tool▁calls▁end｜>",
        "Search complete.",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(
            chunk, is_streaming=True, streaming_state=msg, extract_tool_calls=True
        )
        all_events.extend(events)

    # Verify final message
    assert "I will search for information.Search complete." == msg.content
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0]["name"] == "search_data"
    assert msg.tool_calls[0]["arguments"]["query"] == "test data"
    assert msg.tool_calls[0]["arguments"]["limit"] == 10

    # Verify event sequence
    event_types = [e.type for e in all_events]
    assert "tool_call_start" in event_types
    assert "tool_call_content" in event_types
    assert "tool_call_end" in event_types


def test_streaming_mode_without_tool_calls():
    """Test streaming mode with extract_tool_calls=False"""
    chunks = [
        "I will search for data",
        ".<｜tool▁calls▁begin｜>",
        "Tool call content",
        "<｜tool▁calls▁end｜>",
        "Search complete.",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(
            chunk, is_streaming=True, streaming_state=msg, extract_tool_calls=False
        )
        all_events.extend(events)

    # Verify final message should include tool call markers
    assert (
        "I will search for data.<｜tool▁calls▁begin｜>Tool call content"
        "<｜tool▁calls▁end｜>Search complete." == msg.content  # noqa
    )
    assert len(msg.tool_calls) == 0

    # Verify no tool call events
    event_types = [e.type for e in all_events]
    assert "tool_call_start" not in event_types
    assert "tool_call_content" not in event_types
    assert "tool_call_end" not in event_types


def test_streaming_mode_overlapping():
    """Test handling nested or overlapping markers in streaming mode"""
    chunks = [
        "Start<think>I need to ",
        "analyze</think>Middle<｜tool▁calls▁begin｜>",
        "Tool call content<｜tool▁calls▁end｜>",
        "End",
    ]

    msg = None
    all_events = []

    for i, chunk in enumerate(chunks):
        msg, events = parse_chat_message(
            chunk, is_streaming=True, streaming_state=msg, extract_tool_calls=True
        )
        if i == 0:
            # First chunk contains reasoning content
            assert "I need to " == msg.reasoning_content
        all_events.extend(events)

    # Verify final message
    assert "StartMiddleEnd" == msg.content
    assert "I need to analyze" == msg.reasoning_content

    # Ensure correct event order
    reasoning_start_indices = [
        i for i, e in enumerate(all_events) if e.type == "reasoning_start"
    ]
    reasoning_end_indices = [
        i for i, e in enumerate(all_events) if e.type == "reasoning_end"
    ]
    tool_start_indices = [
        i for i, e in enumerate(all_events) if e.type == "tool_call_start"
    ]
    tool_end_indices = [
        i for i, e in enumerate(all_events) if e.type == "tool_call_end"
    ]

    # Verify nesting order
    assert reasoning_start_indices[0] < reasoning_end_indices[0]
    assert reasoning_end_indices[0] < tool_start_indices[0]
    assert tool_start_indices[0] < tool_end_indices[0]


def test_incomplete_markers():
    """Test handling incomplete markers"""
    # Test incomplete reasoning marker
    chunks1 = [
        "Start<think>Reasoning",
        "content",  # No end marker
    ]

    msg1 = None
    for chunk in chunks1:
        msg1, _ = parse_chat_message(
            chunk, is_streaming=True, streaming_state=msg1, extract_tool_calls=False
        )

    # Verify reasoning content is recorded but state is still incomplete
    assert "Reasoningcontent" == msg1.reasoning_content
    assert msg1.streaming_state["in_reasoning"] is True

    # Test incomplete tool call marker
    chunks2 = [
        "Start<｜tool▁calls▁begin｜>",
        "Tool content",  # No end marker
    ]

    msg2 = None
    for chunk in chunks2:
        msg2, _ = parse_chat_message(
            chunk, is_streaming=True, streaming_state=msg2, extract_tool_calls=True
        )

    # Verify tool call content is recorded but state is still incomplete
    assert msg2.streaming_state["in_tool_call"] is True
    assert "Tool content" in msg2.streaming_state.get("tool_call_text", "")


def test_custom_streaming_patterns():
    """Test custom streaming pattern markers"""
    custom_reasoning = [{"start": "{{thinking}}", "end": "{{/thinking}}"}]
    custom_tools = [{"start": "{{tools}}", "end": "{{/tools}}"}]

    chunks = [
        "Start{{thinking}}I need to ",
        "analyze{{/thinking}}Middle{{tools}}",
        "Tool content{{/tools}}",
        "End",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(
            chunk,
            is_streaming=True,
            streaming_state=msg,
            reasoning_patterns=custom_reasoning,
            tool_call_patterns=custom_tools,
            extract_tool_calls=True,
        )
        all_events.extend(events)

    # Verify final message
    assert "StartMiddleEnd" == msg.content
    assert "I need to analyze" == msg.reasoning_content

    # Verify event sequence
    event_types = [e.type for e in all_events]
    assert "reasoning_start" in event_types
    assert "reasoning_content" in event_types
    assert "reasoning_end" in event_types
    assert "tool_call_start" in event_types
    assert "tool_call_end" in event_types


def test_missing_start_token_non_streaming():
    """Test parsing messages with missing start token but having end token
    (non-streaming mode)
    """
    input_text = """Model reasoning content without start token.
</think>
This is the regular content part."""

    result = parse_chat_message(input_text, extract_reasoning=True)

    assert "This is the regular content part." == result.content
    assert "Model reasoning content without start token." == result.reasoning_content


def test_missing_start_token_streaming():
    """Test parsing messages with missing start token but having end token
    (streaming mode)
    """
    chunks = [
        "Model reasoning content ",
        "without start token.</think>",
        "This is the regular content part.",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(chunk, is_streaming=True, streaming_state=msg)
        all_events.extend(events)

    # Verify final message - match the expected result in test
    assert "This is the regular content part." == msg.content
    assert "Model reasoning content without start token." == msg.reasoning_content

    # Verify event sequence contains correct reasoning events
    event_types = [e.type for e in all_events]
    assert "reasoning_start" in event_types
    assert "reasoning_content" in event_types
    assert "reasoning_end" in event_types


def test_missing_start_token_deepseek_chinese():
    """Test the DeepSeek example with Chinese content missing start token"""
    input_text = """您好！我是由中国的深度求索（DeepSeek）公司开发的智能助手\
DeepSeek-R1。有关模型和产品的详细内容请参考官方文档。
</think>
您好！我是由中国的深度求索（DeepSeek）公司开发的智能助手DeepSeek-R1。有关模型\
和产品的详细内容请参考官方文档。"""

    result = parse_chat_message(input_text, extract_reasoning=True)

    assert (
        "您好！我是由中国的深度求索（DeepSeek）公司开发的智能助手DeepSeek-R1。"
        "有关模型和产品的详细内容请参考官方文档。" == result.content
    )
    assert (
        "您好！我是由中国的深度求索（DeepSeek）公司开发的智能助手DeepSeek-R1。"
        "有关模型和产品的详细内容请参考官方文档。" == result.reasoning_content
    )


def test_multiple_missing_start_tokens():
    """Test multiple occurrences of missing start tokens in the same message"""
    input_text = """First reasoning section.
</think>
Some regular content.
Second reasoning section.
</reasoning>
More regular content."""

    result = parse_chat_message(input_text, extract_reasoning=True)

    # Note: In non-streaming mode, only the first matching reasoning content is
    # extracted
    assert (
        "Some regular content.\nSecond reasoning section.\n</reasoning>\nMore regular "
        "content." == result.content
    )
    assert "First reasoning section." == result.reasoning_content

    # Use streaming to capture all sections
    chunks = [
        "First reasoning section.\n</think>\n",
        "Some regular content.\n",
        "Second reasoning section.\n</reasoning>\n",
        "More regular content.",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(chunk, is_streaming=True, streaming_state=msg)
        all_events.extend(events)

    # In streaming mode, reasoning content should match the expected format
    assert (
        "First reasoning section.\n\nSome regular content.\nSecond reasoning section.\n"
        == msg.reasoning_content
    )

    # Verify event sequence contains two reasoning sections
    reasoning_start_counts = sum(1 for e in all_events if e.type == "reasoning_start")
    reasoning_end_counts = sum(1 for e in all_events if e.type == "reasoning_end")

    assert reasoning_start_counts == 2
    assert reasoning_end_counts == 2


def test_missing_start_token_with_tools():
    """Test missing reasoning start token with tool calls"""
    input_text = """Analyzing user request to query weather information.
</think>
I'll look up the weather data for you.

<｜tool▁calls▁begin｜>
<｜tool▁call▁begin｜>function<｜tool▁sep｜>get_weather
```json
{
    "location": "Beijing",
    "date": "2023-05-20"
}
```
<｜tool▁call▁end｜>
<｜tool▁calls▁end｜>"""

    result = parse_chat_message(
        input_text, extract_reasoning=True, extract_tool_calls=True
    )

    assert "I'll look up the weather data for you." in result.content
    assert (
        "Analyzing user request to query weather information."
        == result.reasoning_content
    )
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "get_weather"
    assert result.tool_calls[0]["arguments"]["location"] == "Beijing"


def test_mixed_language_missing_start_token():
    """Test mixed Chinese and English content with missing start token"""
    input_text = """这是一段中英文混合的思考内容 with both languages mixed together.
</think>
Here's the regular content with 中文 mixed in."""

    result = parse_chat_message(input_text, extract_reasoning=True)

    assert "Here's the regular content with 中文 mixed in." == result.content
    assert (
        "这是一段中英文混合的思考内容 with both languages mixed together."
        == result.reasoning_content
    )


def test_streaming_mixed_language_missing_start():
    """Test streaming mixed language content with missing start token"""
    chunks = [
        "Analysis 分析: The user needs ",
        "information about 关于天气的信息。</reasoning>",
        "I'll provide weather information 我将提供天气信息。",
    ]

    msg = None
    all_events = []

    for chunk in chunks:
        msg, events = parse_chat_message(chunk, is_streaming=True, streaming_state=msg)
        all_events.extend(events)

    # Verify final message includes mixed language content properly parsed
    assert "I'll provide weather information 我将提供天气信息。" == msg.content
    assert (
        "Analysis 分析: The user needs information about 关于天气的信息。"
        == msg.reasoning_content
    )

    # Verify events sequence
    reasoning_events = [e for e in all_events if e.type.startswith("reasoning_")]
    assert len(reasoning_events) >= 3  # At least start, content, and end events


def test_chinese_pattern_missing_start():
    """Test Chinese pattern with missing start token"""
    input_text = """这里是模型的思考内容，但是没有开始标记。
</思考>
这是正常的响应内容。"""

    result = parse_chat_message(input_text, extract_reasoning=True)

    assert "这是正常的响应内容。" == result.content
    assert "这里是模型的思考内容，但是没有开始标记。" == result.reasoning_content


#
# def test_multiple_special_sections():
#     """Test handling multiple special sections"""
#     input_text = """<think>Reasoning content 1</think>Regular content 1
# <｜tool▁calls▁begin｜>Tool call content<｜tool▁calls▁end｜>
# Regular content 2<think>Reasoning content 2</think>End"""
#
#     result = parse_chat_message(input_text, extract_tool_calls=True)
#
#     # Verify only first reasoning content is extracted
#     assert "Reasoning content 1" == result.reasoning_content
#     assert (
#         "Regular content 1\n\nRegular content 2<think>Reasoning content 2</think>End"
#         == result.content
#     )
#
#     # Use streaming processing to handle multiple reasoning parts
#     chunks = [
#         "<think>Reasoning content 1</think>Regular content 1\n",
#         "<｜tool▁calls▁begin｜>Tool call content<｜tool▁calls▁end｜>\n",
#         "Regular content 2<think>Reasoning content 2</think>End",
#     ]
#
#     msg = None
#     all_events = []
#
#     for chunk in chunks:
#         msg, events = parse_chat_message(
#             chunk, is_streaming=True, streaming_state=msg, extract_tool_calls=True
#         )
#         all_events.extend(events)
#
#     # Verify event sequence contains two reasoning sections
#     reasoning_start_counts = sum(1 for e in all_events if e.type == "reasoning_start")
#     reasoning_end_counts = sum(1 for e in all_events if e.type == "reasoning_end")
#
#     assert reasoning_start_counts == 2
#     assert reasoning_end_counts == 2
#
#     # In streaming mode, reasoning content should match the expected format
#     assert "Reasoning content 1Reasoning content 2" == msg.reasoning_content
