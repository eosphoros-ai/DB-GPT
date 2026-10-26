---
name: dashboard-filter-configuration
description: 配置当前看板的全局筛选器，使真实字段、可选值、组件查询参数及分享页筛选一致，并验证空选、单选和多选语义。
---

# 全局筛选配置

依据当前 annotation、saved_schema 和授权 source_context 生成修改；历史建议只解释用户意图，不能替代当前目标或数据证据。配置已有筛选器时保留其 ID。

- 从零新增筛选器时，选择未使用的 ID，用 `{"op":"add","path":"/filters/-","value":完整筛选对象}` 创建。`/filters/by-id/筛选ID` 只定位已经存在或本批前序操作已创建的对象，不能用它直接创建新 ID。先创建定义，再配置受影响组件的查询与发布映射；不要把“新增筛选器”误写成“修改不存在的筛选器”。

- 同步修改筛选的 label、field、type、default、options，以及受影响组件的 query.filter_parameters、SQL、default_parameters 和已有 publication.filter_fields。仅改下拉框名称不算完成。
- field 必须来自实际数据。可选值优先使用 distinct_values；truncated=true 时它不是完整枚举，不能声称提供全部选项。保留已有可信选项。不要把样本中的第一种类别当成唯一值。
- 筛选对象没有 targets 字段。作用范围由组件 query.filter_parameters 是否包含该筛选 ID 决定。选择业务上适用的组件；待配置的空查询组件可以明确排除。不要让筛选作用于无该维度且无法保持原口径的组件。
- 用户未限定范围的“全局筛选”应联动所有同源且基础表拥有该维度的已配置组件，包括 KPI、趋势、仪表和新图表。“最小修改方案”是减少无关属性变化，不能据此把全局筛选缩成只影响少数几个组件。规划参考列出的部分组件不是用户授权的范围限制。
- query.filter_parameters 的键是筛选 ID，值为 SQL 参数名字符串；范围绑定用 {start_parameter,end_parameter}。默认参数是对象。不能写成 field→filter_id 或数组。
- multi_select 的 default 是 []，绑定参数默认值也是 []。SQL 只写 `category IN (:category)` 或 NOT IN；后端已将空数组解释为不过滤，并安全展开多个值。**不要**写 `:category='all'`、等号比较、IS NULL 或把数组参数用于 IN 之外的表达式。单选的 all 哨兵与多选数组语义不同。
- 单选可沿用 `(:segment='all' OR segment=:segment)`。日期/数值范围使用两个参数并保留边界语义，不把多选套成单选。
- 保持每个图表的分组、聚合、分母和单位；分类饼图筛选后只显示选中扇区是正常结果，不强行保持所有类别。
- 原查询没有选出新筛选字段，不代表不能联动。基础表含该维度时，应补充预聚合粒度与参数。同一查询/指标的 KPI、仪表盘等不同展示必须保持相同作用范围，不能让指标卡变了而对应仪表盘不变；只有用户明确要求差异范围时才排除其中一个。
- 发布数据查询不含筛选占位符，返回完整筛选粒度的原料；新增筛选维度时补全其 output_fields、GROUP BY 粒度与 filter_fields。最终 group_by 与 measures.output_field 必须恰好生成 output_columns。平均/比例不能直接对已算好的比例求和，应保留分子与分母再聚合。
- 区分冻结原料字段与最终显示字段。若原 KPI 的 query.output_fields 只有 value，新增 channel 筛选后仍保持 publication.group_by=[]、output_columns=["value"]。channel 只需存在于 publication.query.output_fields 与 filter_fields 中；筛选后再求一个总 value，不把 channel 加入 KPI 的最终分组或输出。示例：publication.query 返回 channel,amount；filter_fields={"channel_filter":"channel"}；group_by=[]；measures=[{"source_field":"amount","output_field":"value","aggregation":"sum"}]；output_columns=["value"]。
- 不移除 publication、不删其他筛选或组件来绕过验证。用稳定 ID 路径 `/filters/by-id/筛选ID` 和 `/widgets/by-id/组件ID/query`、`/widgets/by-id/组件ID/publication`。

收到具体校验反馈时，在相同目标上修正参数和字段。服务端将检查空选、单值、多值查询；只有验证成功的方案才供用户应用。
