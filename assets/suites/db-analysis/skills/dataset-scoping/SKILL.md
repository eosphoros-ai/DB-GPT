---
name: dataset-scoping
name_zh: 数据集圈定
name_en: Dataset Scoping
description_en: Define the analysis dataset using approved tables and documented join paths. Record the scope, default filters, and metric versions before querying.
command: /dataset
user-invocable: true
description: 智能分析场景的数据集圈定技能。基于语义层表白名单与血缘 join 路径把分析范围固化为数据集卡（dataset_card），禁止从全量库里猜表选表。当用户要求"圈数据集/确定分析范围/看这次分析用哪些表/绑定表范围与口径/切换数据集/数据集太大或口径不清"，或在开始归因、趋势、对比、报告类分析前需要先确定表范围、join 路径、默认过滤与指标版本时使用。触发词：圈数据集、数据集、表范围、白名单、join、血缘、口径绑定、分析范围、dataset。
---

# 数据集圈定（Dataset Scoping）

## 技能目标

在任何多步分析开始之前，把"这次分析能用哪些表、怎么 join、用哪个指标口径、套哪些默认过滤、什么时间粒度"一次性固化成一个**数据集（dataset）**，产出 `dataset_card` 产物与 `dataset_id`。

数据集圈定的本质是**范围约束**，不是查询：

- 表范围来自语义层**表白名单**（含业务域标签过滤），而不是让模型在几百张表里凭表名猜；
- 表间关系来自语义层**血缘 / join 路径**（含 join key 与基数），而不是让模型即兴写 join；
- 口径来自**指标定义（版本 pin）** + **默认过滤** + **时间粒度**，一次声明、后续每步自动注入。

圈定完成后，`dataset_id` 是多步取数的唯一入口：后续每次 `nl2sql` / `sql_execute` 都必须带上它，从而保证跨步口径一致。

## 核心工作流程

1. **确认圈定意图与范围线索**
   - 从用户问句中提取：业务域（交易/销售/库存/会员）、分析对象指标、维度（区域/渠道/品类/客户）、时间窗、可能的过滤（华东区、剔除测试单）。
   - 若用户已指定数据集（如 `dataset_id` 或数据集名称），跳到步骤 6 做校验与复用，不重复圈定。

2. **语义召回候选表与指标**
   - 调用 `semantic_search(query="<业务域 + 指标 + 维度>", types=["table", "metric", "lineage"], top_k=10, layer="mysql_prod")`。
   - 拿到的结果里关注 `metadata.id`、`type`、`tags`、`status`（只用 `published`，草稿不进入检索）。
   - 命中不理想时换关键词再召一次（同义词、英文表名、指标别名），最多 2 次，不要无限召回。

3. **回源权威定义与 join 路径**
   - 调用 `schema_link(entity_ids=[<上一步的 metadata.id 列表>], join_depth=2)`。
   - 从返回中取：表白名单候选（含字段语义与注释）、**join 路径**（`left_table.left_key = right_table.right_key` + 基数 1:N / N:1）、血缘上下游、行级权限与白名单状态。
   - 向量召回只是索引，**权威定义一律以 `schema_link` 回源结果为准**。

4. **裁剪表清单（宁窄勿宽）**
   - 保留：承载指标的事实表、必要的维度表、口径规则中显式要求的表。
   - 剔除：无 join 路径可达的表、`status=draft` 的语义条目、与分析对象无关的同名历史表（如 `_bak`、`_2023`）。
   - 表数量控制在 3~15 张；超过 40 张会触发审批 confirm（`approval_overrides`），此时应缩小业务域或拆成多个数据集。

5. **固化数据集**
   - 调用 `dataset_scope(name="<业务域>-<范围>-<时间窗>", tables=[...], joins=[{left, left_key, right, right_key, cardinality}], semantic_model="mysql_prod", default_filters=["is_deleted=0", "order_type != 'TEST'"], grain="day", pin_metrics=[{metric: "valid_gmv", version: "v2"}])`。
   - `pin_metrics` 取自套件 `semantic.pin.versions`；用户提到但未被 pin 覆盖的指标，取最新 published 版本并记录版本号。
   - 拿到返回的 `dataset_id` 与 `dataset_card` 产物；**记住 `dataset_id`，后续所有步骤都要传它**。

6. **向用户展示并确认**
   - 展示数据集卡要点：表清单（张数 + 关键表名）、join 路径、pin 的指标@版本、默认过滤、时间粒度、覆盖时间范围。
   - 明确询问是否需要调整范围（"是否需要把退款表纳入以分析净额？"），一次确认即可，不要反复追问。

7. **范围变更时重新圈定（而非打补丁）**
   - 用户中途要加维度（如"再按门店拆"）而现有白名单不含门店表 → 重新走步骤 2~5，生成新数据集或在原数据集上追加表（`dataset_scope` 带原 `dataset_id` 做扩展）。
   - 追加表后必须复核：新表的 join 路径是否存在、是否会改变行数基数（1:N join 导致度量翻倍是常见事故）。

