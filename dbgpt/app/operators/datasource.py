import json
import logging
from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.agent.resource.database import DBResource
from dbgpt.core import Chunk
from dbgpt.core.awel import DAGContext, MapOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    IOField,
    OperatorCategory,
    Parameter,
    ViewMetadata,
    ui,
)
from dbgpt.core.operators import BaseLLM
from dbgpt.util.i18n_utils import _
from dbgpt.vis.tags.vis_chart import default_chart_type_prompt

from .llm import HOContextBody

logger = logging.getLogger(__name__)

CFG = Config()

_DEFAULT_CHART_TYPE = default_chart_type_prompt()

_DEFAULT_TEMPLATE_EN = """You are a database expert. 
Please answer the user's question based on the database selected by the user and some \
of the available table structure definitions of the database.
Database name:
     {db_name}
Table structure definition:
     {table_info}

Constraint:
    1.Please understand the user's intention based on the user's question, and use the \
    given table structure definition to create a grammatically correct {dialect} sql. \
    If sql is not required, answer the user's question directly.. 
    2.Always limit the query to a maximum of {max_num_results} results unless the user \
    specifies in the question the specific number of rows of data he wishes to obtain.
    3.You can only use the tables provided in the table structure information to \
    generate sql. If you cannot generate sql based on the provided table structure, \
    please say: "The table structure information provided is not enough to generate \
    sql queries." It is prohibited to fabricate information at will.
    4.Please be careful not to mistake the relationship between tables and columns \
    when generating SQL.
    5.Please check the correctness of the SQL and ensure that the query performance is \
    optimized under correct conditions.
    6.Please choose the best one from the display methods given below for data \
    rendering, and put the type name into the name parameter value that returns the \
    required format. If you cannot find the most suitable one, use 'Table' as the \
    display method. , the available data display methods are as follows: {display_type}

User Question:
    {user_input}
Please think step by step and respond according to the following JSON format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads.
"""

_DEFAULT_TEMPLATE_ZH = """你是一个数据库专家. 
请根据用户选择的数据库和该库的部分可用表结构定义来回答用户问题.
数据库名:
    {db_name}
表结构定义:
    {table_info}

约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的 {dialect} sql，如果不需要 \
    sql，则直接回答用户问题。
    2. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多 {max_num_results} \
    个结果。
    3. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：\
    “提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
    4. 请注意生成SQL时不要弄错表和列的关系
    5. 请检查SQL的正确性，并保证正确的情况下优化查询性能
    6.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种\
    ，如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下: {display_type}
用户问题:
    {user_input}
请一步步思考并按照以下JSON格式回复：
      {response}
确保返回正确的json并且可以被Python json.loads方法解析.
"""
_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

_DEFAULT_RESPONSE = json.dumps(
    {
        "thoughts": "thoughts summary to say to user",
        "sql": "SQL Query to run",
        "display_type": "Data display method",
    },
    ensure_ascii=False,
    indent=4,
)

_PARAMETER_DATASOURCE = Parameter.build_from(
    _("Datasource"),
    "datasource",
    type=DBResource,
    description=_("The datasource to retrieve the context"),
)
_PARAMETER_PROMPT_TEMPLATE = Parameter.build_from(
    _("Prompt Template"),
    "prompt_template",
    type=str,
    optional=True,
    default=_DEFAULT_TEMPLATE,
    description=_("The prompt template to build a database prompt"),
    ui=ui.DefaultUITextArea(),
)
_PARAMETER_DISPLAY_TYPE = Parameter.build_from(
    _("Display Type"),
    "display_type",
    type=str,
    optional=True,
    default=_DEFAULT_CHART_TYPE,
    description=_("The display type for the data"),
    ui=ui.DefaultUITextArea(),
)
_PARAMETER_MAX_NUM_RESULTS = Parameter.build_from(
    _("Max Number of Results"),
    "max_num_results",
    type=int,
    optional=True,
    default=50,
    description=_("The maximum number of results to return"),
)
_PARAMETER_RESPONSE_FORMAT = Parameter.build_from(
    _("Response Format"),
    "response_format",
    type=str,
    optional=True,
    default=_DEFAULT_RESPONSE,
    description=_("The response format, default is a JSON format"),
    ui=ui.DefaultUITextArea(),
)

