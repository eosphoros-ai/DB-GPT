---
sidebar_position: 3
title: 外接数据源
---

# 外接数据源

将外部平台——飞书知识库、飞书云盘、语雀、RSS——绑定到一个知识空间。这些平台的文档会被自动拉取（分块、向量化、可检索），并按你选择的频率持续同步。

![知识库列表与 Wiki 徽标](/images/web-ui/llm-wiki/01-knowledge-list.png)

## 支持的数据源

| 来源 | 同步内容 | 凭证 |
|---|---|---|
| **飞书知识库** | Wiki 空间 → docx 文档（blocks → Markdown），表格/多维表格链接 | App ID + App Secret |
| **飞书云盘** | 云盘文件夹 → docx 文件，其它类型转为引用链接 | App ID + App Secret |
| **语雀** | 个人 + 团队仓库 → 文档（正文即 Markdown） | 个人 Token |
| **RSS / Atom** | 订阅源文章 → Markdown | Feed URL |

Notion 即将开放（卡片已在类型选择器中，连接器发布后即可点亮）。

## 绑定数据源

### 第一步 — 创建或打开知识空间

两个入口都可以绑定：

- **创建空间时**——选择绑定式卡片（飞书知识库 / 语雀 / RSS）。空间创建后，绑定向导自动内嵌打开并预选连接器。
- **空间详情页 → 数据源页签**——点击 **绑定数据源**。

![创建向导与数据源卡片](/images/web-ui/llm-wiki/05-datasource-cards.png)

### 第二步 — 选择连接器类型

向导共四步。先选平台（从创建流程进入时本步已自动回答并跳过）。

![绑定向导 — 选择类型](/images/web-ui/llm-wiki/14-binding-wizard-types.png)

### 第三步 — 配置凭证

凭证会先对接平台**实时验证**，验证通过才保存，并以 AES-256-GCM 加密存储在元数据库中。

![绑定向导 — 配置凭证](/images/web-ui/llm-wiki/15-binding-credentials.png)

### 第四步 — 选择范围

资源树从平台懒加载（如飞书知识库空间 → 节点树、语雀个人/团队仓库）。勾选需要同步的对象——行内不会暴露原始 URL。

### 第五步 — 同步策略

| 字段 | 含义 |
|---|---|
| 同步频率 | 仅手动 / 每 15 / 60 / 1440 分钟 |
| 同步模式 | 增量（游标比对仅拉取变更）/ 全量 |
| 冲突策略 | 覆盖（更新并重新分块）/ 无变化跳过 |
| 同步删除 | 开启后源端删除的条目会同步删除本地文档（仅全量轮次判定） |

点击 **完成**——首次拉取立即执行，并弹出新增/更新数量提示。文档出现在 **文件视图**；若空间同时开启了 LLM-Wiki 索引，Wiki 页面会自动再生。

## 管理绑定

![数据源页签的绑定卡片](/images/web-ui/llm-wiki/13-sources-tab.png)

每张绑定卡片实时展示状态（正常 / 已暂停 / 同步中 / 异常）、最近同步时间与错误信息。可用操作：

- **立即同步** — 手动执行一次全量/增量
- **暂停 / 恢复** — 停止或恢复定时调度
- **同步日志** — 最近 50 次运行的新增/更新/跳过/失败/删除明细
- **删除** — 解除绑定（已同步文档保留）

## 故障排查

| 症状 | 处理 |
|---|---|
| `knowledge source encrypt key not configured` | 当前版本已自动托管密钥；仅需在需要 DBA 级保密时设置 `DB_GPT_KS_ENCRYPT_KEY`（或 `[rag.knowledge_source] encrypt_key`） |
| 语雀 `HTTP 429` | 触发限流——1~2 分钟后重试；持续 429 说明 Token 被限流或与其它脚本共用，请轮换 Token |
| `CERTIFICATE_VERIFY_FAILED` | 公司代理拦截了 TLS。设置 `DB_GPT_KS_CA_BUNDLE` 指向企业根证书（或临时 `DB_GPT_KS_INSECURE=1`）后重启 |
| `Errno 8 nodename nor servname` | DNS 解析失败——检查服务器网络/代理 |
| 飞书 `invalid app_id/secret` | 创建企业自建应用并开通 `wiki:wiki:readonly`、`docx:document:readonly`、`drive:export:readonly` 权限后发布 |

## 社区连接器

新平台遵循一个小契约：实现
`BaseKnowledgeSourceConnector` 的
`validate / list_resources / fetch_all / fetch_incremental` 四个方法与
`ConnectorMeta`，即可让凭据表单自动渲染。

```toml
[project.entry-points."dbgpt.knowledge_sources"]
my_source = "my_pkg.connector:MyConnector"
```

`pip install` 后重启 DB-GPT 即可在向导中出现——无需任何前端代码。完整开发者指南见 docs 站 Developers → Agent Modules → Resource 下的《自定义知识数据源连接器》。
