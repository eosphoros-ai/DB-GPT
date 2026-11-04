# 元数据与架构专家

基于直连数据库的物理元数据交付套件，支持 DB-GPT 和 PI 的现有工具链。版本 1.0.0。

## 使用与产物

选择元数据与架构专家并绑定已授权的数据源，指定 schema/表范围。

| 命令 | 交付 |
| --- | --- |
| /data-dictionary | 物理字段字典、真实目录查询 CSV、语义确认清单 |
| /physical-er | 真实主外键关系表、可复制 Mermaid ER 源码；完整任务提供 HTML 报告 |
| /schema-doc | HTML 结构文档、字典、物理关系及来源 |
| /model-review | 模型问题、候选设计/DDL 文本、取舍与迁移验证清单 |

CSV 仅来自已执行且未截断的目录查询。HTML 由 generate_report 交付；图默认提供 Mermaid 源码，HTML 内静态图的呈现取决于报告渲染能力，不承诺独立 PNG/SVG 文件。

## 边界

初版优先 MySQL、PostgreSQL、SQLite，其他方言以经核实目录或用户 DDL 为基础。真实外键不等于跨系统血缘；推断关系与业务定义另列。语义中心为可选增强，不影响物理结构交付。

只允许目录查询、可选语义读取、现有结果 CSV 导出和报告生成。不会执行 DDL、全量读取业务内容或写回语义中心。生产账号、取消、查询成本及对象可见性由部署侧管理。

详见[工作规程](prompts/workflow.md)、[元数据边界](references/metadata-boundaries.md)、[字典契约](templates/data-dictionary.md)及[报告模板](templates/schema-report.md)。
