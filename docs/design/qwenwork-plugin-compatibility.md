# QwenWork 原生专家套件兼容

DB-GPT 支持直接导入千问办公生成的专家套件 ZIP，不需要生成或修改 `suite.yaml`。
原始 `.qwenwork-plugin/plugin.json`、`SKILL.md` 和参考文件保持不变。
旧版 `suite.yaml` 包继续兼容；同一目录同时存在两种清单时以 plugin.json 为准。

## 包结构与命令

ZIP 可以直接包含清单，也可以包含一层套件目录：

```text
mysql-ops-expert/
  .qwenwork-plugin/plugin.json
  skills/
    mysql-sql-doctor/
      SKILL.md
      references/
    mysql-ops-knowledge/
      SKILL.md
      references/
```

plugin.json 的 `skills` 数组声明技能目录或 SKILL.md 路径。
套件名称、版本、中文展示名称分别读取 `name`、`version`、`displayNameCn`。
命令由技能 frontmatter 生成：

| 字段 | DB-GPT 行为 |
| --- | --- |
| `name` | 技能标识，也是 `/技能标识` 别名 |
| `name_zh` | 中文命令名，例如 `/SQL 体检` |
| `name_en` | 英文命令别名，例如 `/SQL Doctor` |
| `command` | DB-GPT 可选扩展，保留既有命令，例如 `/nl2sql`；中文名称仍可作别名 |
| `description_zh` / `description` | 命令说明 |
| `argument-hint-zh` / `argument-hint` | 参数提示 |
| `user-invocable: false` | 内部知识技能，不生成用户命令 |

缺省 `user-invocable` 为 true。未声明 DB-GPT 上下文要求的插件允许未连接数据库时
使用粘贴的 SQL、执行计划、日志等输入。连接器和数据库仍需在 DB-GPT 中配置。

## 内置套件与数据库

### 内容国际化

英文入口显示为 `Plugins`，中文入口仍为“专家套件”。列表、详情和首页示例
随当前语言切换；命令 ID、技能绑定、数据库名和工具权限不随语言改变。

- plugin.json：`displayNameEn` / `displayName`、`descriptionEn` / `description`
  为英文内容；中文仍用 `displayNameCn`、`descriptionZh`。
- SKILL.md：读取 `name_en`、`description_en`、`argument-hint-en`；对应中文字段
  保持可用。原生中文命令可展示英文别名，发送时仍用规范命令名。
- 示例：在 `dbgpt.recommended_questions` 中提供 `text_en`、`title_en`、
  `hint_en`，数据库与 command 字段由两种语言共用。
- README：详情接口从包内 `README.en.md`、`README.zh.md` 读取可选译文，
  缺省回退 `README.md`。正文不存入注册快照。

三个内置套件已提供英文简介、全部技能说明、示例和英文 README。
导入包没有译文时回退原文，不自动机器翻译技能正文或修改原始文件。
添加译文后通过启动同步或 `/api/v1/suites/sync` 更新注册快照。

智能取数、智能分析、智能运维均采用 `.qwenwork-plugin/plugin.json`，
不再保留 suite.yaml 或第二份平台清单，版本为 1.1.0。
命令只从 SKILL.md 元数据生成，不在 JSON 中维护第二份命令映射。
`/metric` 与 `/explain` 是独立入口技能，通过 Markdown 链接复用已有知识。
只读护栏是内部技能，由 `/nl2sql` 等命令预加载。

`plugin.json.dbgpt` 为 DB-GPT 扩展，保留 SOP 路径、工具白名单与拒绝列表、
审批声明、数据库要求、语义绑定、示例与路由等平台配置。
扩展不能覆盖原生 name、version、skills 或生成的 commands。
这些声明继续由原有执行器处理；格式迁移没有新增声明项的执行保证。

启动或调用 `POST /api/v1/suites/sync` 时扫描文件并同步数据库：

- `dbgpt_serve_plugins`：安装注册表，保存名称、版本、来源、状态、路径、
  包摘要、使用次数、时间与可重建的 manifest_snapshot。
- `dbgpt_serve_plugins_event`：安装、启停、升级、会话 pin/switch 等事件。
- 对话历史：保存本轮命令引用与各加载文档的路径和哈希。

plugin.json、SKILL.md、SOP、模板和参考正文保存在文件系统。
版本或包摘要改变时更新同一注册记录，保留 ID、启用状态及使用次数；
文件丢失时不能仅依赖配置快照执行技能。该迁移不改变历史会话正文。

## 技能和共享知识加载

每轮明确选择命令或输入已知命令时，后端读取对应 SKILL.md，并递归读取其中
包内 Markdown 链接，包括共享知识、报告模板和跨技能参考文件。
外部网址、图片和代码块中的示例链接不作为加载依赖。
已读取文件去重，循环引用终止；路径必须位于套件内，
最多 64 个文档、正文合计不超过 512KB。

必需文件缺失、为空、越界或超限时，命令绑定失败并阻止业务工具执行，
用户询问与结束任务工具仍可使用。
运行时沿用后端预加载模式，加载完整正文到模型上下文；
它不是千问办公运行时的逐步按需加载实现，也不保证模型逐项执行业务 SOP。
文件加载成功与 SQL、连接器或其他工具执行成功是不同状态。

`suite.bound` 事件和历史消息 `suite_binding` 保存命令、技能、
各文件相对路径和 SHA-256。哈希基于去除首尾空白后的 UTF-8 正文。
历史记录不保存参考正文，刷新页面后恢复加载标签。

## 导入与边界

页面入口：专家套件 → 添加 ZIP；接口：`POST /api/v1/suites/upload`。
上传压缩包和解压文件总量分别限制为 50MB。
拒绝路径越界和 ZIP 符号链接，先校验再安装。
升级整包替换，注册失败恢复旧目录，避免旧技能和引用残留。

兼容范围为包结构、技能元数据、命令入口、包内参考内容与历史回显。
没有 `dbgpt` 扩展的原生 plugin 不额外声明 DB-GPT 工具白名单；
有扩展的内置套件保留既有白名单，工具执行仍经过平台权限与审批。
千问办公专有连接器、发布接口以及 `@技能` 跨技能自动转交没有新增实现。
未通过 Markdown 链接声明的脚本、二进制和参考文件不自动注入上下文。
