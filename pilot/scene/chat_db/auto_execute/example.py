from pilot.prompts.example_base import ExampleSelector
from pilot.common.schema import ExampleType
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

sql_data_example = ExampleSelector(examples_record=EXAMPLES, use_example=True, type=ExampleType.ONE_SHOT.value)
