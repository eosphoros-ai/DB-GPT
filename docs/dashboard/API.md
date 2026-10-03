# Dashboard API

基础路径：`/api/v1`。非公共接口使用 DB-GPT 身份适配，并按对象角色和数据源策略授权，参见 [授权集成](AUTHORIZATION_INTEGRATION.md)。本页基础接口与扩展章节共同阅读；完整合同以 [api.py](../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/api.py) 及请求模型为准。

统一响应仍使用 DB-GPT `Result`：

```json
{
  "success": true,
  "err_code": null,
  "err_msg": null,
  "data": {}
}
```

## 1. 草稿

### `POST /dashboards`

创建草稿。

```json
{
  "schema": {"schema_version": "1.0"},
  "conversation_id": "optional-conversation-id",
  "source_turn_id": "optional-agent-turn-id",
  "origin": "manual",
  "asset_state": "saved"
}
```

服务端生成或固定 Dashboard ID，把状态设为 `draft`，执行结构和 SQL 静态校验，然后保存修订 1。普通 API 默认创建 `manual/saved` 资产；Agent 内部创建路径固定为 `task/generated`。

### `GET /dashboards`

列出当前用户的看板。只返回卡片所需摘要，不返回大快照。支持 `conversation_id`、`origin`、`exclude_origin`、`asset_state`、`status` 和 `include_generated` 查询参数；默认隐藏 generated 草稿。

### `GET /dashboards/page`

服务器分页、搜索和状态筛选，生命周期筛选参数与普通列表一致。返回 `items/total/limit/offset`；权限列表使用 ID 子查询，页数据和总数始终固定为两条数据库查询。

### `GET /dashboards/{id}`

读取当前用户的一个草稿。其他用户访问同一 ID 得到 404，不泄漏对象是否存在。

### `PUT /dashboards/{id}`

保存编辑：

```json
{
  "schema": {},
  "expected_revision": 3
}
```

成功后返回修订 4；修订不一致返回 `409 Conflict`。

用户编辑器第一次保存 task/generated 草稿时，同一操作会把它转为 saved 资产并写入 `saved_at`。Agent 内部修复使用非资产化路径，不会代替用户执行第一次保存。

### `GET /dashboards/{id}/snapshot`

读取当前用户有权限查看的最新不可变发布快照，用于编辑器恢复最近一次数据。接口不会重新执行 SQL；没有已发布版本时返回 404。

### 看板生命周期

| 方法 | 路由 | 用途 |
|---|---|---|
| POST | `/dashboards/{id}/copy` | 复制为新草稿 |
| POST | `/dashboards/{id}/archive` | 按预期修订归档 |
| POST | `/dashboards/{id}/restore` | 恢复已归档看板 |
| GET | `/dashboards/{id}/revisions` | 列出不可变发布修订 |
| POST | `/dashboards/{id}/revisions/{revision}/restore` | 由旧快照创建新草稿修订 |

## 2. Schema 与兼容导入

### `GET /dashboards/schema`

返回后端 Pydantic 生成的 JSON Schema，前端用 Ajv 做快速检查。

### `POST /dashboards/import/legacy`

把旧 `chat_dashboard.ReportData` 复制为新草稿：

```json
{
  "report": {},
  "data_source_id": "demo",
  "conversation_id": "legacy-conversation"
}
```

导入不修改旧报告或会话历史。

## 3. 校验与执行

### `POST /dashboards/{id}/validate`

```json
{
  "schema": {},
  "execute_queries": true,
  "filters": {"year": 2024}
}
```

即使请求提供未保存 Schema，接口也会先确认当前用户拥有 `{id}`，并禁止临时切换数据源。返回：

```json
{
  "valid": false,
  "issues": [
    {
      "path": "widgets.1.query",
      "code": "query_validation_failed",
      "message": "SQL references columns outside the data source allowlist: profit.",
      "severity": "error"
    }
  ],
  "widget_status": {"sales": "executed", "profit": "invalid"}
}
```

### `POST /dashboards/{id}/widgets/{widget_id}/preview`

只试运行一个组件。可携带当前未保存 Schema，以便用户先验证 SQL 再保存；同样先检查对象操作权限和数据源边界。

