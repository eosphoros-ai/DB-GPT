---
sidebar_position: 3
title: Model Providers UI
summary: "Connect LLM providers and manage models from the settings page, no code required"
read_when:
  - You want to connect a provider (OpenAI, Copilot, DeepSeek…) without editing config files
  - You need to enable/disable specific models or add an OpenAI-compatible custom provider
---
# Model Providers UI

import useBaseUrl from '@docusaurus/useBaseUrl';

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/01-providers-overview.png')} width="900px" />
</div>

<br />

The **Model Providers** page is a settings page where you connect LLM providers and manage their models entirely from the UI — no `.toml` editing and no code required.

Key properties:

- **Connect once, enable models individually.** Credentials are stored per provider; each model under a provider can be enabled or disabled independently.
- **Takes effect immediately.** Enabling a model starts its worker in the running server; the model is selectable in chat right away — no restart.
- **Survives restarts.** Connected providers and enabled models are persisted and restored automatically when the server boots.

## Opening the page

Use the top navigation: **Model Providers**. The page has three worker-type tabs — `llm`, `text2vec`, `reranker`. The provider list on the left shows every built-in provider with its model count; providers with a green **Connected** tag already have stored credentials.

## Built-in providers (pre-integrated)

27 providers ship pre-integrated — each comes with a ready-made model catalog (label, context length, function-calling support), so you only need to provide credentials:

| Group | Providers |
| --- | --- |
| Global model providers | OpenAI, GitHub Copilot, Anthropic (Claude), Google Gemini, xAI (Grok), Mistral AI, NVIDIA NIM |
| Chinese model providers | DeepSeek, Zhipu AI (GLM), Kimi (Moonshot), Tongyi Qwen, Volcengine (Doubao), MiniMax, Baichuan, Yi (01.AI), iFlytek Spark, Baidu Qianfan (ERNIE) |
| Gateways & aggregators | OrcaRouter (orcarouter.ai), Vercel AI Gateway, SiliconFlow, LiteLLM, Groq, AIML API, BurnCloud, Gitee AI, Infini AI |
| Local | Ollama (local models, no API key needed) |

Notes on a few of them:

- **Ollama** — connects without any API key (probed against your local server at `http://localhost:11434`).
- **Baidu Qianfan** — API Key uses the `AccessKey:SecretKey` format.
- **iFlytek Spark / LiteLLM** — credentials cannot be verified at connect time (no model-list endpoint); the connection is accepted as-is and model startup is the source of truth.
- **GitHub Copilot** — see [GitHub Copilot (OAuth sign-in)](#github-copilot-oauth-sign-in) below; Personal Access Tokens are not supported.

## Connecting a provider

Select a provider and click **Connect**:

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/03-connect-api-key.png')} width="700px" />
</div>

<br />

- **API Key** (required for most providers) — the provider's API key.
- **API Base** (optional) — override the default endpoint. Leave empty to use the provider's official address.

On connect the credentials are **verified against the real provider** (e.g. a model-list probe) before anything is saved, and the provider's 5 most recently updated models are enabled automatically. A failed verification saves nothing.

## Enabling and disabling models

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/02-provider-models.png')} width="900px" />
</div>

<br />

Each model row shows its label, function-calling support and context length, with a switch to enable or disable it:

- **Enable** starts the model's worker — the model becomes usable in chat immediately.
- **Disable** stops the worker and frees the concurrency slot.

Use the **Search models** box to filter long catalogs; large catalogs show the first 50 rows with a **show all** button. Once a provider is connected you can **Reconnect** (to change credentials) or **Disconnect** (which stops its models and clears the stored key).

## GitHub Copilot (OAuth sign-in)

GitHub Copilot requires a Copilot subscription and uses the same GitHub device-flow sign-in as OpenCode: open the connect dialog, visit [github.com/login/device](https://github.com/login/device), enter the confirmation code, and the connection completes automatically once you authorize. Personal Access Tokens are **not** accepted by GitHub for Copilot.

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/04-copilot-catalog.png')} width="900px" />
</div>

<br />

One-time server setup: register a GitHub OAuth App at [github.com/settings/developers](https://github.com/settings/developers) (enable **Device Flow**), then start the server with:

```bash
export GITHUB_COPILOT_OAUTH_CLIENT_ID=Iv1_your_client_id
```

## Adding a custom provider

If your service is not in the built-in list, any **OpenAI-compatible** endpoint (vLLM, LiteLLM gateway, one-api, FastChat, Xinference, company gateways…) can be added without code via **Add Custom Provider**:

<div align="center">
  <img src={useBaseUrl('/images/model-providers-ui/05-custom-provider.png')} width="700px" />
</div>

<br />

| Field | Description |
| --- | --- |
| Name | Display name of the provider (shown in the left list) |
| API Base | Base URL, e.g. `http://localhost:8000/v1` |
| API Key | Bearer token (fill any placeholder like `sk-xxx` for unauthenticated local servers) |
| Model list | The available model ids, comma or newline separated |

How it works:

1. On submit, the backend first probes the endpoint (`GET {API Base}/models`) to verify reachability.
2. The provider is persisted as a `custom/<slug>` provider and every listed model is started immediately — usable in chat without a restart.
3. The available models are **exactly what you list** — there is no auto-discovery. To add or remove models later, disconnect and re-create the provider, or enable/disable the existing ones from its detail page.
4. Custom providers survive server restarts like built-in ones.

:::tip
Try it in the UI first to validate connectivity and model quality; if you later want a first-class provider (branded icon, curated model catalog with metadata, default-enabled models), add a real adapter — see `packages/dbgpt-core/src/dbgpt/model/proxy/llms/` for templates.
:::
