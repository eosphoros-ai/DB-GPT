# ER 图渲染与导出验证

2026-10-28。官方 `metadata-architecture-expert` 已同步，新工具同时注册于 DB-GPT 与 PI。前端静态构建完成并部署，本地主服务 5670 已重启，首页与套件接口均正常。

## 验证结果

- 后端 ER/产物/套件加载/创建相关回归：65 项通过；最终 ER 和引擎产物回归：17 项通过。
- ArtifactCards：12 项通过，包括 ER 内联 iframe、普通 HTML 报告保持原有卡片。Python Ruff 与修改组件 ESLint 通过。
- 实际 Olist SQLite：目录查询采集 12 表、60 列、0 声明外键；未编造关系。目录证据在 `catalog-evidence.json`。
- 实际 Olist、复合声明外键、复合推断关系三组导出均通过 `@dbml/core` 和 Mermaid 解析器。
- Chrome 中使用与对话相同的 iframe sandbox 验证三组 SVG 渲染、放大/重置及 15 次文件下载；下载内容逐字节匹配导出文件。
- draw.io XML 检查表/列节点、复合键的逐列连线、推断虚线和字符转义。官方在线编辑器访问返回 `ERR_HTTP_RESPONSE_CODE_FAILURE`，嵌入编辑器等待超时，未完成其在线导入验证。
- 部署后首页浏览器验证通过，官方元数据套件可见；套件接口返回 `source=official` 且 allow 含 `generate_er_diagram`。

本轮未运行付费模型的完整对话。套件指令强制调用生成工具，已验证工具产物及两引擎共享注册/产物传递；模型对任意数据库的字段选择和约束判断仍需依靠采集证据与指令。

## 使用

刷新页面，选择元数据与架构专家并绑定数据源，执行 `/physical-er` 或“生成可渲染、可下载导入的 ER 图”。已有仅 Mermaid 源码的历史回答需重新生成。

`.drawio` 用于 diagrams.net 打开编辑；`.dbml` 用于 dbdiagram 导入；`.mmd` 用于 Mermaid；`.svg` 用于文档；`.json` 保留图模型及证据引用。推断关系在图中为虚线，在 DBML 中仅为注释。暂不提供 DBeaver、Navicat 原生模型文件。

实际数据库图：`olist/er-diagram.html`。图内提供全部五种格式的下载入口。文件包同步至 `../db-expert-suites-20261028/metadata-architecture-expert-1.0.0.zip`。

格式解析与浏览器验证可复跑：

```sh
npm install --prefix output/er-diagram-verification-20261028/tooling --no-save --package-lock=false @dbml/core mermaid
.venv/bin/python output/er-diagram-verification-20261028/generate_examples.py
node output/er-diagram-verification-20261028/validate_formats.cjs
node output/er-diagram-verification-20261028/deployed_smoke.cjs
```