_PARAMETER_CONTEXT_KEY = Parameter.build_from(
    _("Context Key"),
    "context_key",
    type=str,
    optional=True,
    default="context",
    description=_("The key of the context, it will be used in building the prompt"),
)
_INPUTS_QUESTION = IOField.build_from(
    _("User question"),
    "query",
    str,
    description=_("The user question to retrieve table schemas from the datasource"),
)
_OUTPUTS_CONTEXT = IOField.build_from(
    _("Retrieved context"),
    "context",
    HOContextBody,
    description=_("The retrieved context from the datasource"),
)

_INPUTS_SQL_DICT = IOField.build_from(
    _("SQL dict"),
    "sql_dict",
    dict,
    description=_("The SQL to be executed wrapped in a dictionary, generated by LLM"),
)
_OUTPUTS_SQL_RESULT = IOField.build_from(
    _("SQL result"),
    "sql_result",
    str,
    description=_("The result of the SQL execution"),
)

_INPUTS_SQL_DICT_LIST = IOField.build_from(
    _("SQL dict list"),
    "sql_dict_list",
    dict,
    description=_(
        "The SQL list to be executed wrapped in a dictionary, generated by LLM"
    ),
    is_list=True,
)


class GPTVisMixin:
    async def save_view_message(self, dag_ctx: DAGContext, view: str):
        """Save the view message."""
        await dag_ctx.save_to_share_data(BaseLLM.SHARE_DATA_KEY_MODEL_OUTPUT_VIEW, view)


