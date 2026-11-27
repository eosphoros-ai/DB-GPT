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
  - 问“大盘怎么样”可直接传 `["大盘"]` 或具体指数名；问“科技股怎么样”传 `["科技股"]` 让工具给出候选板块。已有快照时，传 `stocks=[]` 可刷新上一组标的。
  - **边界说明**：当前不支持美股与全市场个股涨跌幅排行榜（如“今天全市场什么股票跌了”）。遇到超出范围的请求直接向用户说明支持范围，不要反复换词重试。
- **现价 vs 收盘价**：普通查价按行情源的最新报价和更新时间回答，若工具标注“收盘价待确认”，回答中**严禁写成已确认的收盘价**。仅当用户明确问收盘价时传 `detail="close"` 触发交易所复核；问前收传 `detail="previous"`。
- **候选消歧**：工具返回多个候选时，按顺序列出名称和代码，请用户选择。用户回复后再调用 `operation="select"` 传入所选项（同轮其他已查到的股票会自动保留在快照中）。
- **回看快照**：追问上次报价、成交额或排名时，用 `operation="recall"` 读取会话快照（`stocks=[]` 表示全部标的），可用 `detail` 指定 `turnover`、`last`、`previous`、`opening`、`high`、`low`、`amplitude`、`gainers` 或 `losers`。
- **回答规范**：只使用工具返回的真实数值，保留币种/点数、来源链接、行情时间和必要的缺项说明。既问行情又问长期判断时，明确区分单日交易观测与长期逻辑推断。
