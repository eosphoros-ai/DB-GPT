---
title: 语义中心上手
---

# 为第一次取数准备定义

先确认**数据源**中的数据库连接可用，再与熟悉业务的负责人审核定义。

## 1. 登记并同步

打开**语义层**，使用登记连接操作，将现有连接补充为数据空间。查看同步结果和失败连接。打开目标空间，在数据库结构变更后同步元数据。

![登记数据空间与同步操作](/img/data-agent/zh-CN/semantic-spaces.png)

核对预期表字段是否齐全。连接成功不代表元数据快照完整、实时。

## 2. 选择激活与采样选项

通过空间的激活操作，检查采样上限和是否生成草稿。采样会读取数据值，应根据敏感性和负载选择范围。Embedding 模型选项不代表语义只读工具已经使用向量搜索。

激活是空间生命周期操作，不会自动发布所有草稿，也不建立数据库行级权限。

## 3. 审核业务语义

需要时生成草稿，在业务语义页确认或拒绝提议。检查字段目标与同义词，尤其是“日期”“来源”“有效订单”等易歧义概念。

模型生成的描述是候选定义。审核依据应是业务规则，不只是文字是否顺畅。

## 4. 审核并发布指标

在**指标**页检查口径，记录必要的公式、单位、粒度、时间字段、过滤、去重和依赖，再发布。

当前界面提供检查与发布，没有完整指标编辑器。生成的 `COUNT(*)` 草稿只是起点，
不是现成业务口径。自定义指标应通过下方 API 或部署中维护的语义初始化流程准备，再审核发布。

![指标与发布状态](/img/data-agent/zh-CN/semantic-metrics.png)

发布生成版本快照。Agent 读取已发布快照，不回退读取可编辑草稿正文。变更后发布新版本并核对引用。

## 5. 在对话中使用

选择**智能取数**或**智能分析**，绑定同一数据库，要求先读取已发布指标并引用版本。详见[与 Data Agent 配合](./using-with-data-agent.md)。

找不到指标时核对数据库、发布状态、名称与版本，参见[排查指南](./troubleshooting.md)。

## 通过 API 准备自定义指标

运维与集成使用以下准备接口：

| 方法与路径 | 用途 |
| --- | --- |
| `GET /api/v1/semantic/spaces` | 查询连接对应的数据空间 ID |
| `GET /api/v1/semantic/spaces/{ds_id}/tables` | 查询同步后的表 ID，作为定义目标 |
| `POST /api/v1/semantic/spaces/{ds_id}/entries` | 创建业务定义草稿 |
| `POST /api/v1/semantic/entries/{entry_id}/review` | 确认、修改或拒绝定义 |
| `POST /api/v1/semantic/spaces/{ds_id}/metrics` | 创建指标草稿 |
| `POST /api/v1/semantic/metrics/{metric_id}/publish` | 发布指标快照 |
| `GET /api/v1/semantic/spaces/{ds_id}/metrics/{metric_id}/versions/{version}` | 查看精确版本快照 |

准备表定义时，将 `123` 替换为表清单接口返回的 `orders` 表 ID，再向 entries 接口提交：

```json
{
  "entry_type": "table",
  "target_id": 123,
  "entry_name": "orders",
  "entry_comment": "订单记录，包含真实与测试订单。",
  "synonyms": ["订单记录"],
  "entry_definition": "有效订单限定 tenant_id=1、is_test=0、is_deleted=0、status IN ('PAID','COMPLETED')。"
}
```

创建返回定义 ID。业务审核后，向对应 review 接口提交 `{"action":"confirm"}`；
错误提议使用 `{"action":"reject"}`。`modify` 操作通过 `updates` 修改
`entry_comment`、`synonyms` 或 `entry_definition`，并将定义返回草稿状态，需重新审核确认。

同一数据库可参考以下指标创建请求体：

```json
{
  "metric_name": "eligible_order_count",
  "metric_type": "atomic",
  "metric_comment": "租户1真实已支付或已完成订单数。",
  "formula": "COUNT(*)",
  "metric_definition": "按 order_id 对订单只计一次。限定 tenant_id=1、is_test=0、is_deleted=0、status IN ('PAID','COMPLETED')。使用 orders.created_at 归属时间，按请求的左闭右开区间过滤，单位为订单。",
  "dimensions": ["orders.channel_id"],
  "base_metrics": []
}
```

按真实结构调整并审核请求体。创建返回指标 ID，向对应 publish 接口提交
`{"change_note":"首次业务审核后的定义"}`，记录返回版本，并读取精确快照再用于取数。
响应使用 DB-GPT 标准结果封装，鉴权遵循部署配置。文档示例不会自动创建资源。

上述公共路由不包含通用指标修改接口，不应假设界面能编辑现有正文或管理所有历史版本。
变更应通过维护的初始化流程协调，并保留已有引用。