```json
{
  "filters": {},
  "schema": {}
}
```

### `POST /dashboards/{id}/refresh`

用已保存 Schema 和当前筛选器刷新所有组件：

```json
{"filters": {"date": ["2011-01-01", "2012-12-31"]}}
```

单个组件失败不会终止其他组件。响应 `widgets` 以组件 ID 为键，每项包含列、行、耗时、截断标记或错误。

## 4. 发布与分享

### `POST /dashboards/{id}/publish`

```json
{
  "expected_revision": 4,
  "filters": {"year": 2024}
}
```

发布步骤：

1. 检查所有者和草稿修订；
2. 结构、SQL、允许列表和参数校验；
3. 全部组件真实刷新；
4. 任一组件失败则返回 422；
5. 追加不可变 Schema/数据/校验快照；
6. 返回分享令牌和相对路径；授权发布者恢复链接所需的密文由独立保管表保存，详见 [安全说明](SECURITY.md)。

```json
{
  "dashboard_id": "abc",
  "published_revision": 2,
  "share_token": "secret-token",
  "share_path": "/dashboard-share/secret-token",
  "published_at": "2026-08-11T00:00:00"
}
```

### `GET /public/dashboards/{token}`

无需登录。固定发布令牌只读取发布修订中的 Schema 和数据快照；持续分享令牌由独立授权路径按已发布定义刷新，不接受访客任意查询。两种模式的边界见 [安全说明](SECURITY.md)。

### `POST /public/dashboards/{token}/filter`

无需登录。固定发布模式按公开页面的筛选值，在冻结的受限数据集上重新聚合；持续模式按已发布的绑定和授权执行：

```json
{
  "filters": {
    "date_range": ["2011-01-01", "2012-12-31"],
    "stores": [1, 2],
    "holiday": true
  }
}
```

响应包含新的公开 `snapshot` 和 `unsupported_widget_ids`。该接口不会取得数据源 Connector、不会执行 SQL，也不会在响应中暴露内部 `publication_datasets`。未知筛选器、非法日期或不在允许选项中的值返回 422；撤销或过期的令牌返回 404。

### 分享生命周期（需登录）

| 方法 | 路由 | 用途 |
|---|---|---|
| GET | `/dashboards/{id}/publications` | 列出分享记录、到期和撤销状态 |
| POST | `/dashboards/{id}/publications/{revision}/rotate` | 使旧链接立即失效并签发新链接 |
| DELETE | `/dashboards/{id}/publications/{revision}` | 撤销该发布修订的活动链接 |

`publish` 可选传 `share_expires_in_seconds`（60 秒至 365 天）。到期或撤销后公开读取立即失效，但不变更已发布 Schema/数据快照。

## 4.1 Dashboard 批注与 Agent 变更提案（v3.4）

| 方法 | 路由 | 用途 |
|---|---|---|
| GET | `/dashboards/{id}/annotations` | 按分页读取当前用户可见批注 |
| POST | `/dashboards/{id}/annotations` | 保存目标、基础修订和自然语言要求 |
| POST | `/dashboards/{id}/annotations/{annotation_id}/apply` | 在修订一致且验证通过后应用提案 |
| POST | `/dashboards/{id}/annotations/{annotation_id}/reject` | 放弃待处理或已提议变更 |

提案由 `propose_dashboard_change` Agent 工具写入批注记录。模型只使用组件、筛选器等稳定 ID；服务端转换成真实补丁路径，并在应用前再次验证 Schema、SQL 与组件查询。旧修订提案返回 409，不会静默覆盖用户的新修改。

## 5. 状态码

| 状态码 | 含义 |
|---|---|
| 200 | 请求成功，具体业务结果在 `data` |
| 404 | 看板不属于当前用户、ID 不存在或分享令牌无效 |
| 409 | `expected_revision` 已过期 |
| 422 | Schema、SQL、字段映射或发布前刷新未通过 |

## 6. 调用示例

```powershell
$headers = @{ "user-id" = "001" }
$schema = Get-Content -Raw -Encoding UTF8 `
  .\examples\dashboard\schemas\walmart-sales.schema.json | ConvertFrom-Json
