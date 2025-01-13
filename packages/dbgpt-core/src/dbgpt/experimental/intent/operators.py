"""Operators for intent detection."""

from typing import Dict, List, Optional, cast

from dbgpt.core import ModelMessage, ModelRequest, ModelRequestContext
from dbgpt.core.awel import BranchFunc, BranchOperator, BranchTaskType, MapOperator
from dbgpt.model.operators.llm_operator import MixinLLMOperator

from .base import BaseIntentDetection, IntentDetectionResponse


class IntentDetectionOperator(
    MixinLLMOperator, BaseIntentDetection, MapOperator[ModelRequest, ModelRequest]
):
    """The intent detection operator."""

    def __init__(
        self,
        intent_definitions: str,
        prompt_template: Optional[str] = None,
        response_format: Optional[str] = None,
        examples: Optional[str] = None,
        **kwargs,
    ):
        """Create the intent detection operator."""
        MixinLLMOperator.__init__(self)
        MapOperator.__init__(self, **kwargs)
        BaseIntentDetection.__init__(
            self,
            intent_definitions=intent_definitions,
            prompt_template=prompt_template,
            response_format=response_format,
            examples=examples,
        )

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Detect the intent.

        Merge the intent detection result into the context.
        """
        language = "en"
        if self.system_app:
            language = self.system_app.config.get_current_lang()
        messages = self.parse_messages(input_value)
        ic = await self.detect_intent(
            messages,
            input_value.model,
            language=language,
        )
        if not input_value.context:
            input_value.context = ModelRequestContext()
        if not input_value.context.extra:
            input_value.context.extra = {}
        input_value.context.extra["intent_detection"] = ic
        return input_value

    def parse_messages(self, request: ModelRequest) -> List[ModelMessage]:
        """Parse the messages from the request."""
        return request.get_messages()


class IntentDetectionBranchOperator(BranchOperator[ModelRequest, ModelRequest]):
    """The intent detection branch operator."""

    def __init__(self, end_task_name: str, **kwargs):
        """Create the intent detection branch operator."""
        super().__init__(**kwargs)
        self._end_task_name = end_task_name

    async def branches(
        self,
    ) -> Dict[BranchFunc[ModelRequest], BranchTaskType]:
        """Branch the intent detection result to different tasks."""
        download_task_names = set(task.node_name for task in self.downstream)  # noqa
        branch_func_map = {}
        for task_name in download_task_names:

            def check(r: ModelRequest, outer_task_name=task_name):
                if not r.context or not r.context.extra:
                    return False
                ic_result = r.context.extra.get("intent_detection")
                if not ic_result:
                    return False
                ic: IntentDetectionResponse = cast(IntentDetectionResponse, ic_result)
                if ic.has_empty_slot():
                    return self._end_task_name == outer_task_name
                else:
                    return outer_task_name == ic.task_name

            branch_func_map[check] = task_name

        return branch_func_map  # type: ignore
