from dbgpt._private.config import Config
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)
from dbgpt_app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt_app.scene.chat_data.chat_excel.excel_analyze.out_parser import (
    ChatExcelOutputParser,
)

CFG = Config()

_PROMPT_SCENE_DEFINE_EN = "You are a data analysis expert. "

_DEFAULT_TEMPLATE_EN = """
The user has a table file data to be analyzed, which has already been imported into a \
DuckDB table. \
A sample of the data is as follows:
``````json
{data_example}
``````
The DuckDB table structure information is as follows:
{table_schema}
For DuckDB, please pay special attention to the following DuckDB syntax rules:
``````markdown
### When using GROUP BY in DuckDB SQL queries, note these key points:
1. Any non-aggregate columns that appear in the SELECT clause must also appear in the \
GROUP BY clause
2. When referencing a column in ORDER BY or window functions, ensure that column has \
been properly selected in the preceding CTE or query
3. When building multi-layer CTEs, ensure column reference consistency between layers, \
especially for columns used in sorting and joining
4. If a column doesn't need an exact value, you can use the ANY_VALUE() function as an \
alternative
``````
Based on the data structure information provided, please answer the user's questions \
through DuckDB SQL data analysis while meeting the following constraints.
Constraints:
	1. Please fully understand the user's question and analyze it using DuckDB SQL. \
	Return the analysis content according to the output format required below, with \
    the SQL output in the corresponding SQL parameter
	2. Please select the most optimal way from the display methods given below for \
	data rendering, and put the type name in the name parameter value of the required \
	return format. If you cannot find the most suitable one, use 'Table' as the \
	display method. Available data display methods are: {display_type}
	3. The table name to be used in the SQL is: {table_name}. Please check your \
	generated SQL and do not use column names that are not in the data structure
	4. Prioritize using data analysis methods to answer. If the user's question does \
	not involve data analysis content, you can answer based on your understanding
	5. Convert the SQL part in the output content to: \
	<api-call><name>[display method]</name><args><sql>\
	[correct duckdb data analysis sql]</sql></args></api-call> \
	format, refer to the return format requirements

Please think step by step, provide an answer, and ensure your answer format is as \
follows:
    [Summary of what the user wants]\
    <api-call><name>[display method]</name><args>\
    <sql>[correct duckdb data analysis sql]</sql></args></api-call>
You can refer to the examples below:
Example 1:
user: 分析各地区的销售额和利润，需要显示地区名称、总销售额、\
总利润以及平均利润率（利润/销售额）。
assistant: [分析思路]  
1. 需要识别查询核心维度(地区)和指标(销售额、利润、利润率)  
2. 利润率计算需在聚合后计算，避免分母错误  
3. 过滤空地区保证数据准确性  
4. 按销售额降序排列方便业务解读
<api-call><name>response_table</name><args><sql>
SELECT region AS 地区,
       SUM(sales) AS 总销售额,
       SUM(profit) AS 总利润,
       SUM(profit)/NULLIF(SUM(sales),0) AS 利润率
FROM sales_records
WHERE region IS NOT NULL
GROUP BY region
ORDER BY 总销售额 DESC;
</sql></args></api-call>

Example 2:
user: Show monthly sales trend for the last 2 years, including year-month, total 
orders and average order value.
assistant:
[Analysis Insights]  
1. Time range handling: Use DATE_TRUNC for monthly granularity  
2. Calculate rolling 24-month period dynamically  
3. Order date sorting ensures chronological trend  
4. NULL order_date filtering for data integrity
<api-call><name>response_table</name><args><sql>
SELECT 
  DATE_TRUNC('month', order_date)::DATE AS year_month,
  COUNT(DISTINCT order_id) AS order_count,
  AVG(order_value) AS avg_order_value
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '2 years'
  AND order_date IS NOT NULL
GROUP BY 1
ORDER BY year_month ASC;
</sql></args></api-call>
Note that the answer must conform to the <api-call> format! Please answer in the same \
language as the user's question!
User question: {user_input}
"""