$body = @{ schema = $schema } | ConvertTo-Json -Depth 100

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:5670/api/v1/dashboards" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

## Dashboard schedules (v2.2)

Only a dashboard owner with `manage_schedule` permission can use these routes.
They are intentionally separate from the generic scheduled-chat API.

| Method | Route | Purpose |
|---|---|---|
| POST | `/dashboards/{id}/schedules` | Create a persisted refresh plan |
| GET | `/dashboards/{id}/schedules` | List plans for this dashboard |
| PUT | `/dashboards/{id}/schedules/{schedule_id}` | Update cron, filters, retry, timeout, or publication policy |
| POST | `/dashboards/{id}/schedules/{schedule_id}/toggle` | Pause or resume a plan |
| POST | `/dashboards/{id}/schedules/{schedule_id}/run` | Run now using the same persistent execution lease |
| GET | `/dashboards/{id}/schedules/{schedule_id}/runs` | Read bounded run history |
| DELETE | `/dashboards/{id}/schedules/{schedule_id}` | Delete a plan |

Create example:

```json
{
  "task_name": "Daily operating dashboard refresh",
  "cron_expression": "0 6 * * *",
  "filters": {"region": "east"},
  "publish_after_refresh": false,
  "timeout_seconds": 180,
  "max_attempts": 2
}
```

Runs may end in `success`, `partial_success`, `failed`, or `timeout`.
`partial_success` preserves successful widgets but never auto-publishes an incomplete
snapshot. Run history contains filter keys, not raw filter values.

## Constrained cross-source widgets (v2.3)

No additional anonymous or SQL proxy endpoint is introduced. The existing validate,
preview, refresh, and publish routes accept Schema 1.1 widgets with
`query.federation`. The service authorizes and validates every declared source before
executing it, then performs a bounded `union_all`, `inner` equality join, or `left`
equality join in application memory.

See `SCHEMA_1_1_FEDERATION.md` for the contract and limits. A federated widget that
uses Schema 1.0, mixes top-level SQL with federation, refers to an unauthorized source,
or exceeds its mapping/operation rules is rejected with a 422 validation response.

## Collaborative editing (v2.4)

| Method | Route | Purpose |
|---|---|---|
| POST | `/dashboards/{id}/operations` | Apply a validated, idempotent patch against an expected revision |
| GET | `/dashboards/{id}/operations?after_revision=7` | Catch up after reconnecting |
| POST | `/dashboards/{id}/collaboration-ticket` | Issue a 60-second, one-time WebSocket ticket |
| WS | `/dashboards/{id}/collaborate?ticket=...` | Presence and accepted-operation events |

Operation example:

```json
{
  "operation_id": "62be0466-6676-4fb2-a4de-79cc5c93dd40",
  "client_id": "web-browser-a",
  "expected_revision": 7,
  "operations": [
    {"op": "replace", "path": "/dashboard/title", "value": "华东销售看板"}
  ]
}
```

The server rejects stale revisions with 409, unsafe paths with 422, and unauthorized
actors with 403. Reusing the same operation id with the same content is a harmless
replay; reusing it for different content is a conflict. The ticket is consumed on the
first connection attempt and is never persisted in plaintext.

WebSocket event types:

- `collaboration.ready`
- `presence.changed`
- `operation.accepted`
- `operation.conflict`
- `operation.rejected`
- `collaboration.error`
- `pong`

For one application process, no broker is required. Multi-worker deployments set
`DBGPT_DASHBOARD_COLLAB_REDIS_URL`; durable recovery always comes from the database
operation log, not from Redis.

注意：本地部署的前后端端口和代理配置可能不同，应以实际 `API_BASE_URL` 为准。


## 持续分享与发布别名

`POST /dashboards/{id}/live-share` 为持续更新模式创建受控授权。固定历史链接、最新发布别名和持续授权有不同的数据变化语义；不能将本页固定快照示例泛化到全部公开令牌。管理、有效期和撤销细节以 api.py、live_share.py 和请求模型为准，界面选择见 [用户指南](USER_GUIDE.md)。
