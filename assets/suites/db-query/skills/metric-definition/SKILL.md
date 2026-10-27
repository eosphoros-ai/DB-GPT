---
name: metric-definition
name_zh: 指标口径查询
command: /metric
description: 查询指标定义、版本与默认过滤，按标识回源权威语义口径。
user-invocable: true
argument-hint-zh: 指标名或口径问题（如 valid_gmv 的定义与版本）
---

# 指标口径查询

读取并遵循[语义召回与权威口径加载](../semantic-linking/SKILL.md)。
将用户问题作为指标查询参数，返回指标定义、版本、默认过滤及来源。
未发布或不可获得的指标需明确说明，不得自创公式充当权威口径。
此命令只查询口径，不自动执行取数 SQL。
