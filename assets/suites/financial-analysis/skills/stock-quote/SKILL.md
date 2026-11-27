---
name: stock-quote
name_zh: 查股票
name_en: Stock quotes
command: /查股票
command-en: /stock-quote
user-invocable: true
agent-tools: [query_stock_quotes]
description: 查询沪深京 A 股、ETF、港股、主要中港指数（含大盘）和 A 股板块涨跌、领涨领跌，或回看之前的行情快照。适用于用户询问价格、估值、交易表现或板块排名。纯概念、前景和长期观点由 Agent 直接讨论。
description_en: Look up CN/HK share prices, ETFs, major CN/HK indices, A-share sector moves and rankings, or recall a saved quote. Use for questions about trading data. Discuss concepts and long-term theses directly.
argument-hint-zh: 帮我查查今天科技股和贵州茅台涨了多少？
argument-hint-en: How much have tech stocks and Kweichow Moutai (600519.SH) moved today?
---

# 查股票

用这项技能取得回答所需的行情事实。收到结果后，回到用户的完整问题，按要求组织最终回答。

- **查最新行情**：调用 `query_stock_quotes(stocks=[...], operation="latest")`。
  - 支持沪深京 A 股、ETF、港股个股（含双柜台）、主要中港指数（如“大盘”“上证指数”“深证成指”“创业板指”“沪深300”“科创50”“恒生指数”“恒生科技”）和 A 股行业/概念板块（如“光模块”“半导体”“银行板块”）。
  - 问“大盘怎么样”直接传 `["大盘"]`（已包含上证指数、深证成指、创业板指，无需重复列举）或只传所需具体指数名；问“科技股怎么样”传 `["科技股"]` 让工具给出候选板块。已有快照时，传 `stocks=[]` 可刷新上一组标的。
  - **边界说明**：当前不支持美股与全市场个股涨跌幅排行榜（如“今天全市场什么股票跌了”）。遇到超出范围的请求直接向用户说明支持范围，不要反复换词重试。向用户主动询问是否查询某公司行情时，明确标注当前支持的上市地（如港股支持、美股暂不支持）。
- **多轮追问**：用户简短回复“查询一下吧”“看看”“查吧”等时，优先结合**紧邻上一轮对话**确定目标标的并显式传入 `stocks=[...]` 调用 `latest`（如上轮刚提到阿里巴巴-SW 9988.HK 和美股 BABA，则直接查 `["9988.HK"]` 并说明美股暂不支持），切勿被更早轮次的旧行情快照带偏。
- **现价 vs 收盘价**：普通查价按行情源的最新报价和更新时间回答，若工具标注“收盘价待确认”，回答中**严禁写成已确认的收盘价**。仅当用户明确问收盘价时传 `detail="close"` 触发交易所复核；问前收传 `detail="previous"`。
- **候选消歧**：工具返回多个候选（`needs_selection=true`）时，**必须立即在本轮调用 `question` 工具**（不要结束本轮回复，也不要切到下一轮对话），将各候选作为 `options`（`label` 带名称与代码，如 `半导体（BK1036）` 或 `中芯国际 688981.SH`；板块候选支持多选可设 `multiple: true`）弹出到输入框上方让用户选择。收到用户选择后，立即在同一轮调用 `query_stock_quotes(operation="select", stocks=[...])` 合并补查，再输出一份完整的最终回答（同轮其他已查到的股票会自动保留在快照中）；若用户跳过/取消提问，则基于已查到的标的直接作答。
- **回看快照**：追问上次报价、成交额或排名时，用 `operation="recall"` 读取会话快照（`stocks=[]` 表示全部标的），可用 `detail` 指定 `turnover`、`last`、`previous`、`opening`、`high`、`low`、`amplitude`、`gainers` 或 `losers`。成功回看时界面会自动展示精简卡片。
- **回答规范**：
  - 当工具成功返回行情或候选卡片（`card_rendered=true`）时，界面上方已渲染结构化行情卡片。正文应以**一句话/要点总结核心涨跌**为主，重点解答用户的延伸问题（对比、归因、观点分析等），**不要重复铺出完整的 Markdown 行情明细表**（前收、开盘、最高、最低、成交额、估值全项已在卡片展示）。
  - 只使用工具返回的真实数值，保留币种/点数与必要的边界/缺项提示（如“收盘价待确认”、口径冲突、部分标的不支持）。若工具全部失败（无卡片展示），直接简洁说明原因和支持范围。
  - 既问行情又问长期判断时，明确区分单日交易观测与长期逻辑推断。
  - 完成回答时直接通过 `terminate(output=...)` 返回最终正文，避免在工具调用之外裸输出纯文本。
