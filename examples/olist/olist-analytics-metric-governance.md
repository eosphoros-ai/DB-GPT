---
title: Olist 电商分析口径与数据治理
knowledge_space: Olist_Analytics_Governance
version: 1.0
updated: 2026-09-11
currency: BRL (R$)
---

# Olist 电商分析口径与数据治理

本文档是 Olist_Ecommerce 数据库的分析知识库基准。除非分析请求明确覆盖，下列定义、粒度和过滤条件必须优先采用；不得把支付金额或运费误称为商品 GMV。

## 1. 全局分析约定

- 默认订单范围：`orders.order_status = 'delivered'`。
- 默认时间字段：`orders.order_purchase_timestamp`，采用左闭右开区间，例如 2017-01-01 至 2018-08-31 写作 `>= '2017-01-01' AND < '2018-09-01'`。
- 默认货币：巴西雷亚尔（BRL/R$）。
- 订单粒度使用 `COUNT(DISTINCT o.order_id)`；`order_items` 是订单明细粒度，一个订单可有多行商品。
- 任何同时连接 `order_items`、`order_payments`、`order_reviews` 的查询必须先分别在订单粒度聚合，再关联，避免多对多连接造成金额或数量重复。

## 2. 核心指标字典

| 指标 | 默认定义/公式 | 数据表与字段 | 注意事项 |
| --- | --- | --- | --- |
| 商品 GMV | `SUM(order_items.price)` | `orders` + `order_items.price` | **唯一默认 GMV 定义；不含运费。** |
| 总运费 | `SUM(order_items.freight_value)` | `order_items.freight_value` | 是履约/物流成本代理，不属于 GMV。 |
| 含运费成交额 | `SUM(price + freight_value)` | `order_items` | 必须标为“含运费成交额”，不可标成 GMV。 |
| 已交付订单量 | `COUNT(DISTINCT orders.order_id)` | `orders.order_id` | 默认限定 `order_status='delivered'`。 |
| 客单价（AOV） | `商品 GMV / 已交付订单量` | 上述指标 | 不是 `AVG(order_items.price)`；多商品订单需先汇总到订单。 |
| 运费占 GMV | `总运费 / 商品 GMV` | `order_items` | 展示为百分比，分母为商品 GMV。 |
| 每单运费 | `总运费 / 已交付订单量` | `order_items`, `orders` | 与运费占 GMV 是不同指标。 |
| 商品件数 | `COUNT(*)`（在 `order_items` 粒度） | `order_items` | 不等于订单量。 |
| 每单商品件数 | `COUNT(order_items 行数) / 订单量` | `orders` + `order_items` | 明确统计范围。 |
| 支付总额 | `SUM(order_payments.payment_value)` | `order_payments.payment_value` | 与商品 GMV 不必相等；含支付口径差异。 |
| 支付方式金额占比 | 某 `payment_type` 的支付总额 / 全部支付总额 | `order_payments` | 分母、分子均以支付金额计算。 |
| 支付方式订单占比 | 该方式 `COUNT(DISTINCT order_id)` / 全部订单数 | `order_payments` | 一单可有多笔、甚至多种支付方式，比例可能不能直接相加为 100%。 |
| 平均分期数 | `AVG(payment_installments)` | `order_payments` | 是支付记录加权的均值；若需订单加权须先按订单聚合。 |
| 平均配送时长（天） | `julianday(delivered_customer_date)-julianday(purchase_timestamp)` 的平均值 | `orders` | 仅保留实际送达时间非空的已交付订单。 |
| 准时交付率 | `准时送达订单数 / 可比较已交付订单数` | `orders` | 准时：`delivered_customer_date <= estimated_delivery_date`；分母须同时有两日期。 |
| 逾期交付率 | `逾期送达订单数 / 可比较已交付订单数` | `orders` | 逾期：`delivered_customer_date > estimated_delivery_date`。 |
| 平均评价 | `AVG(order_reviews.review_score)` | `order_reviews.review_score` | 明确是“有评价订单”的评分，不能将无评价当 0 分。 |
| 评价覆盖率 | `有评价的订单数 / 目标订单数` | `orders` + `order_reviews` | 使用 `COUNT(DISTINCT review.order_id)`。 |
| 复购客户数 | 在观察窗内 `COUNT(DISTINCT order_id) >= 2` 的客户数 | `orders.customer_id` | Olist 的 `customer_id` 是订单级客户标识；跨订单复购优先使用稳定的 `customer_unique_id`。 |
| 复购率 | 复购客户数 / 有至少一笔目标订单的客户数 | `customers.customer_unique_id` + `orders` | 必须写明观察窗与客户身份字段。 |

## 3. 数据模型与关联

### 3.1 主业务链路

`customers` 1--N `orders` 1--N `order_items`

