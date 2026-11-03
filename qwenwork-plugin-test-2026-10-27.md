# 千问办公专家套件兼容验证

已实现原生 plugin.json 导入、SKILL.md 元数据生成命令、包内关联知识加载，
并在本地服务安装启用了用户提供的 `mysql-ops-expert.zip`。

## 实包验证

- 套件目录：`assets/suites/mysql-ops-expert/`，没有生成 suite.yaml。
- ZIP 中 29 个文件与安装后文件逐字节一致。
- 8 个技能，7 个可调用命令；mysql-ops-knowledge 为内部知识技能。
- 全部 7 个命令的主技能和 Markdown 关联参考均成功加载。
- 实际上传接口返回 200，启用状态为 enabled。

## 真实会话

会话 ID：`a9d56459-3caa-4553-8deb-6945b5375c5d`。
在未选择数据库的页面中选择 `/SQL 体检`，提供明确标注为测试样例的 SQL
与 EXPLAIN，要求不执行采集或写操作。

后端与历史消息记录主技能及 6 个参考文件，每个正文 SHA-256 均与包内文件一致。
回复指出 DATE(created_at) 函数包裹索引列的问题，给出范围过滤改写、
安全分级和待验证收益；本轮没有执行业务工具。
重新打开真实会话，命令引用和全部 7 份加载记录恢复成功。
该测试验证加载和粘贴输入诊断，不验证线上数据库性能收益。

证据：

- `output/qwenwork-plugin-verification.json`
- `output/playwright/qwenwork-plugin-history.png`

## 自动检查

- 后端插件、绑定和历史回归：53 passed，18 subtests passed。
- 页面原有套件回归：7 passed；新增原生插件用例修复后单独复测：1 passed。
- 前端套件路由测试：11 passed。
- 修改的 Python 加载、绑定、上传及测试文件通过 Ruff。
- git diff --check 通过。
- TypeScript 全量检查仍有 175 个错误，与已知工作区基线数量一致；
  不能视为全量类型检查通过。

原生插件兼容范围和运行时差异见 `docs/design/qwenwork-plugin-compatibility.md`。
专有连接器、@技能自动转交和完整 SOP 执行保证不在本次实现范围。
