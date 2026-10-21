# 使用 Harness

## 选择引擎

点击侧栏底部的 **设置（Setting）**。弹层内含管理入口与 **HARNESS** 分区：每个引擎带实时
可用性状态，当前选中项打勾，并附一行作用域说明。

![Setting 弹层中的 Harness 选择](/img/harness/zh/fig-01-settings-harness.png)

- 选择引擎后在服务端持久化，对任意标签页的**新任务**生效。
- 不可用引擎置灰并显示探测原因（如缺 pi CLI、Node 版本过旧）；点击置灰项以 toast 拒绝，
  不会跑到一半才失败。
- 可用性按请求探测：安装 pi CLI 后无需重启服务即生效。

## pi 前置条件

pi 引擎按会话拉起 pi CLI 子进程：

- `pi` 可执行文件需可被发现：`DBGPT_HARNESS_PI_CLI` 环境变量、`PATH` 上的 `pi`、或已知安装位置；
  Node ≥ 22.19 从 `PATH` 或 nvm 安装中解析（`DBGPT_HARNESS_PI_NODE` 可显式指定）。
- 每个会话拥有隔离工作区（`pi_workspace/<conv_id>`）与隔离 agent 目录；DB-GPT 内置工具以原生
  工具形式桥接进 pi，经内部 token 保护端点在服务端执行。
- 破坏性内置工具默认排除（`DBGPT_HARNESS_PI_EXCLUDED_TOOLS`，默认 `bash`），与 dbgpt 引擎
  的 containment 对齐。

## 读一轮运行

无论哪个引擎执行，会话表面完全一致：

- **时间线**——意图行、分组工具行与观察随运行流式呈现。
- **轨迹（Trace）**——产物 rail 的 Trace 入口打开合成 span 树（思考、工具动作、terminate），
  pi 运行同样支持。
- **产物**——取数结果集渲染为内联数据卡：含执行 SQL、编辑重跑入口与 CSV / Excel 导出；
  HTML 报告在 rail 内预览。

![pi 一轮运行产出的取数产物](/img/harness/zh/fig-02-query-artifact.png)

- **审批**——高危调用弹出同一确认 dock；session/always 记忆跨引擎行为一致。

## 请求级覆盖（API）

程序化调用方可按请求钉死引擎：

```json
{
  "conv_uid": "<会话>",
  "user_input": "销售额前 5 的门店",
  "ext_info": { "harness_engine": "pi" }
}
```

未知值回落服务端偏好；显式指定但不可用时，在任何 Agent 工作开始之前以终止消息快速失败。

## 排障

- `GET /api/v1/chat/harness/engines` 返回弹层渲染所用的可用性清单——看 pi 为何置灰的最快方式。
- 回合"开始即结束"并提示引擎不可用，说明偏好指向的引擎探测已失败（CLI 被删、Node 降级）；
  在设置中切回 DB-GPT 或修复安装。
