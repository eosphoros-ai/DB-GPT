# Olist 真实多表 Dashboard 案例

## 1. 这个案例证明什么

Walmart 合成案例适合演示筛选、编辑和发布，但单表不足以证明真实 BI
场景中的数据建模能力。本案例使用一份公开、匿名化、包含多个关联 CSV
的数据集，验证完整链路：

```text
Olist 原始 CSV
→ 关系表加载（SQLite / MySQL）
→ 指标口径和联接规则
→ Dashboard Schema 1.3
→ 参数化 SQL、安全校验和组件执行
→ 同一组标准答案对拍
```

SQLite 与 MySQL 使用相同 CSV、相同表结构、相同业务口径和同一份标准
答案。数据库方言差异只留在加载器和日期函数的受控分支中。

2026-08-24 实机复测环境为 MySQL Community Server 8.4.11，绑定本机回环地址；
七组标准查询和六个 Dashboard 组件均与 SQLite 一致。完整命令和结果见
`V3_7_OLIST_TEST_REPORT.md`。

## 2. 来源、版本和许可证

- 数据集：Brazilian E-Commerce Public Dataset by Olist
- 页面：https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- Kaggle 数据集版本：2
- 页面更新时间：2021-10-01
- 许可证：CC BY-NC-SA 4.0
- 时间范围：2016-09-04 至 2018-10-17
- 压缩包 SHA-256：`967E41E04FC306FE604E2A693F488995A8B41E5047418F8A5C8E4ABD6DECA784`

完整下载 URL、文件名、大小和校验值保存在
`examples/dashboard/olist/source-manifest.json`。原始 CSV 和生成的数据库不进入
Git；商业使用前还需单独复核非商业、相同方式共享等许可证条件。

## 3. 关系模型

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--o{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : describes
    SELLERS ||--o{ ORDER_ITEMS : fulfils
    ORDERS ||--o{ PAYMENTS : paid_by
    ORDERS ||--o{ REVIEWS : receives
    PRODUCTS }o--|| CATEGORY_TRANSLATION : translates

    CUSTOMERS {
      string customer_id PK
      string customer_unique_id
      string customer_state
    }
    ORDERS {
      string order_id PK
      string customer_id FK
      string order_status
      datetime order_purchase_timestamp
      datetime order_delivered_customer_date
      datetime order_estimated_delivery_date
    }
    ORDER_ITEMS {
      string order_id PK,FK
      int order_item_id PK
      string product_id FK
      string seller_id FK
      decimal price
      decimal freight_value
    }
    PAYMENTS {
      string order_id PK,FK
      int payment_sequential PK
      string payment_type
      decimal payment_value
    }
    REVIEWS {
      string review_id PK
      string order_id PK,FK
      int review_score
    }
```

默认加载八张核心表；约一百万行的地理坐标表是可选项，因为当前看板没有
地图组件，不让无关数据拖慢最小复现链路。

## 4. 数据量和质量观察

SQLite 实际导入记录：

| 表 | 行数 |
|---|---:|
| customers | 99,441 |
| products | 32,951 |
| sellers | 3,095 |
| category translations | 71 |
| orders | 99,441 |
| order items | 112,650 |
| payments | 103,886 |
| reviews | 99,224 |
| 合计 | 550,759 |

数据质量差异必须显式说明：

- `order_status='delivered'` 有 96,478 条；其中 96,476 条具有实际送达时间。
- 99,441 笔订单中，并不是每一笔都一定有支付、订单项或评价记录。
- 同一订单可能有多条支付、多个商品和多条评价。直接同时联接会产生笛卡尔式
  金额放大，因此查询先分别聚合至订单粒度。
- 客户表同时包含订单级 `customer_id` 与跨订单去重用
  `customer_unique_id`；“客户数”必须说明采用哪一种。

## 5. 七个标准业务问题与答案

以下结果来自固定源文件的完整 SQLite 数据库，保存在
`examples/dashboard/olist/gold_answers.json`，MySQL 必须得到同样结果。

1. 订单总数 99,441；状态已送达 96,478；唯一客户 96,096；支付总额
   R$16,008,872.12。
2. 月度支付峰值出现在 2017-11：7,544 笔订单，R$1,194,882.80。
3. 商品成交额最高的英文品类为 `health_beauty`：8,836 笔订单，
   R$1,258,681.34。
4. 支付贡献最高的客户州为 SP：41,746 笔订单，R$5,998,226.96。
5. 有送达时间的 96,476 笔订单平均 12.5587 天送达；7,827 笔晚于预计日期，
   晚达率 8.1129%。
6. 1 分评价的平均送达时间 21.3114 天、晚达率 37.7723%；5 分评价分别为
   10.6886 天和 2.9986%。这说明履约与评价强相关，但不是因果证明。
7. 信用卡支付 R$12,542,084.19，覆盖 76,505 笔订单，是主要支付方式。

完整月度、品类、地区、评分和支付方式明细以 JSON 文件为准，避免把截屏中的
近似值当成测试标准。

## 6. Dashboard 设计

`examples/dashboard/schemas/olist-ecommerce.schema.json` 包含：

- 全局筛选：购买日期、客户州多选、订单状态单选；
- KPI：支付总额、已送达率；
- 双轴图：月度订单量与支付总额；
- 横向条形图：Top 10 商品品类成交额；
- 柱状图：评价分数分布；
- 明细表：订单、支付、商品、运费与评分核对。

支付总额与商品成交额是两个不同口径：前者来自支付记录，后者只合计商品价格且
不含运费。看板不会把二者混称为“销售额”。

## 7. 复现命令

```powershell
python examples/dashboard/olist/download_olist.py

python examples/dashboard/olist/load_olist.py `
  --source-dir examples/dashboard/olist/data/raw/extracted `
  --sqlite examples/dashboard/olist/data/generated/olist.db `
  --replace

python examples/dashboard/olist/verify_olist.py `
  --sqlite examples/dashboard/olist/data/generated/olist.db

python examples/dashboard/olist/verify_dashboard_schema.py `
  --sqlite examples/dashboard/olist/data/generated/olist.db
```

MySQL 使用同一加载器：

```powershell
python examples/dashboard/olist/load_olist.py `
  --source-dir examples/dashboard/olist/data/raw/extracted `
  --mysql-url "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/olist?charset=utf8mb4" `
  --replace

python examples/dashboard/olist/verify_olist.py `
  --mysql-url "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/olist?charset=utf8mb4"

python examples/dashboard/olist/verify_dashboard_schema.py `
  --mysql-url "mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/olist?charset=utf8mb4"
```

口令只通过本机环境或临时命令传入，不写入仓库、文档产物或测试日志。
独立 Schema 校验脚本会优先加载当前 checkout 的 `packages/*/src`，即使复用的
虚拟环境还保留旧 editable install，也不会误拿旧版本 Dashboard 模型验新代码。

## 8. 验收标准

- 下载文件与固定 SHA-256 一致；
- 八表行数合理，外键关系可联接；
- 七组答案在 SQLite/MySQL 上逐字段一致；
- Schema 的六个组件都能通过 DB-GPT SQL 安全层并执行；
- 更改日期、州和订单状态时所有绑定组件同步变化；
- 任一组件失败不掩盖其他组件结果；
- 原始数据、数据库文件和凭据不进入 Git。

该案例提供数据正确性和跨数据库证据；Walmart/Apple 继续承担发布、分享、
批注和可视编辑的完整交互回归，两类证据互补而不是互相替代。
