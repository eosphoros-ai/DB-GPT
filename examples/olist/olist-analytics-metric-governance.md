---
title: Olist 电商分析口径与数据治理
knowledge_space: Olist_Analytics_Governance_Demo_v2
version: 2.0
updated: 2026-11-03
currency: BRL (R$)
---

# Olist 电商分析口径与数据治理

本文档对应首页 Olist_Ecommerce 两表演示数据库。数据仅包含 2017-01-01（含）至 2018-09-01（不含）的已交付订单；这是演示子集，不代表完整 Olist 数据。全部金额使用 BRL/R$。

## 数据模型

- `demo_orders`：一行一订单，主键 `order_id`。字段为 `purchase_date`、`customer_state`、`product_gmv`、`freight`、`delivery_days`、`on_time`、`review_score`。
- `demo_items`：一行一订单商品，字段为 `order_id`、`category`、`price`。通过 `order_id` 关联订单；一个订单可以有多件商品。
- 数据已在构建时过滤已交付订单，时间用 `purchase_date`，不再具有订单状态字段。
- `product_gmv` 为每单商品价格之和，不含运费；`freight` 为每单运费之和。不可把二者之和称作商品 GMV。
- `delivery_days` 为购买到实际送达的天数；`on_time` 为实际送达不晚于预计送达（1 为准时、0 为逾期）。缺少日期时这些字段可以为空。
- `review_score` 是构建时按订单汇总的平均评价，无评价为空，不可当作 0 分。
- `category` 是已映射英文品类或原品类名，缺失显示 `unmapped`，不得静默丢弃。

## 指标定义

| 指标 | 定义 | 粒度 |
| --- | --- | --- |
| 商品 GMV | `SUM(product_gmv)` | 订单 |
| 已交付订单量 | `COUNT(*)` | 订单 |
| 总运费 | `SUM(freight)` | 订单 |
| 客单价 AOV | 商品 GMV / 订单量 | 订单 |
| 运费占 GMV | 总运费 / 商品 GMV | 订单 |
| 平均配送天数 | `AVG(delivery_days)`，排除空值 | 订单 |
| 准时交付率 | `AVG(on_time)`，排除空值 | 有有效配送日期的订单 |
| 平均评分 | `AVG(review_score)`，排除空值 | 有评价订单 |
| 评价覆盖率 | `COUNT(review_score) / COUNT(*)` | 订单 |
| 品类商品 GMV | `SUM(price)` | 商品明细 |
| 品类订单量 | `COUNT(DISTINCT order_id)` | 品类内订单 |

不同品类可能包含同一订单，品类订单量不能相加当作全局订单量。地域默认指客户州 `customer_state`。库中不包含稳定客户身份、支付方式、分期或卖家字段，不可从该演示计算复购率、支付结构或卖家表现；需要这些分析时应接入完整数据源。

## 推荐 SQL

采用左闭右开时间区间，绑定 `:start_date='2017-01-01'`、`:end_date='2018-09-01'`。

### 总体经营指标

```sql
SELECT COUNT(*) AS delivered_orders,
       SUM(product_gmv) AS product_gmv,
       SUM(freight) AS total_freight,
       SUM(product_gmv) / NULLIF(COUNT(*), 0) AS aov,
       100.0 * SUM(freight) / NULLIF(SUM(product_gmv), 0) AS freight_to_gmv_pct,
       AVG(delivery_days) AS delivery_days,
       100.0 * AVG(on_time) AS on_time_pct,
       AVG(review_score) AS review_score
FROM demo_orders
WHERE purchase_date >= :start_date AND purchase_date < :end_date;
```

### 月度趋势

```sql
SELECT substr(purchase_date, 1, 7) AS month,
       COUNT(*) AS delivered_orders, SUM(product_gmv) AS product_gmv,
       SUM(product_gmv) / NULLIF(COUNT(*), 0) AS aov
FROM demo_orders
WHERE purchase_date >= :start_date AND purchase_date < :end_date
GROUP BY substr(purchase_date, 1, 7) ORDER BY month;
```

### 品类分析

```sql
SELECT i.category, COUNT(DISTINCT i.order_id) AS delivered_orders,
       SUM(i.price) AS product_gmv
FROM demo_items i JOIN demo_orders o ON o.order_id = i.order_id
WHERE o.purchase_date >= :start_date AND o.purchase_date < :end_date
GROUP BY i.category ORDER BY product_gmv DESC;
```

## 查询与解释规范

订单汇总直接查询 `demo_orders`。关联 `demo_items` 后不可再次累加订单级 `product_gmv` 或 `freight`，否则多商品订单会重复计数。月度 AOV 使用月度 GMV 除以月度订单量，不能平均每日 AOV。

报告必须注明演示时间范围、已交付订单范围、币种和指标定义。配送和评价指标同时说明有效样本范围。图表、KPI 和结论须引用同一执行产物与口径。活动或季节因素只能作为解释假设，相关性不能表述为因果。用户要求含运费成交额时须明确标名，并与默认商品 GMV 区分。
