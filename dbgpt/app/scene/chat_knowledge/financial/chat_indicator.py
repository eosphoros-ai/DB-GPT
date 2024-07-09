"""The ChatDatabaseOperator."""
import json

from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    ModelMessage,
    ModelOutput,
    ModelRequest,
    SQLOutputParser,
    SystemPromptTemplate,
)
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.rag.extractor.fin_report import FinReportIntent
from dbgpt.util.i18n_utils import _

_DEFAULT_TEMPLATE_EN = """You are a database expert. Please answer the user's question 
based on the database selected by the user and some of the available table structure 
definitions of the database.
Database name:
     {db_name}
Table structure definition:
     {table_info}
indicator calculate rule definition:
     {indicator}

Constraint:
1.Please understand the user's intention based on the user's question, and use the 
given table structure definition to create a grammatically correct {dialect} sql. 
If sql is not required, answer the user's question directly.. 
2.Always limit the query to a maximum of {top_k} results unless the user specifies 
in the question the specific number of rows of data he wishes to obtain.
3.You can only use the tables provided in the table structure information to 
generate sql. If you cannot generate sql based on the provided table structure, 
please say: "The table structure information provided is not enough to generate 
sql queries." It is prohibited to fabricate information at will.
4.Please be careful not to mistake the relationship between tables and columns 
when generating SQL.
5.Please check the correctness of the SQL and ensure that the query performance 
is optimized under correct conditions.
6.Please choose the best one from the display methods given below for data 
rendering, and put the type name into the name parameter value that returns the 
required format. If you cannot find the most suitable one, use 'Table' as the 
display method. , the available data display methods are as follows: {display_type}

User Question:
    {user_input}
Please think step by step and respond according to the following JSON format:
    {response}
Ensure the response is correct json and can be parsed by Python json.loads.

"""

_DEFAULT_TEMPLATE_ZH = """你是一个数据库专家.
请根据用户选择的数据库和该库的部分可用表结构和财务指标规则来回答用户问题.
数据库名:
    {db_name}
表结构定义:
    {table_info}
财务指标计算公式:
    {indicator}
约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的 {dialect} sql，如果不需要sql，
    则直接回答用户问题。
    2. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多 {top_k} 个结果。
    3. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：
    “提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
    4. 请注意生成SQL时不要弄错表和列的关系
    5. 请检查SQL的正确性，并保证正确的情况下优化查询性能
    6.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种，
    如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下: {display_type}
用户问题:
    {user_input}
请一步步思考并按照以下JSON格式回复：
      {response}
确保返回正确的json并且可以被Python json.loads方法解析.

"""

