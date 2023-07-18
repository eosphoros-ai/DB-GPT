from pilot.prompts.example_base import ExampleSelector
from pilot.common.schema import ExampleType

## Two examples are defined by default
EXAMPLES = [
    {
        "messages": [
            {"type": "human", "data": {"content": "查询用户test1所在的城市", "example": True}},
            {
                "type": "ai",
                "data": {
                    "content": """{
							\"thoughts\": \"thought text\",
							\"sql\": \"SELECT city FROM user where user_name='test1'\",
						}""",
                    "example": True,
                },
            },
        ]
    },
    {
        "messages": [
            {"type": "human", "data": {"content": "查询成都的用户的订单信息", "example": True}},
            {
                "type": "ai",
                "data": {
                    "content": """{
							\"thoughts\": \"thought text\",
							\"sql\": \"SELECT b.* FROM user a  LEFT JOIN tran_order b ON a.user_name=b.user_name  where a.city='成都'\",
						}""",
                    "example": True,
                },
            },
        ]
    },
]

sql_data_example = ExampleSelector(
    examples_record=EXAMPLES, use_example=True, type=ExampleType.ONE_SHOT.value
)
