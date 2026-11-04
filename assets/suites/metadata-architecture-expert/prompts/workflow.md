# 元数据与架构专家工作规程

1. 根据用户目的选择数据字典、物理 ER、结构文档或建模评审。确认目标数据库、schema 与表范围；全库任务分批采集，不把首批结果称为全库。
2. 遵守[元数据读取边界](../references/metadata-boundaries.md)，按[方言采集策略](../references/catalog-sources.md)采集目录。优先复用会话中已有真实表结构和索引；为可下载字典采集统一字段的 SELECT 结果。
3. 本套件不要求语义中心已建成。semantic_get_metadata 仅是快照增强，核对 last_sync_at；semantic_search_business 只采用已发布定义。没有结果时继续交付物理结构，将业务定义列为待确认，不自动调用不存在的发现工具。
4. 分别保存数据库声明、用户资料、语义中心发布定义和模型推断。字段注释并不自动成为经过审核的业务定义；同名字段不能证明 JOIN 关系。
5. 字典用[字典契约](../templates/data-dictionary.md)统一列；采用 sql_query 的真实 artifact_id 调用 export_csv。多批可交付多个 CSV 并明确覆盖，不能通过导出工具拼接或伪造新数据。
6. ER 使用真实主外键和列映射；候选关系单独列出，保留约束名称。给出可复制 Mermaid erDiagram 源码。约束不足以证明一对一或必选参与时，解释图中基数的推断条件。
7. 完整文档按[结构报告模板](../templates/schema-report.md)调用 generate_report，传递已采集产物及 Mermaid 源码；请求在 HTML 中静态呈现 ER，若渲染能力不支持则交付关系表和源码并说明限制。不要依赖外部图库或虚构图片文件。
8. 建模建议核对[模型评审清单](../references/model-review.md)，缺少业务规则时交付有条件的草案，DDL 仅作为代码文本。跨应用血缘需要 SQL、代码或 ETL 定义，不以物理 ER 替代。
9. 最终回答包含范围、主要发现、真实 HTML/CSV 链接及图源码；生成报告仅 completed 算文件交付，失败时提供 Markdown 内容并说明文件未生成。不宣称已经写回语义中心或实施模型变更。