fin_indicator_map = {
    "营业成本率": {"公式": "营业成本率=CAST(营业成本)/CAST(营业收入)", "数值": ["营业成本", "营业收入"]},
    "投资收益占营业收入比率": {"公式": "投资收益占营业收入比率=CAST(投资收益)/CAST(营业收入)", "数值": ["投资收益", "营业收入"]},
    "管理费用率": {"公式": "管理费用率=CAST(管理费用)/CAST(营业收入)", "数值": ["管理费用", "营业收入"]},
    "财务费用率": {"公式": "财务费用率=CAST(财务费用)/CAST(营业收入)", "数值": ["财务费用", "营业收入"]},
    "三费比重": {
        "公式": "三费比重=(CAST(销售费用+管理费用+财务费用))/营业收入",
        "数值": ["销售费用", "管理费用", "财务费用", "营业收入"],
    },
    "企业研发经费占费用比例": {
        "公式": "企业研发经费占费用比例=CAST(研发费用)/CAST((销售费用+财务费用+管理费用+研发费用))",
        "数值": ["研发费用", "销售费用", "财务费用", "管理费用"],
    },
    "企业研发经费与利润比值": {"公式": "企业研发经费与利润比值=CAST(研发费用)/CAST(净利润)", "数值": ["研发费用", "净利润"]},
    "企业研发经费与营业收入比值": {
        "公式": "企业研发经费与营业收入比值=CAST(研发费用)/CAST(营业收入)",
        "数值": ["研发费用", "营业收入"],
    },
    "销售人员占比": {"公式": "销售人员占比=销售人员/职工总数", "数值": ["销售人员", "职工总数"]},
    "行政人员占比": {"公式": "行政人员占比=行政人员/职工总数", "数值": ["行政人员", "职工总数"]},
    "财务人员占比": {"公式": "财务人员占比=财务人员/职工总数", "数值": ["财务人员", "职工总数"]},
    "生产人员占比": {"公式": "生产人员占比=生产人员员/职工总数", "数值": ["生产人员", "职工总数"]},
    "技术人员占比": {"公式": "技术人员占比=技术人员/职工总数", "数值": ["技术人员", "职工总数"]},
    "研发人员占职工人数比例": {
        "公式": "研发人员占职工人数比例=研发人数/职工总数",
        "数值": ["研发人数", "职工总数"],
    },
    "企业硕士及以上人员占职工人数比例": {
        "公式": "企业硕士及以上人员占职工人数比例=(硕士人员 + 博士及以上人员)/职工总数",
        "数值": ["硕士人员", "博士及以上人员", "职工总数"],
    },
    "毛利率": {"公式": "毛利率=(CAST(营业收入)-CAST(营业成本))/CAST(营业收入)", "数值": ["营业收入", "营业成本"]},
    "营业利润率": {"公式": "营业利润率=CAST(营业利润)/CAST(营业收入)", "数值": ["营业利润", "营业收入"]},
    "流动比率": {"公式": "流动比率=CAST(流动资产合计)/CAST(流动负债合计)", "数值": ["流动资产合计", "流动负债合计"]},
    "速动比率": {
        "公式": "速动比率=(CAST(流动资产合计)-CAST(存货))/CAST(流动负债合计)",
        "数值": ["流动资产合计", "存货", "流动负债合计"],
    },
    "资产负债比率": {"公式": "资产负债比率=CAST(负债合计)/CAST(资产总计)", "数值": ["负债合计", "资产总计"]},
    "现金比率": {"公式": "现金比率=CAST(货币资金)/CAST(流动负债合计)", "数值": ["货币资金", "流动负债合计"]},
    "非流动负债合计比率": {
        "公式": "非流动负债合计比率=CAST(非流动负债合计)/CAST(负债合计)",
        "数值": ["非流动负债合计", "负债合计"],
    },
    "流动负债合计比率": {"公式": "流动负债合计比率=CAST(流动负债合计)/CAST(负债合计)", "数值": ["流动负债合计", "负债合计"]},
    "净利润率": {"公式": "净利润率=CAST(净利润)/CAST(营业收入)", "数值": ["净利润", "营业收入"]},
}

_SHARE_DATA_DATABASE_NAME_KEY = "__database_name__"


