from dbgpt.core._private.example_base import ExampleSelector, ExampleType

## Two examples are defined by default
EXAMPLES = [
    {
        "messages": [
            {"type": "human", "data": {"content": "查询用户test1所在的城市", "example": True}},
            {
                "type": "ai",
                "data": {
                    "content": """{\n\"thoughts\": \"直接查询用户表中用户名为'test1'的记录即可\",\n\"sql\": \"SELECT city FROM user where user_name='test1'\"}""",
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
                    "content": """{\n\"thoughts\": \"根据订单表的用户名和用户表的用户名关联用户表和订单表，再通过用户表的城市为'成都'的过滤即可\",\n\"sql\": \"SELECT b.* FROM user a  LEFT JOIN tran_order b ON a.user_name=b.user_name  where a.city='成都'\"}""",
                    "example": True,
                },
            },
        ]
    },
]

sql_data_example = ExampleSelector(
    examples_record=EXAMPLES, use_example=True, type=ExampleType.ONE_SHOT.value
)