- `customers.customer_id = orders.customer_id`
- `orders.order_id = order_items.order_id`
- `order_items.product_id = products.product_id`
- `products.product_category_name = product_category_translation.product_category_name`
- `orders.order_id = order_payments.order_id`
- `orders.order_id = order_reviews.order_id`
- `order_items.seller_id = sellers.seller_id`

### 3.2 表用途

| 表 | 分析粒度 | 常用字段 | 典型用途 |
| --- | --- | --- | --- |
| `orders` | 一行一订单 | `order_status`, 购买/批准/发货/送达/预计送达时间 | 订单范围、履约时长、准时性。 |
| `order_items` | 一行一订单商品 | `price`, `freight_value`, `product_id`, `seller_id` | 商品 GMV、运费、品类、卖家。 |
| `order_payments` | 一行一支付记录 | `payment_type`, `payment_installments`, `payment_value` | 支付结构与分期。 |
| `order_reviews` | 一行一评价记录 | `review_score`, 评论时间 | 满意度与履约关系。 |
| `customers` | 一行一订单收货客户记录 | `customer_unique_id`, `customer_state`, `customer_city` | 地域与复购。 |
| `products` | 一行一商品 | `product_category_name` | 品类映射。 |
| `product_category_translation` | 一行一品类映射 | 英文品类名 | 可读品类报表。 |
| `sellers` | 一行一卖家 | `seller_state`, `seller_city` | 供给/卖家地域分析。 |
| `geolocation` | 多行一邮编前缀 | 经纬度、城市、州 | 地理可视化；连接前需处理重复邮编。 |

## 4. 推荐 SQL 模式

### 4.1 总体经营指标

```sql
SELECT
  COUNT(DISTINCT o.order_id) AS delivered_orders,
  SUM(oi.price) AS product_gmv,
  SUM(oi.freight_value) AS total_freight,
  1.0 * SUM(oi.price) / COUNT(DISTINCT o.order_id) AS aov,
  100.0 * SUM(oi.freight_value) / NULLIF(SUM(oi.price), 0) AS freight_to_gmv_pct
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= :start_date
  AND o.order_purchase_timestamp < :end_date;
```

### 4.2 月度趋势

以 `substr(o.order_purchase_timestamp, 1, 7)`（SQLite）或等价的月截断函数分组。月度 AOV 应为月度商品 GMV除以月度去重订单量，不能平均每日/明细 AOV。

### 4.3 先聚合，后连接

当需要“订单商品金额 + 支付方式 + 评价”时：

1. `item_by_order`：按 `order_id` 汇总 `SUM(price)` 和 `SUM(freight_value)`；
2. `payment_by_order`：按 `order_id` 汇总支付金额或选择目标支付维度；
3. `review_by_order`：按 `order_id` 汇总/选择评价；
4. 三个订单粒度 CTE 再连接 `orders`。

这样可避免一笔包含多商品、多个支付记录的订单被金额倍增。

## 5. 分析模板与解释规范

- **趋势分析**：同时给出月度商品 GMV、订单量和 AOV；对峰值先说明时间和数值，再将活动/季节解释为假设，除非有外部证据。
- **品类分析**：以商品 GMV 排序；应同时给出订单量、AOV、GMV 占比。未映射品类须显示为“未映射/未知”，不可静默丢弃。
- **地域分析**：客户州（需求侧）与卖家州（供给侧）必须明确区分；默认“州表现”指客户 `customer_state`。
- **履约与评分**：比较准时与逾期订单时，统一使用同一时间窗和有有效送达/预计日期的订单；评分仅在有评价的订单子集上计算，并同时给出覆盖率。
- **支付分析**：金额占比默认用 `payment_value`；若展示“支付 GMV”，必须改称“支付金额”。
- **结论**：数值结论需标注其指标口径、时间范围与订单状态；相关性不得表述为因果性。

## 6. 质量检查清单

1. 订单状态过滤是否明确且与指标一致？
2. 时间范围是否为左闭右开，避免遗漏日末订单？
3. GMV 是否严格为 `SUM(order_items.price)`，没有加入运费或 `payment_value`？
4. 订单量是否 `COUNT(DISTINCT order_id)`？
5. 多明细/多支付/多评价表是否先在订单粒度聚合？
6. 配送时长、准时率是否排除了缺失日期？
7. 客户复购是否使用 `customer_unique_id` 而非 `customer_id`？
8. 品类翻译或地理映射的缺失值是否可见？
9. 图表、KPI 与结论是否引用同一执行产物和同一口径？

## 7. 口径变更规则

若用户要求“含运费 GMV”“支付 GMV”或其他非默认定义，报告必须：

1. 在指标名中明确新口径；
2. 同时保留默认商品 GMV（若用于比较）；
3. 在图表标题、KPI 和结论中使用一致名称；
4. 将变更作为报告元数据和证据的一部分。
