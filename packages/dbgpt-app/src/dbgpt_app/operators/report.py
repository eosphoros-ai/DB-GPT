from functools import cache
from typing import Optional

from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    LLMClient,
    ModelMessage,
    SystemPromptTemplate,
)
from dbgpt.core.awel import JoinOperator
from dbgpt.core.awel.flow.base import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    Parameter,
    ViewMetadata,
)
from dbgpt.core.interface.llm import ModelRequest
from dbgpt.model.operators import MixinLLMOperator
from dbgpt.util.i18n_utils import _
from dbgpt_app.operators.datasource import GPTVisMixin

_DEFAULT_PROMPT_EN = """You are a helpful AI assistant.

Please carefully read the data in the Markdown table format below, the data is a 
database query result based on the user question. Please analyze and summarize the 
data carefully, and provide a summary report in markdown format.

<data-report>
{data_report}
</data-report>

user question:
{user_input}

Please answer in the same language as the user's question.
"""

_DEFAULT_PROMPT_ZH = """你是一个有用的AI助手。

请你仔细阅读下面的 Markdown 表格格式的数据，这是一份根据用户问题查询到的数据库的数据，\
你需要根据数据仔细分析和总结，给出一份总结报告，使用 markdown 格式输出。

<data-report>
{data_report}
</data-report>

用户的问题:
{user_input}

请用用户提问的语言回答。
"""

_DEFAULT_USER_PROMPT = """\
{user_input}
"""


@cache
def _get_default_prompt(language: str) -> ChatPromptTemplate:
    if language == "zh":
        sys_prompt = _DEFAULT_PROMPT_ZH
        user_prompt = _DEFAULT_USER_PROMPT
    else:
        sys_prompt = _DEFAULT_PROMPT_EN
        user_prompt = _DEFAULT_USER_PROMPT

    return ChatPromptTemplate(
        messages=[
            SystemPromptTemplate.from_template(sys_prompt),
            HumanPromptTemplate.from_template(user_prompt),
        ]
    )


class ReportAnalystOperator(MixinLLMOperator, JoinOperator[str]):
    metadata = ViewMetadata(
        label=_("Report Analyst"),
        name="report_analyst",
        description=_("Report Analyst"),
        category=OperatorCategory.DATABASE,
        tags={"order": TAGS_ORDER_HIGH},
        parameters=[
            Parameter.build_from(
                _("Prompt Template"),
                "prompt_template",
                ChatPromptTemplate,
                description=_("The prompt template for the conversation."),
                optional=True,
                default=None,
            ),
            Parameter.build_from(
                _("Model Name"),
                "model",
                str,
                optional=True,
                default=None,
                description=_("The model name."),
            ),
            Parameter.build_from(
                _("LLM Client"),
                "llm_client",
                LLMClient,
                optional=True,
                default=None,
                description=_(
                    "The LLM Client, how to connect to the LLM model, if not provided,"
                    " it will use the default client deployed by DB-GPT."
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("User question"),
                "question",
                str,
                description=_("The question of user"),
            ),
            IOField.build_from(
                _("The data report"),
                "data_report",
                str,
                _("The data report in markdown format."),
                dynamic=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Report Analyst Result"),
                "report_analyst_result",
                str,
                description=_("The report analyst result."),
            )
        ],
    )

    def __init__(
        self,
        prompt_template: Optional[ChatPromptTemplate] = None,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        **kwargs,
    ):
        JoinOperator.__init__(self, combine_function=self._join_func, **kwargs)
        MixinLLMOperator.__init__(self, llm_client=llm_client, **kwargs)

        # User must select a history merge mode
        self._prompt_template = prompt_template
        self._model = model

    @property
    def prompt_template(self) -> ChatPromptTemplate:
        """Get the prompt template."""
        language = "en"
        if self.system_app:
            language = self.system_app.config.get_current_lang()
        if self._prompt_template is None:
            return _get_default_prompt(language)
        return self._prompt_template

    async def _join_func(self, question: str, data_report: str, *args):
        dynamic_inputs = [data_report]
        for arg in args:
            if isinstance(arg, str):
                dynamic_inputs.append(arg)
        data_report = "\n".join(dynamic_inputs)
        messages = self.prompt_template.format_messages(
            user_input=question,
            data_report=data_report,
        )
        model_messages = ModelMessage.from_base_messages(messages)
        models = await self.llm_client.models()
        if not models:
            raise Exception("No models available.")
        model = self._model or models[0].model

        model_request = ModelRequest.build_request(model, messages=model_messages)
        model_output = await self.llm_client.generate(model_request)
        text = model_output.gen_text_with_thinking()

        return text


class StringJoinOperator(GPTVisMixin, JoinOperator[str]):
    """Join operator for strings.
    This operator joins the input strings with a specified separator.
    """

    metadata = ViewMetadata(
        label=_("String Join Operator"),
        name="string_join_operator",
        description=_("Merge multiple inputs into a single string."),
        category=OperatorCategory.COMMON,
        parameters=[
            Parameter.build_from(
                _("Separator"),
                "separator",
                str,
                optional=True,
                default="\n\n",
                description=_("The separator to join the strings."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Input Strings"),
                "input_strings",
                str,
                description=_("The input strings to join."),
                dynamic=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Joined String"),
                "joined_string",
                str,
                description=_("The joined string."),
            )
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, separator: str = "\n\n", **kwargs):
        super().__init__(combine_function=self._join_func, **kwargs)
        self.separator = separator

    async def _join_func(self, *args) -> str:
        """Join the strings with the separator."""
        view = self.separator.join(args)
        await self.save_view_message(self.current_dag_context, view)
        return view
