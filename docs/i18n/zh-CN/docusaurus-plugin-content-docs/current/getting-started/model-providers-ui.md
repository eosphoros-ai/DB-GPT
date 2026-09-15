---
sidebar_position: 3
title: 模型提供商配置
---
# 模型提供商配置

import useBaseUrl from '@docusaurus/useBaseUrl';

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/01-providers-overview.png')} width="900px" />
</div>

<br />

**模型提供商配置**页面让你在界面上完成大模型提供商的接入和模型管理——无需修改 `.toml` 配置文件，无需写代码。

核心特性：

- **一次连接，按模型启停。** 凭证按提供商存储，其下每个模型可独立启用/停用。
- **即时生效。** 启用模型即在运行中的服务里启动对应 worker，聊天界面立即可选——无需重启。
- **重启自动恢复。** 已连接的提供商和启用的模型会持久化，服务重启后自动恢复。

## 打开页面

顶部导航 → **模型提供商配置**。页面顶部有三个 worker 类型切换：`llm`、`text2vec`、`reranker`。左侧提供商列表展示全部内置提供商及各自的模型数量；带绿色 **已连接** 标签的表示已保存凭证。

## 内置提供商（已预集成）

内置 27 家提供商，每家都预置了模型目录（含名称、上下文长度、函数调用支持等元数据），只需填凭证即可使用：

| 分组 | 提供商 |
| --- | --- |
| 国际模型厂商 | OpenAI、GitHub Copilot、Anthropic (Claude)、Google Gemini、xAI (Grok)、Mistral AI、NVIDIA NIM |
| 国内模型厂商 | DeepSeek、智谱 AI (GLM)、Kimi (Moonshot)、通义千问、火山引擎 (豆包)、MiniMax、百川、零一万物 (Yi)、讯飞星火、百度千帆 (文心) |
| 网关与聚合 | OrcaRouter (orcarouter.ai)、Vercel AI Gateway、SiliconFlow、LiteLLM、Groq、AIML API、BurnCloud、Gitee AI、无问芯穹 |
| 本地 | Ollama（本地模型，无需 API Key） |

部分提供商说明：

- **Ollama** —— 免 API Key 连接（探测本地服务 `http://localhost:11434`）。
- **百度千帆** —— Key 使用 `AccessKey:SecretKey` 格式。
- **讯飞星火 / LiteLLM** —— 连接时无法校验凭证（无模型列表端点），以模型启动结果为准。
- **GitHub Copilot** —— 见下文 [GitHub Copilot（GitHub 授权登录）](#github-copilotgithub-授权登录)；GitHub 已禁用 Personal Access Token。

## 连接提供商

选中一个提供商，点击 **连接**：

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/03-connect-api-key.png')} width="700px" />
</div>

<br />

- **API Key**（多数提供商必填）—— 提供商的 API 密钥。
- **API Base**（可选）—— 覆盖默认接入点，留空使用官方地址。

连接时会**先对提供商做真实凭证校验**（如探测模型列表端点），校验通过才保存，并自动启用该提供商最近更新的 5 个模型。校验失败则不落任何数据。

## 启用与停用模型

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/02-provider-models.png')} width="900px" />
</div>

<br />

每个模型行展示名称、函数调用支持、上下文长度，右侧开关控制启停：

- **开启**：启动该模型的 worker，聊天中立即可用。
- **关闭**：停止 worker 并释放并发槽位。

模型较多时可用 **搜索模型** 框过滤；大目录默认展示前 50 条，可点击 **显示全部** 展开。已连接的提供商支持 **重新连接**（更换凭证）和 **断开连接**（停用其全部模型并清除存储的密钥）。

## GitHub Copilot（GitHub 授权登录）

GitHub Copilot 需要账号有 Copilot 订阅，授权流程与 OpenCode 相同的 GitHub 设备流：打开连接弹窗，访问 [github.com/login/device](https://github.com/login/device) 输入确认码，授权后自动完成连接。**Personal Access Token 已被 GitHub 禁用，无法用于 Copilot。**

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/04-copilot-catalog.png')} width="900px" />
</div>

<br />

服务端一次性配置：在 [github.com/settings/developers](https://github.com/settings/developers) 注册 GitHub OAuth App（勾选 **Enable Device Flow**），然后携带环境变量启动服务：

```bash
export GITHUB_COPILOT_OAUTH_CLIENT_ID=Iv1_你的ClientID
```

## 添加自定义提供商

如果服务不在内置列表里，任何 **OpenAI 兼容** 端点（vLLM、LiteLLM 网关、one-api、FastChat、Xinference、公司内部网关…）都可通过 **添加自定义提供商** 免代码接入：

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/05-custom-provider.png')} width="700px" />
</div>

<br />

| 字段 | 说明 |
| --- | --- |
| 名称 | 提供商显示名（展示在左侧列表） |
| API Base | 接入点地址，如 `http://localhost:8000/v1` |
| API Key | Bearer Token（本地无鉴权服务可随意填 `sk-xxx`） |
| 模型列表 | 可用模型 id，逗号或换行分隔 |

工作机制：

1. 提交后后端先探测接入点（`GET {API Base}/models`）验证连通性。
2. 提供商以 `custom/<slug>` 持久化，列出的模型立即启动——聊天中立即可用。
3. 可用模型即你填写的列表，**不会自动发现**。后续增删模型可断开后重建，或在详情页启停现有模型。
4. 自定义提供商与内置提供商一样支持重启后自动恢复。

:::tip
建议先在界面用自定义提供商验证连通性和模型效果；如果后续需要一等内置体验（品牌图标、带元数据的精选模型目录、默认启用模型），可以编写真正的适配器——参考 `packages/dbgpt-core/src/dbgpt/model/proxy/llms/` 下的现有模板。
:::