## 完整流程示例

用户：「分析本月华东区销售下滑的归因，出图文报告」

```
Step 1: 提取线索 → 业务域=交易/销售，指标=valid_gmv，维度=区域(华东)+渠道+品类，时间窗=本月(含环比/同比基准)

Step 2: semantic_search(query="销售 有效GMV 区域 渠道 品类 订单", types=["table","metric","lineage"], top_k=10, layer="mysql_prod")
  → 命中: metric:valid_gmv(v2, published) / table:ods_order_main / table:ods_order_item
          table:dim_region / table:dim_channel / table:dim_category / lineage:valid_gmv→ods_order_main

Step 3: schema_link(entity_ids=["metric:valid_gmv","table:ods_order_main","table:ods_order_item","table:dim_region","table:dim_channel","table:dim_category"], join_depth=2)
  → 白名单 6 表；join 路径:
     ods_order_main.order_id = ods_order_item.order_id (1:N)
     ods_order_main.region_id = dim_region.region_id (N:1)
     ods_order_main.channel_id = dim_channel.channel_id (N:1)
     ods_order_item.category_id = dim_category.category_id (N:1)
  → 默认过滤: is_deleted=0, order_type<>'TEST', order_status IN ('PAID','SHIPPED','FINISHED')
  → 行级权限: 当前账号可见 region IN ('华东','华南','华北')

Step 4: 裁剪 → 剔除 ods_order_refund（本轮先看下滑总量与结构，退款额作为二次深挖）、dim_store（暂无门店维度需求）
  → 保留 5 表（主表 + 明细表 + 3 张维度表）

Step 5: dataset_scope(
          name="交易域-华东区销售下滑归因-本月",
          tables=["ods_order_main","ods_order_item","dim_region","dim_channel","dim_category"],
          joins=[{"left":"ods_order_main","left_key":"order_id","right":"ods_order_item","right_key":"order_id","cardinality":"1:N"},
                 {"left":"ods_order_main","left_key":"region_id","right":"dim_region","right_key":"region_id","cardinality":"N:1"},
                 {"left":"ods_order_main","left_key":"channel_id","right":"dim_channel","right_key":"channel_id","cardinality":"N:1"},
                 {"left":"ods_order_item","left_key":"category_id","right":"dim_category","right_key":"category_id","cardinality":"N:1"}],
          semantic_model="mysql_prod",
          default_filters=["is_deleted=0","order_type<>'TEST'","order_status IN ('PAID','SHIPPED','FINISHED')"],
          grain="day",
          pin_metrics=[{"metric":"valid_gmv","version":"v2"},{"metric":"paid_order_cnt","version":"v1"}])
  → 返回 dataset_id="ds-trade-east-1024"，产出 dataset_card（左栏可见表清单 + join 图）

Step 6: 回复用户 → "已圈定数据集 ds-trade-east-1024：5 张表（订单主表/明细/区域/渠道/品类），
        口径 valid_gmv@v2（已剔除测试单与未支付单），时间粒度=日，可见区域受行级权限限制。
        是否纳入退款表以分析净额？" → 用户确认不纳入，进入多步取数（见 multi-step-analysis）
```

## 注意事项

- **绝不从全量表清单里选表**：如果 `semantic_search` 与 `schema_link` 都没给出白名单，说明语义层未就绪（降级 DBSummary 模式）。此时必须在回复与报告中显式标注"数据集基于表摘要圈定，口径未经语义层确认"，并把结论置信度下调一档。
- **1:N join 的度量放大**：主表 join 明细表后，直接对主表金额求和会翻倍。圈定时就要标明基数，取数时明确"度量在哪一侧聚合"（先在明细侧聚合到订单粒度，再上卷）。
- **默认过滤只声明一次**：写进 `dataset_scope` 的 `default_filters` 后由核心在每步自动注入；后续任何一步的 SQL 都不要重复手写或删除这些条件，否则跨步口径会漂移。
- **pin 的指标版本不可中途更换**：会话内 `valid_gmv@v2` 一经 pin，全流程一致。若怀疑 v2 口径有误，停下来告知用户并提交语义纠错提案（进待审队列），不要私自改用 v1。
- **数据集不是越大越好**：表越多，schema linking 噪声越大、SQL 越容易错、扫描代价越高。宁可按子问题拆两个数据集，也不要圈一个 40+ 表的巨型数据集。
- **行级权限是硬边界**：`schema_link` 返回的可见范围之外的数据不要尝试查询，也不要向用户暗示可以绕过。
- **圈定结果要落卡**：必须产出 `dataset_card`，它是右栏查看器（表清单白名单态 + join 路径）与报告"数据集与口径说明"章节的数据源。
- 工具只使用套件 `tools.allow` 内的：`semantic_search`、`schema_link`、`dataset_scope`（本技能不直接执行 SQL）。