class HODatasourceRetrieverOperator(MapOperator[str, HOContextBody]):
    """Retrieve the table schemas from the datasource."""

    _share_data_key = "__datasource_retriever_chunks__"

    class ChunkMapper(MapOperator[HOContextBody, List[Chunk]]):
        async def map(self, context: HOContextBody) -> List[Chunk]:
            schema_info = await self.current_dag_context.get_from_share_data(
                HODatasourceRetrieverOperator._share_data_key
            )
            if isinstance(schema_info, list):
                chunks = [Chunk(content=table_info) for table_info in schema_info]
            else:
                chunks = [Chunk(content=schema_info)]
            return chunks

    metadata = ViewMetadata(
        label=_("Datasource Retriever Operator"),
        name="higher_order_datasource_retriever_operator",
        description=_("Retrieve the table schemas from the datasource."),
        category=OperatorCategory.DATABASE,
        parameters=[
            _PARAMETER_DATASOURCE.new(),
            _PARAMETER_PROMPT_TEMPLATE.new(),
            _PARAMETER_DISPLAY_TYPE.new(),
            _PARAMETER_MAX_NUM_RESULTS.new(),
            _PARAMETER_RESPONSE_FORMAT.new(),
            _PARAMETER_CONTEXT_KEY.new(),
        ],
        inputs=[_INPUTS_QUESTION.new()],
        outputs=[
            _OUTPUTS_CONTEXT.new(),
            IOField.build_from(
                _("Retrieved schema chunks"),
                "chunks",
                Chunk,
                is_list=True,
                description=_("The retrieved schema chunks from the datasource"),
                mappers=[ChunkMapper],
            ),
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        datasource: DBResource,
        prompt_template: str = _DEFAULT_TEMPLATE,
        display_type: str = _DEFAULT_CHART_TYPE,
        max_num_results: int = 50,
        response_format: str = _DEFAULT_RESPONSE,
        context_key: Optional[str] = "context",
        **kwargs,
    ):
        """Initialize the operator."""
        super().__init__(**kwargs)
        self._datasource = datasource
        self._prompt_template = prompt_template
        self._display_type = display_type
        self._max_num_results = max_num_results
        self._response_format = response_format
        self._context_key = context_key

    async def map(self, question: str) -> HOContextBody:
        """Retrieve the context from the datasource."""
        db_name = self._datasource._db_name
        dialect = self._datasource.dialect
        schema_info = await self.blocking_func_to_async(
            self._datasource.get_schema_link,
            db=db_name,
            question=question,
        )
        await self.current_dag_context.save_to_share_data(
            self._share_data_key, schema_info
        )
        context = self._prompt_template.format(
            db_name=db_name,
            table_info=schema_info,
            dialect=dialect,
            max_num_results=self._max_num_results,
            display_type=self._display_type,
            user_input=question,
            response=self._response_format,
        )

        return HOContextBody(
            context_key=self._context_key,
            context=context,
        )


class HODatasourceExecutorOperator(GPTVisMixin, MapOperator[dict, str]):
    """Execute the context from the datasource."""

    metadata = ViewMetadata(
        label=_("Datasource Executor Operator"),
        name="higher_order_datasource_executor_operator",
        description=_("Execute the context from the datasource."),
        category=OperatorCategory.DATABASE,
        parameters=[_PARAMETER_DATASOURCE.new()],
        inputs=[_INPUTS_SQL_DICT.new()],
        outputs=[_OUTPUTS_SQL_RESULT.new()],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, datasource: DBResource, **kwargs):
        """Initialize the operator."""
        MapOperator.__init__(self, **kwargs)
        self._datasource = datasource

    async def map(self, sql_dict: dict) -> str:
        """Execute the context from the datasource."""
        from dbgpt.vis.tags.vis_chart import VisChart

        if not isinstance(sql_dict, dict):
            raise ValueError(
                "The input value of datasource executor should be a dictionary."
            )
        vis = VisChart()
        sql = sql_dict.get("sql")
        if not sql:
            return sql_dict.get("thoughts", "No SQL found in the input dictionary.")
        data_df = await self._datasource.query_to_df(sql)
        view = await vis.display(chart=sql_dict, data_df=data_df)
        await self.save_view_message(self.current_dag_context, view)
        return view


class HODatasourceDashboardOperator(GPTVisMixin, MapOperator[dict, str]):
    """Execute the context from the datasource."""

    metadata = ViewMetadata(
        label=_("Datasource Dashboard Operator"),
        name="higher_order_datasource_dashboard_operator",
        description=_("Execute the context from the datasource."),
        category=OperatorCategory.DATABASE,
        parameters=[_PARAMETER_DATASOURCE.new()],
        inputs=[_INPUTS_SQL_DICT_LIST.new()],
        outputs=[_OUTPUTS_SQL_RESULT.new()],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(self, datasource: DBResource, **kwargs):
        """Initialize the operator."""
        MapOperator.__init__(self, **kwargs)
        self._datasource = datasource

    async def map(self, sql_dict_list: List[dict]) -> str:
        """Execute the context from the datasource."""
        from dbgpt.vis.tags.vis_dashboard import VisDashboard

        if not isinstance(sql_dict_list, list):
            raise ValueError(
                "The input value of datasource executor should be a list of dictionaries."
            )
        vis = VisDashboard()
        chart_params = []
        for chart_item in sql_dict_list:
            chart_dict = {k: v for k, v in chart_item.items()}
            sql = chart_item.get("sql")
            try:
                data_df = await self._datasource.query_to_df(sql)
                chart_dict["data"] = data_df
            except Exception as e:
                logger.warning(f"Sql execute failed！{str(e)}")
                chart_dict["err_msg"] = str(e)
            chart_params.append(chart_dict)
        view = await vis.display(charts=chart_params)
        await self.save_view_message(self.current_dag_context, view)
        return view
