"""FinReportJoinOperator."""
from dbgpt.core import ModelMessage, ModelRequest, StorageInterface
from dbgpt.core.awel import (
    CommonLLMHttpRequestBody,
    JoinOperator,
    MapOperator,
    is_empty_data,
)
from dbgpt.core.awel.flow import IOField, OperatorCategory, ViewMetadata
from dbgpt.core.interface.operators.message_operator import BaseConversationOperator


class RequestHandleOperator(
    BaseConversationOperator, MapOperator[CommonLLMHttpRequestBody, ModelRequest]
):
    """RequestHandleOperator."""

    def __init__(self, storage: StorageInterface, **kwargs):
        """Create a new RequestHandleOperator."""
        MapOperator.__init__(self, **kwargs)
        BaseConversationOperator.__init__(
            self, storage=storage, message_storage=storage
        )

    async def map(self, input_value: str) -> ModelRequest:
        """Map the input value to the output value."""
        return ModelRequest.build_request(
            "chatgpt_proxyllm", messages=[ModelMessage.build_human_message(input_value)]
        )


def join_func(*args):
    """Join function."""
    for arg in args:
        if not is_empty_data(arg):
            return arg
    return None


class FinReportJoinOperator(JoinOperator[str]):
    """FinReportJoinOperator."""

    streaming_operator = True
    metadata = ViewMetadata(
        label="Fin Report Output Join Operator",
        name="final_join_operator",
        category=OperatorCategory.COMMON,
        description="A example operator to say hello to someone.",
        parameters=[],
        inputs=[],
        outputs=[
            IOField.build_from(
                "Output value", "value", str, description="The output value"
            )
        ],
    )

    def __init__(self, **kwargs):
        """Create a new FinReportJoinOperator."""
        super().__init__(join_func, can_skip_in_branch=False, **kwargs)
