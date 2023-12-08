from dbgpt.core._private.example_base import ExampleSelector

## Two examples are defined by default
EXAMPLES = [
    {
        "messages": [
            {"type": "human", "data": {"content": "查询xxx", "example": True}},
            {
                "type": "ai",
                "data": {
                    "content": """{
							\"thoughts\": \"thought text\",
							\"speak\": \"thoughts summary to say to user\",
							\"command\": {\"name\": \"command name\", \"args\": {\"arg name\": \"value\"}},
						}""",
                    "example": True,
                },
            },
        ]
    },
]

plugin_example = ExampleSelector(examples_record=EXAMPLES, use_example=True)