class ChatIndicatorOperator(MapOperator[ModelRequest, ModelRequest]):
    """The ChatDataOperator."""

    metadata = ViewMetadata(
        label=_("Chat Indicator Operator"),
        name="chat_indicator_operator",
        category=OperatorCategory.EXPERIMENTAL,
        description=_(_("Chat Indicator Operator.")),
        inputs=[
            IOField.build_from(
                _("input_value"),
                "input_value",
                ModelRequest,
                _("user question."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("model request"),
                "model_request",
                ModelRequest,
                description=_("model request."),
            )
        ],
        parameters=[
            Parameter.build_from(
                label=_("conn_datasource"),
                name="conn_datasource",
                type=str,
                optional=True,
                default=None,
                description=_("conn_datasource."),
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        task_name="chat_indicator",
        db_name: str = None,
        conn_datasource=None,
        intent: FinReportIntent = None,
        **kwargs,
    ):
        """Create a new ChatDataOperator."""
        self._conn_datasource = conn_datasource
        self._intent = intent
        from dbgpt._private.config import Config

        cfg = Config()

        self._db_name = db_name
        if not self._db_name:
            raise ValueError("Database name is required.")

        self._database = (
            cfg.local_db_manager.get_connector(self._db_name) or self._conn_datasource
        )
        company_df = self._database.run_to_df(f"select 公司名称_x from fin_report")
        self._company_list = [
            item[0] for item in company_df.values.tolist() if item is not None
        ]
        super().__init__(task_name=task_name, **kwargs)

    async def map(self, input_value: ModelRequest) -> ModelRequest:
        """Map the input value to the output value."""
        from dbgpt.rag.summary.db_summary_client import DBSummaryClient
        from dbgpt.vis.tags.vis_chart import default_chart_type_prompt

        await self.current_dag_context.save_to_share_data(
            _SHARE_DATA_DATABASE_NAME_KEY, self._db_name
        )
        client = DBSummaryClient(system_app=self.system_app)
        user_input = input_value.messages[-1].content
        if self._intent.company:
            from fuzzywuzzy import process

            best_match, confidence = process.extractOne(
                self._intent.company, self._company_list
            )
            hit_company = best_match or self._intent.company
            new_query = user_input.replace(self._intent.company, hit_company)
            user_input = new_query
        indicator = ""
        if self._intent.intent:
            intent_list = list(fin_indicator_map.keys())
            from fuzzywuzzy import process

            best_match, confidence = process.extractOne(
                self._intent.intent, intent_list
            )
            hit_indicator = best_match or self._intent.intent
            indicator = fin_indicator_map.get(hit_indicator)

        table_infos = await self.blocking_func_to_async(
            client.get_db_summary, self._db_name, user_input, 5
        )

        input_values = {
            "db_name": self._db_name,
            "user_input": user_input,
            "top_k": 5,
            "dialect": self._database.dialect,
            "table_info": table_infos,
            "indicator": indicator.get("公式"),
            "display_type": default_chart_type_prompt(),
        }

        response_format_simple = {
            "thoughts": "thoughts summary to say to user",
            "sql": "SQL Query to run",
            "display_type": "Data display method",
        }

        user_language = self.system_app.config.get_current_lang(default="en")
        prompt_template = (
            _DEFAULT_TEMPLATE_EN if user_language == "en" else _DEFAULT_TEMPLATE_ZH
        )
        prompt = ChatPromptTemplate(
            messages=[
                SystemPromptTemplate.from_template(
                    prompt_template,
                    response_format=json.dumps(
                        response_format_simple, ensure_ascii=False, indent=4
                    ),
                ),
                HumanPromptTemplate.from_template("{user_input}"),
            ]
        )

        messages = prompt.format_messages(**input_values)
        model_messages = ModelMessage.from_base_messages(messages)
        request = input_value.copy()
        request.messages = model_messages
        return request


class ChatDatabaseOutputParserOperator(SQLOutputParser):
    """ChatDatabaseOutputParserOperator."""

    metadata = ViewMetadata(
        label=_("Chat Data Output Operator"),
        name="chat_data_out_parser_operator",
        category=OperatorCategory.EXPERIMENTAL,
        description=_(_("Chat Data Output Operator.")),
        inputs=[
            IOField.build_from(
                _("model output"),
                "model_output",
                ModelOutput,
                description=_("model output."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("dict"),
                "dict",
                dict,
                description=_("dict."),
            )
        ],
        parameters=[],
        documentation_url="https://github.com/openai/openai-python",
    )

    async def map(self, input_value: ModelOutput) -> dict:
        """Map the input value to the output value."""
        return self.parse_model_nostream_resp(input_value, "#########")


class ChatDatabaseChartOperator(MapOperator[dict, str]):
    """The ChatDatabaseChartOperator."""

    metadata = ViewMetadata(
        label=_("Chat Data Chart Operator"),
        name="chat_data_chart_operator",
        category=OperatorCategory.EXPERIMENTAL,
        description=_(_("Chat Data Output Operator.")),
        inputs=[
            IOField.build_from(
                _("dict"),
                "dict",
                dict,
                description=_("dict."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("str"),
                "str",
                str,
                description=_("dict."),
            )
        ],
        parameters=[],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(self, task_name="chat_database_parser", **kwargs):
        """Create a new ChatDatabaseChartOperator."""
        super().__init__(task_name=task_name, **kwargs)

    async def map(self, input_value: dict) -> str:
        """Map the input value to the output value."""
        from dbgpt._private.config import Config
        from dbgpt.datasource import RDBMSConnector
        from dbgpt.vis.tags.vis_chart import VisChart

        db_name = await self.current_dag_context.get_from_share_data(
            _SHARE_DATA_DATABASE_NAME_KEY
        )
        vis = VisChart()
        cfg = Config()
        database: RDBMSConnector = cfg.local_db_manager.get_connector(db_name)
        sql = input_value.get("sql")
        data_df = await self.blocking_func_to_async(database.run_to_df, sql)
        view = await vis.display(chart=input_value, data_df=data_df)
        return view