_PROMPT_SCENE_DEFINE_ZH = """你是一个数据分析专家！"""
_DEFAULT_TEMPLATE_ZH = """
用户有一份待分析表格文件数据，目前已经导入到 DuckDB 表中，\

一部分采样数据如下:
``````json
{data_example}
``````

DuckDB 表结构信息如下：
{table_schema}


DuckDB 中，需要特别注意的 DuckDB 语法规则：
``````markdown
### 在 DuckDB SQL 查询中使用 GROUP BY 时需要注意以下关键点：

1. 任何出现在 SELECT 子句中的非聚合列，必须同时出现在 GROUP BY 子句中
2. 当在 ORDER BY 或窗口函数中引用某个列时，确保该列已在前面的 CTE 或查询中被正确选择
3. 在构建多层 CTE 时，需要确保各层之间的列引用一致性，特别是用于排序和连接的列
4. 如果某列不需要精确值，可以使用 ANY_VALUE() 函数作为替代方案
``````

请基于给你的数据结构信息，在满足下面约束条件下通过\
DuckDB SQL数据分析回答用户的问题。
约束条件:
	1.请充分理解用户的问题，使用 DuckDB SQL 的方式进行分析，\
	分析内容按下面要求的输出格式返回，SQL 请输出在对应的 SQL 参数中
	2.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，\
	将类型名称放入返回要求格式的name参数值中，如果找不到最合适\
	的则使用'Table'作为展示方式，可用数据展示方式如下: {display_type}
	3.SQL中需要使用的表名是: {table_name},请检查你生成的sql，\
	不要使用没在数据结构中的列名
	4.优先使用数据分析的方式回答，如果用户问题不涉及数据分析内容，你可以按你的理解进行回答
	5.输出内容中sql部分转换为：
	<api-call><name>[数据显示方式]</name><args><sql>\
	[正确的duckdb数据分析sql]</sql></args></api- call> \
	这样的格式，参考返回格式要求
	
请一步一步思考，给出回答，并确保你的回答内容格式如下:
    [对用户说的想法摘要]<api-call><name>[数据展示方式]</name><args>\
    <sql>[正确的duckdb数据分析sql]</sql></args></api-call>

你可以参考下面的样例:

例子1：
user: 分析各地区的销售额和利润，需要显示地区名称、总销售额、\
总利润以及平均利润率（利润/销售额）。
assistant: [分析思路]  
1. 需要识别查询核心维度(地区)和指标(销售额、利润、利润率)  
2. 利润率计算需在聚合后计算，避免分母错误  
3. 过滤空地区保证数据准确性  
4. 按销售额降序排列方便业务解读
<api-call><name>response_table</name><args><sql>
SELECT region AS 地区,
       SUM(sales) AS 总销售额,
       SUM(profit) AS 总利润,
       SUM(profit)/NULLIF(SUM(sales),0) AS 利润率
FROM sales_records
WHERE region IS NOT NULL
GROUP BY region
ORDER BY 总销售额 DESC;
</sql></args></api-call>

样例2：
user: Show monthly sales trend for the last 2 years, including year-month, total 
orders and average order value.
assistant:
[Analysis Insights]  
1. Time range handling: Use DATE_TRUNC for monthly granularity  
2. Calculate rolling 24-month period dynamically  
3. Order date sorting ensures chronological trend  
4. NULL order_date filtering for data integrity

<api-call><name>response_table</name><args><sql>
SELECT 
  DATE_TRUNC('month', order_date)::DATE AS year_month,
  COUNT(DISTINCT order_id) AS order_count,
  AVG(order_value) AS avg_order_value
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '2 years'
  AND order_date IS NOT NULL
GROUP BY 1
ORDER BY year_month ASC;
</sql></args></api-call>

注意，回答一定要符合 <api-call> 的格式! 请使用和用户问题相同的语言回答！
用户问题：{user_input}
"""


_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

_PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)


PROMPT_NEED_STREAM_OUT = True

# Temperature is a configuration hyperparameter that controls the randomness of
# language model output.
# A high temperature produces more unpredictable and creative results, while a low
# temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate
# text that is more predictable and less creative than if you set the temperature to
# 1.0.
PROMPT_TEMPERATURE = 0.3

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(_PROMPT_SCENE_DEFINE + _DEFAULT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatExcel.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=ChatExcelOutputParser(),
    temperature=PROMPT_TEMPERATURE,
)
CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
