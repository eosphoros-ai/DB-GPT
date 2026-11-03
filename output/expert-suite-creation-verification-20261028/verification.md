# 专家套件智能创建验证

日期：2026-10-28

已实现用户批准的 P0 流程：专家套件页「智能创建」→ 创建对话 → 草稿 → 结构校验 → 套件产物卡片 → 预览 / 编辑 / 下载 ZIP → 用户点击安装 → 已安装套件可选择并开始业务对话。DBGPT 与 PI 共用草稿工具、包格式与安装服务。

## 实现范围

- 创建对话加载专用创建技能，时间线显示「读取技能」，支持历史回放。
- 草稿使用独立目录与修订号；修改需要匹配修订，避免覆盖新版本。
- 校验套件声明、技能、SOP、文件引用、工具依赖、必需资源和输出契约；包中仅接受 Markdown / JSON。
- 套件产物冻结修订并保存 ZIP 摘要。卡片可展开查看正文、修改草稿并生成后继版本；旧产物仍保持不变。
- 安装由卡片按钮发起，模型没有安装工具。安装包含登记、审计、重复安装处理与失败恢复。
- 需要数据库的套件可在卡片配置数据源，并在新业务对话中恢复绑定。
- 创建模式只开放读取材料及受控草稿写入工具；PI 排除原生 bash / write / edit，并在进入或取消创建模式时重建运行实例。
- 中英文、窄屏、鼠标取消与键盘取消均有覆盖。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 后端插件、草稿、安装恢复、共享工具、绑定、产物与 PI 流式回归 | 113 tests + 19 subtests 通过 |
| 前端套件卡片、产物解析、时间线与输入菜单 | 57 tests 通过 |
| 浏览器完整交互 | 4 项通过；覆盖 DBGPT / PI 产物形态、预览编辑、下载安装、历史回放、取消与英文 390px |
| 最后修改的共享工具、PI 桥接与流式文件 Ruff | 通过 |
| 本地主服务 | 已重启；两种引擎可用，前端首页响应正常 |

前端全量 TypeScript 检查仍被仓库已有的 models 类型及其他页面错误阻断；本次套件卡片与左侧面板相关错误已处理。没有将全量构建标记为通过。

## 真实模型创建

使用本地运行服务与 `deepseek-v4-flash`，两个引擎均完成真实工具调用并生成校验状态为 `ready` 的专家套件。

| 引擎 | 套件 | 文件数 | 产物 ID | 会话 ID |
| --- | --- | --- | --- | --- |
| DBGPT | weekly-office-dbgpt-verification | 5 | 54011cc79a1a4dcbbd74ff4fcf1ccbeb | cea2b936239f4e588ff25a71249ed2e3 |
| PI | weekly-office-pi-verification | 7 | b150a72f2f1a44b7967fbc0aabffc6e2 | 062500a4b9a74586b27be2163300169d |
| PI（最终权限调整后） | meeting-actions-guard-verification | 4 | 8dade94a05bb495292444a9374f6ab3f | 9d8fd804ed1345bca3e0915a9f7b677e |

两个真实套件均包含两个技能，历史接口保留套件产物和创建技能读取步骤。验证套件未自动安装。服务重启后，产物接口仍能读取上述文件和校验结果。

最终权限调整后，PI 用真实模型在 30 秒内再次完成四个文件的创建、校验和打包，未调用 bash / write / edit / code / 技能脚本。部署后的四项浏览器验证也再次通过，用时 25.8 秒。

浏览器用真实后端验证草稿、包、下载、安装与配置操作；聊天 SSE 使用确定性样本分别覆盖 DBGPT 类型化输出与 PI 工具结果封装。真实模型生成证据与这些浏览器交互验证分别记录，避免把模拟输出计为真实模型测试。

## 可查看的证据

- [DBGPT 套件预览](dbgpt-suite-preview.png)、[PI 套件预览](pi-suite-preview.png)、[安装完成](pi-installed-suite.png)、[英文窄屏](english-narrow-creation.png)。
- [最终后端测试](suite-creation-final-guards.log)、[前端测试](suite-creation-final-frontend.log)、[部署后浏览器验证](suite-creation-browser-deployed.log)。
- [真实创建与历史回放记录](suite-creation-real-history.json)、[最终 PI 真实调用记录](suite-creation-guard-real-summary.json)。
- 真实生成的包：[DBGPT 周报套件](weekly-office-dbgpt-verification.zip)、[PI 周报套件](weekly-office-pi-verification.zip)、[最终 PI 行动清单套件](meeting-actions-guard-verification.zip)。

## 当前边界

安装作用域为当前实例。结构校验通过不等同于业务任务试跑通过，卡片会保留「尚未执行真实任务试跑」提示。P0 不包含组织级发布审批、多人市场分发和自动业务试跑。

入口：`http://127.0.0.1:3000/construct/suites/` →「智能创建」。
