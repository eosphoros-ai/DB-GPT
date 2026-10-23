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

## 安装 pi 运行时

pi CLI **故意不写进** DB-GPT 的任何依赖清单：它是带外运行时，由探针按请求发现。因此全新机器上
项目默认值（`pi`）会回退到内置 DB-GPT 引擎，直到运行时被安装。

一键安装脚本（幂等、无需 sudo）：

```bash
bash scripts/install_pi_runtime.sh
```

脚本先确保 Node ≥ 22.19（依次复用 `DBGPT_HARNESS_PI_NODE`、`PATH`、已有 nvm 安装；都不满足时
经 nvm 安装 Node 22），再把 `@earendil-works/pi-coding-agent` 装进 `~/.dbgpt/pi-runtime`——
探针的已知位置之一。npm 源可用 `NPM_REGISTRY` 覆盖（例如 `https://registry.npmmirror.com`），
安装前缀可用 `PI_PREFIX` 覆盖。

手工等价命令：

```bash
nvm install 22
npm install -g --prefix ~/.dbgpt/pi-runtime @earendil-works/pi-coding-agent
```

可用性按请求探测，装完后 `GET /api/v1/chat/harness/engines` 无需重启服务即显示
`pi.available: true`。注意：服务端持久化偏好（服务启动目录下的 `harness_engine.json`）优先级
高于项目默认值——若它钉住 `dbgpt`，需在设置里重选 pi 或 `PUT /api/v1/chat/harness/engine`。

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
