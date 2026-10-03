# Dashboard 安全说明

本说明对应当前集成实现。自然语言、模型计划与 SQL、浏览器 Schema、筛选参数、旧资产和公开令牌都视为不可信输入。

## 查询边界

`sql_security.py` 使用 AST 解析并限制只读 SELECT/CTE，拒绝写操作、DDL、多语句、文件与命令类函数和模板插值。解析失败时拒绝执行。表和字段必须在所选数据源的允许列表内；联邦查询还要验证每个来源、关系及资源约束。

筛选值通过命名参数绑定。多选参数由执行层展开，不能拼接用户文本；标识符、表名和排序方向不能作为普通值替换。超时、行数及总等待受服务端限制。驱动的实际取消能力不同，SQL 校验也不能替代数据库只读权限。

行数上限按所选连接器的方言构造，额外读取一行判断截断；SQLite、MySQL、PostgreSQL、SQL Server 和 Oracle 的生成用例分别验证。SQL Server 的排序子查询补充有界 TOP，CTE 提升到合法位置；Oracle 使用 FETCH FIRST 并省略内联视图别名的 AS。命名绑定保持 SQLAlchemy 的 `:name` 形式，改写后再次执行只读校验。SQL Server/Oracle 的覆盖为语法生成、参数与等价查询回归，尚未进行原生数据库验收；Oracle 的该语法要求 12c 或更新版本。

方言依据：[SQL Server TOP](https://learn.microsoft.com/en-us/sql/t-sql/queries/top-transact-sql)、[SQL Server ORDER BY 的子查询限制](https://learn.microsoft.com/en-us/sql/t-sql/queries/select-order-by-clause-transact-sql)、[Oracle SELECT 行数限制](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/sqlrf/SELECT.html)。

## 身份和对象权限

当前实现通过 `identity.py` 适配 DB-GPT 身份，通过 `access.py` 分别检查对象角色与数据源查询权限。viewer 可查看；editor 可查看、编辑和查询；owner 拥有对象管理权限。公开令牌授权是独立访问路径。

部署身份提供器可由 `DBGPT_DASHBOARD_IDENTITY_PROVIDER` 配置，数据源策略由 `DBGPT_DASHBOARD_DATA_SOURCE_POLICY` 接入。生产模式对开发身份和缺失授权适配采取限制；具体接入与验证见 [授权集成](AUTHORIZATION_INTEGRATION.md)。开发示例中的用户请求头不是对外部署的登录认证方案。

接受未保存 Schema 的验证和预览仍需检查对象和来源权限。保存、修改、发布及计划任务按相应动作授权；审计信息对令牌、凭据、SQL 和参数等敏感内容脱敏。

## 并发和发布

保存携带 `expected_revision`，冲突返回 409。发布经过 Schema、参数、安全、实际查询和输出绑定检查。已发布修订与草稿分离；固定历史数据不因后续编辑变化。

| 公开模式 | 数据与执行边界 |
|---|---|
| 固定历史快照 | 在冻结数据中执行声明的筛选，不连接原数据源。 |
| 最新发布别名 | 跟随后续显式发布，不能冒充固定修订链接。 |
| 持续更新分享 | 按授权的已发布定义刷新，不接受访客任意 SQL；受有效期和撤销控制。 |

令牌查找采用 SHA-256。为让授权发布者恢复自己的分享链接，独立表保存 Fernet 加密密文；不能描述成“数据库只有哈希”。`DBGPT_SHARE_KEY_FILE` 指定密钥文件，默认位置为 `pilot/meta_data/dashboard-share.key`。部署应按密钥与数据库共同恢复的要求管理访问权限、备份和多实例配置。仓库示例及测试输入不应含有效生产令牌。

密文表由 Alembic 管理，服务初始化与请求处理不执行建表。持续分享被撤销或轮换时，同一事务删除其旧密文。解密失败记录不含令牌、哈希或密文的诊断日志，便于检查密钥配置。

默认密钥目录仍与元数据库相邻，生产应显式配置独立保护的密钥。自动生成通过硬链接原子安装密钥：并发创建时沿用胜出进程的密钥，不能用会覆盖目标的替换操作。文件系统不支持硬链接或权限不足时，错误提示明确要求检查权限、硬链接支持或设置 `DBGPT_SHARE_ENCRYPTION_KEY`；失败的临时文件会清理，原始异常保留为原因。配置环境密钥时不依赖文件系统硬链接。持续分享有效期当前固定为 30 天，匿名缓存访问仍使用行锁，尚无高并发负载结论。

## 验证范围

相关测试覆盖 SQL 注入与危险节点、字段允许列表、参数、对象角色、数据源边界、修订冲突、固定快照与持续分享。测试命令见 [开发指南](DEVELOPER_GUIDE.md)，执行情况见 [验证说明](VALIDATION.md)。生产身份、密钥管理和真实数据库驱动行为仍需在实际部署中验收。
