---
title: 插件包格式参考
---

# 插件包格式参考

当前加载器支持 `.dbgpt-plugin/plugin.json`、兼容的 `.qwenwork-plugin/plugin.json` 和旧版 `suite.yaml`。新包优先使用原生 manifest。

```text
my-data-plugin/
  .dbgpt-plugin/
    plugin.json
  skills/
    scoped-query/
      SKILL.md
  prompts/
    playbook.md
```

起始 manifest 示例：

```json
{
  "name": "my-data-plugin",
  "version": "1.0.0",
  "displayName": "Scoped Data Query",
  "displayNameCn": "限定范围取数",
  "descriptionEn": "Answer bounded questions from a selected database.",
  "descriptionZh": "基于选定数据库回答限定范围的数据问题。",
  "skills": ["skills/scoped-query"],
  "dbgpt": {
    "scenario_id": "query",
    "execution": "react",
    "sop": "prompts/playbook.md",
    "required_resources": ["database"]
  }
}
```

这只是布局示例，不是完整可运行插件。补齐引用资源，并在目标版本验证。

## 字段与执行支持

`name` 使用稳定且唯一的名称；版本和双语展示字段用于目录。`skills` 与 `dbgpt.sop` 引用包内资源；`dbgpt` 保存场景、执行、资源、推荐问题及工具声明。

官方 manifest 还包含语义策略、审批覆盖和产物契约。逐项核对实际消费与执行支持：声明版本 pin、扫描阈值或行级规则，不意味着语义只读工具已强制这些控制。

## 打包与验证

将 manifest 和资源一起压缩，路径限制在包内，不包含凭据、环境文件或私人报告。通过插件中心添加 ZIP，检查卡片与已加载 Skill，再运行小范围任务。

详细兼容依据是 `packages/dbgpt-serve/src/dbgpt_serve/plugins/loader.py` 及相邻测试。对外描述的能力应有真实工具结果支撑。
