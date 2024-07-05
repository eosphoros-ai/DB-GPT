"""The Question Classifier Operator."""
from enum import Enum
from typing import Dict, Optional

import joblib
import torch
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer

from dbgpt.core import ModelRequest
from dbgpt.core.awel import BranchFunc, BranchOperator, BranchTaskType, MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.awel.task.base import IN, OUT
from dbgpt.util.i18n_utils import _


class FinQuestionClassifierType(Enum):
    ANALYSIS = "报告解读分析"
    BASE_INFO = "年报基础信息问答"
    FINANCIAL_INDICATOR = "财务指标计算"
    GLOSSARY = "专业名称解释"
    COMPARISON = "统计对比"

    @classmethod
    def get_by_value(cls, value: str):
        """Get the enum member by value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"{value} is not a valid value for {cls.__name__}")


class QuestionClassifierOperator(MapOperator[IN, OUT]):
    """The Question Classifier Operator."""

    metadata = ViewMetadata(
        label=_("Question Classifier Operator"),
        name="question_classifier_operator",
        category=OperatorCategory.EXPERIMENTAL,
        description=_(_("Question Classifier Operator.")),
        inputs=[
            IOField.build_from(
                _("Question"),
                "question",
                ModelRequest,
                _("user question."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("prediction"),
                "prediction",
                ModelRequest,
                description=_("classifier prediction."),
            )
        ],
        parameters=[
            Parameter.build_from(
                label=_("model"),
                name="model",
                type=str,
                optional=True,
                default=None,
                description=_("model."),
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(self, model: str = None, classifier_pkl: str = None, **kwargs):
        """Create a new Question Classifier Operator."""
        if not model:
            raise ValueError("model must be provided")
        if not classifier_pkl:
            raise ValueError("classifier_pkl must be provided")
        self._model = model
        self._pretrained_model = AutoModel.from_pretrained(self._model)
        self._tokenizer = AutoTokenizer.from_pretrained(self._model)
        self._pkl = classifier_pkl
        self._batch_size = 4
        super().__init__(**kwargs)

    async def map(self, request: ModelRequest) -> ModelRequest:
        """Map the user question to a financial."""
        clf_loaded = joblib.load(self._pkl)
        messages = request.messages
        question = [message.content for message in messages]
        new_text = question
        new_embedding = self._get_sentence_embeddings(new_text).numpy()
        prediction = clf_loaded.predict(new_embedding)
        classifiers = FinQuestionClassifierType.get_by_value(prediction[0])
        if not request.context.extra:
            request.context.extra = {}
        request.context.extra["classifier"] = classifiers
        return request

    def _get_sentence_embeddings(self, sentences):
        embeddings = []
        for i in tqdm(
            range(0, len(sentences), self._batch_size), desc="Generating Embeddings"
        ):
            batch = sentences[i : i + self._batch_size]
            encoded_input = self._tokenizer(
                batch, padding=True, truncation=True, return_tensors="pt"
            )
            with torch.no_grad():
                model_output = self._pretrained_model(**encoded_input)
                sentence_embeddings = model_output[0][:, 0]
                sentence_embeddings = torch.nn.functional.normalize(
                    sentence_embeddings, p=2, dim=1
                )
                embeddings.append(sentence_embeddings)
        return torch.cat(embeddings)


class QuestionClassifierBranchOperator(BranchOperator[ModelRequest, ModelRequest]):
    """The intent detection branch operator."""

    def __init__(self, **kwargs):
        """Create the intent detection branch operator."""
        super().__init__(**kwargs)
        # self._end_task_name = end_task_name

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
                classifier = r.context.extra.get("classifier")
                if not classifier:
                    return False
                if classifier == FinQuestionClassifierType.FINANCIAL_INDICATOR:
                    return outer_task_name == "chat_indicator"
                else:
                    return outer_task_name == "chat_knowledge"

            branch_func_map[check] = task_name
        return branch_func_map  # type: ignore
