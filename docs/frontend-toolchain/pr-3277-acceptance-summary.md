# PR #3277 验收总表 — 2026-10-01

交付范围：DB-GPT 前端工具链从 Next.js 13.4.7 升至 **16.3.0**，含兼容性修复及回归证据；不交付 #3278 的 Dashboard 功能。本文用于 PR 审阅与 OSPP 结项材料，材料完成不以 PR 合并为前提。下面均为既有结果，本轮仅整理说明。

前端受测源码 **`763eba34`**，Node **20.19.6** / npm **10.8.2**；九项联调来源 **`80d7c703`**。审阅时 #3277 HEAD 为 **`7ac93ead`**，#3278 为 **`f1977798`**；对照基线 **`d1d398eb`**。完整 SHA 与运行环境见各项证据。

| 类别 | 项目与结果 | 版本 / 证据 | 剩余限制 |
| --- | --- | --- | --- |
| 已验证通过 | typecheck、build/start、单测通过；Ubuntu/macOS 安装、构建和静态导出通过 | `763eba34`；[CI](https://github.com/jcsdxhe/DB-GPT/actions/runs/36667552757)、[运行记录](evidence/pr-3277/review-followup.json) | 仅适用于所记录平台、版本与部署模式 |
| 已验证通过 | dev：Chromium **42/42**；build + start：Chromium **42/42**、Firefox **41/41**、WebKit **41/41**；接受的四轮浏览器诊断均为 0 | `763eba34`；[清单及模式](pr-3277-regression.md#build-development-and-browser-checklist) | 固定 API；Firefox/WebKit 不含组合剪贴板用例；页面渲染不等于完整 CRUD |
| 已验证通过 | 两项等待超时的原始记录保留；20 轮复跑 **40/40** | `763eba34`；[超时调查](pr-3277-flaky-investigation.md) | 根因未确认；不能据此排除升级相关性 |
| 已验证通过 | 九项真实后端联调通过，独立记录来源 | `80d7c703`；[原始结果](evidence/pr-3277/summary.json)、[来源审计](evidence/pr-3277/review-audit.json) | NODE_OPTIONS / JSON 修复后未重跑；不是 Dashboard 验收 |
| 已归因的存量问题 | ESLint **86 警告、0 错误**；同一 ESLint 9 配置对照基线，**新增 0** | `763eba34` 对照 `d1d398eb`；[归因](evidence/pr-3277/baseline-followup.json) | 由已有日志核对；未清零，也未重新运行 lint |
| 已归因的存量问题 | 旧 evaluation 接口及原远程 embedding 配置返回 **404** | `80d7c703`；[联调边界](pr-3277-regression.md#earlier-live-checks--no-api-fixtures-source-80d7c703) | 后端路径未改；本地模型只验证功能链路，不验证远程配置或检索质量 |
| 未覆盖 / 无有效样本 | 旧版安装、dev 启动成功；两个页面导航超过 120 秒，**可比样本 0** | `d1d398eb`；[对照报告](pr-3277-baseline-comparison.md) | 不是旧版性能结论；直接接口数据不能解释 8.27 秒测试桩延迟 |
| 未覆盖 / 无有效样本 | 第三方 OAuth、外部连接器、非 SQLite 实例缺少测试资源；真机未验证 | `763eba34` / `80d7c703`；[覆盖限制](pr-3277-regression.md#explicit-remaining-coverage-limits) | iPhone 真机验证已取消，不列后续待办；全量基准和破坏性 CRUD 未覆盖 |
| 未覆盖 / 无有效样本 | 已审阅回滚步骤；**未执行回滚、未验证回滚后 CI** | `7ac93ead` / `f1977798`；[回滚说明](pr-3277-regression.md#rollback-scope-and-limits--inspected-not-executed) | 取决于合并方式与共享文件；13.4.7 同样受 Windows RCE 影响 |
| 等待维护者决定 | 两 PR **90 个重叠路径**已公开更正；接续、合并顺序及是否拆分待确认 | `7ac93ead` / `f1977798`；[#3277](https://github.com/eosphoros-ai/DB-GPT/pull/3277)、[#3278](https://github.com/eosphoros-ai/DB-GPT/pull/3278) | 两 PR 尚未合并；不能保证独立回滚；本轮未拆分或改分支 |
| 等待维护者决定 | 是否要求安全补丁升级；当前 **16.3.0** 仍有适用的未修复公告 | `16.3.0`；[安全适用性](pr-3277-security-advisories.md#september-30-release-follow-up--checked-2026-10-01) | Windows RCE、自托管 SSG 缓存、dev MCP 分别适用；images.remotePatterns 未配置，相关 SSRF 不适用 |

**版本决策边界：**若确认升级，直接评估 **16.3.8**，不先升级到 16.3.3；新候选须重新验证。当前既有通过记录不替代新版本验收。版本变更仍等待用户单独确认。
