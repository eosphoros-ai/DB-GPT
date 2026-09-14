#!/usr/bin/env python3
"""Sync the models.dev catalog snapshot into models_dev_catalog.json.

Fetches https://models.dev/api.json, maps the providers we support onto the
``proxy/*`` ids used by DB-GPT, and merges them into the committed snapshot
``packages/dbgpt-core/src/dbgpt/model/proxy/models_dev_catalog.json``.

Usage:
    uv run python scripts/models_dev_sync.py            # fetch + merge
    uv run python scripts/models_dev_sync.py --offline  # merge hand-curated only

Providers without upstream models.dev coverage are filled from HAND_CURATED
(kept in sync with the hardcoded registries in
``dbgpt/model/proxy/llms/*.py``). Existing entries absent upstream are
preserved, so hand-curated data survives re-runs.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

MODELS_DEV_URL = "https://models.dev/api.json"

CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "packages/dbgpt-core/src/dbgpt/model/proxy/models_dev_catalog.json"
)

# Cap per provider: gateway catalogs (openrouter/vercel) have hundreds of
# entries and the snapshot ships in the wheel.
MAX_MODELS_PER_PROVIDER = 120

DESCRIPTION_MAX_CHARS = 200

# models.dev provider id -> DB-GPT provider id. Ids drift upstream, so the
# script prints unmatched top-level keys instead of silently dropping them.
PROVIDER_MAP = {
    "openai": "proxy/openai",
    "anthropic": "proxy/claude",
    "google": "proxy/gemini",
    "deepseek": "proxy/deepseek",
    "zhipu": "proxy/zhipu",
    "zhipuai": "proxy/zhipu",
    "moonshotai": "proxy/moonshot",
    "moonshot": "proxy/moonshot",
    "bailian": "proxy/tongyi",
    "volcengine": "proxy/volcengine",
    "minimax": "proxy/minimax",
    "minimax-io": "proxy/minimax",
    "baichuan": "proxy/baichuan",
    "openrouter": "proxy/orcarouter",
    "siliconflow": "proxy/siliconflow",
    "nvidia": "proxy/nvidia",
    "groq": "proxy/groq",
    "mistral": "proxy/mistral",
    "xai": "proxy/xai",
    "vercel": "proxy/vercel",
}


def _entry(
    model: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    context_length: Optional[int] = None,
    max_output_length: Optional[int] = None,
    function_calling: Optional[bool] = None,
    last_updated: str = "",
) -> Dict[str, Any]:
    return {
        "model": model,
        "name": name or model,
        "description": description,
        "context_length": context_length,
        "max_output_length": max_output_length,
        "function_calling": function_calling,
        "status": None,
        "last_updated": last_updated,
    }


# Hand-curated catalogs for providers with no models.dev coverage. Entries
# mirror the hardcoded registries in dbgpt/model/proxy/llms/*.py so a model
# listed here is guaranteed startable by its adapter.
HAND_CURATED: Dict[str, List[Dict[str, Any]]] = {
    "proxy/minimax": [
        _entry(
            "MiniMax-M3",
            "MiniMax M3",
            "MiniMax flagship model with enhanced reasoning, coding and tool use.",
            204800,
            192000,
            True,
        ),
        _entry(
            "MiniMax-M2.7",
            "MiniMax M2.7",
            "MiniMax flagship model with enhanced reasoning and coding.",
            204800,
            192000,
            True,
        ),
        _entry(
            "MiniMax-M2.7-highspeed",
            "MiniMax M2.7 Highspeed",
            "High-speed version of MiniMax M2.7 for low-latency scenarios.",
            204800,
            192000,
            True,
        ),
    ],
    "proxy/yi": [
        _entry(
            "yi-lightning",
            "Yi Lightning",
            "Yi Lightning by Lingyiwanwu, fast and cost-effective.",
            16384,
            4096,
            True,
        ),
    ],
    "proxy/baichuan": [
        _entry(
            "Baichuan4-Turbo",
            "Baichuan4 Turbo",
            "Baichuan4 Turbo by Baichuan.",
            32768,
            None,
            True,
        ),
        _entry(
            "Baichuan4-Air",
            "Baichuan4 Air",
            "Baichuan4 Air by Baichuan.",
            32768,
            None,
            True,
        ),
        _entry("Baichuan4", "Baichuan4", "Baichuan4 by Baichuan.", 32768, None, True),
        _entry(
            "Baichuan3-Turbo",
            "Baichuan3 Turbo",
            "Baichuan3 Turbo by Baichuan.",
            32768,
            None,
            True,
        ),
        _entry(
            "Baichuan3-Turbo-128k",
            "Baichuan3 Turbo 128K",
            "Baichuan3 Turbo with 128K context by Baichuan.",
            131072,
            None,
            True,
        ),
    ],
    "proxy/spark": [
        _entry("lite", "Spark Lite", "Xunfei Spark Lite model.", 14096, 14096, False),
        _entry(
            "generalv3",
            "Spark V3.0",
            "Xunfei Spark General V3 model.",
            18192,
            18192,
            True,
        ),
        _entry(
            "generalv3.5",
            "Spark V3.5",
            "Xunfei Spark General V3.5 model.",
            18192,
            18192,
            True,
        ),
        _entry(
            "4.0Ultra",
            "Spark 4.0 Ultra",
            "Xunfei Spark 4.0 Ultra flagship model.",
            18192,
            18192,
            True,
        ),
        _entry(
            "pro-128k",
            "Spark Pro 128K",
            "Xunfei Spark Pro with 128K context.",
            131072,
            14096,
            True,
        ),
        _entry(
            "max-32k",
            "Spark Max 32K",
            "Xunfei Spark Max with 32K context.",
            32768,
            18192,
            True,
        ),
    ],
    "proxy/wenxin": [
        _entry(
            "ERNIE-Bot-4.0",
            "ERNIE 4.0",
            "Baidu ERNIE Bot 4.0 flagship model.",
            8192,
            2048,
            True,
        ),
        _entry(
            "ERNIE-Bot-8K",
            "ERNIE 8K",
            "Baidu ERNIE Bot with 8K context.",
            8192,
            2048,
            True,
        ),
        _entry(
            "ERNIE-Bot", "ERNIE Bot", "Baidu ERNIE Bot base model.", 8192, 2048, False
        ),
        _entry(
            "ERNIE-Bot-turbo",
            "ERNIE Bot Turbo",
            "Baidu ERNIE Bot Turbo, high-speed version.",
            8192,
            2048,
            False,
        ),
    ],
    "proxy/github_copilot": [
        _entry(m, n, d, c, mo, True)
        for m, n, d, c, mo in [
            ("gpt-4o", "GPT-4o (Copilot)", "GPT-4o via GitHub Copilot.", 128000, 16384),
            (
                "gpt-4.1",
                "GPT-4.1 (Copilot)",
                "GPT-4.1 via GitHub Copilot.",
                128000,
                32768,
            ),
            (
                "o3",
                "o3 (Copilot)",
                "OpenAI o3 reasoning model via GitHub Copilot.",
                200000,
                100000,
            ),
            (
                "claude-sonnet-4",
                "Claude Sonnet 4 (Copilot)",
                "Claude Sonnet 4 via GitHub Copilot.",
                200000,
                64000,
            ),
            (
                "claude-3.7-sonnet",
                "Claude 3.7 Sonnet (Copilot)",
                "Claude 3.7 Sonnet via GitHub Copilot.",
                200000,
                64000,
            ),
            (
                "gemini-2.5-pro",
                "Gemini 2.5 Pro (Copilot)",
                "Gemini 2.5 Pro via GitHub Copilot.",
                1000000,
                64000,
            ),
        ]
    ],
    "proxy/ollama": [
        _entry(
            m,
            n,
            d,
            c,
            None,
            fc,
        )
        for m, n, d, c, fc in [
            (
                "llama3.3",
                "Llama 3.3",
                "Meta Llama 3.3 70B, general-purpose instruction model.",
                131072,
                True,
            ),
            (
                "qwen3",
                "Qwen3",
                "Alibaba Qwen3, hybrid reasoning model.",
                40960,
                True,
            ),
            (
                "deepseek-r1",
                "DeepSeek R1",
                "DeepSeek R1 reasoning model.",
                163840,
                False,
            ),
            (
                "gemma3",
                "Gemma 3",
                "Google Gemma 3, multimodal-capable open model.",
                131072,
                True,
            ),
            (
                "phi4",
                "Phi-4",
                "Microsoft Phi-4, 14B sliding-window attention model.",
                16384,
                False,
            ),
            (
                "mistral",
                "Mistral",
                "Mistral 7B instruction model.",
                32768,
                True,
            ),
            (
                "llama3.2",
                "Llama 3.2",
                "Meta Llama 3.2, lightweight edge model.",
                131072,
                True,
            ),
            (
                "qwen2.5",
                "Qwen2.5",
                "Alibaba Qwen2.5 instruction model.",
                32768,
                True,
            ),
            (
                "deepseek-v3",
                "DeepSeek V3",
                "DeepSeek V3 671B MoE model.",
                163840,
                False,
            ),
            (
                "gpt-oss",
                "GPT-OSS",
                "OpenAI open-weight GPT-OSS model.",
                131072,
                True,
            ),
            (
                "llava",
                "LLaVA",
                "LLaVA multimodal vision-language model.",
                32768,
                False,
            ),
            (
                "nomic-embed-text",
                "Nomic Embed Text",
                "Nomic text embedding model (embedding only).",
                8192,
                False,
            ),
        ]
    ],
    "proxy/litellm": [
        _entry(
            m,
            n,
            d,
            c,
            mo,
            True,
        )
        for m, n, d, c, mo in [
            (
                "openai/gpt-4o",
                "GPT-4o (LiteLLM)",
                "GPT-4o routed through LiteLLM.",
                128000,
                16384,
            ),
            (
                "openai/gpt-4o-mini",
                "GPT-4o Mini (LiteLLM)",
                "GPT-4o Mini routed through LiteLLM.",
                128000,
                16384,
            ),
            (
                "anthropic/claude-sonnet-4",
                "Claude Sonnet 4 (LiteLLM)",
                "Claude Sonnet 4 routed through LiteLLM.",
                200000,
                8192,
            ),
            (
                "gemini/gemini-2.5-pro",
                "Gemini 2.5 Pro (LiteLLM)",
                "Gemini 2.5 Pro routed through LiteLLM.",
                1048576,
                8192,
            ),
            (
                "deepseek/deepseek-chat",
                "DeepSeek Chat (LiteLLM)",
                "DeepSeek Chat routed through LiteLLM.",
                128000,
                16384,
            ),
            (
                "mistral/mistral-large-latest",
                "Mistral Large (LiteLLM)",
                "Mistral Large routed through LiteLLM.",
                131072,
                8192,
            ),
        ]
    ],
    "proxy/gitee": [
        _entry(
            "DeepSeek-V3",
            "DeepSeek V3 (Gitee AI)",
            "DeepSeek V3 hosted on Gitee AI.",
            65536,
            8192,
            True,
        ),
        _entry(
            "DeepSeek-R1",
            "DeepSeek R1 (Gitee AI)",
            "DeepSeek R1 hosted on Gitee AI.",
            65536,
            8192,
            False,
        ),
    ],
    "proxy/infiniai": [
        _entry(
            "deepseek-v3",
            "DeepSeek V3 (InfiniAI)",
            "DeepSeek V3 on Infini AI.",
            65536,
            8192,
            True,
        ),
        _entry(
            "deepseek-r1",
            "DeepSeek R1 (InfiniAI)",
            "DeepSeek R1 on Infini AI.",
            65536,
            8192,
            False,
        ),
        _entry(
            "qwq-32b",
            "QwQ 32B (InfiniAI)",
            "QwQ 32B reasoning model on Infini AI.",
            65536,
            8192,
            False,
        ),
    ],
    "proxy/aimlapi": [
        _entry(
            "openai/gpt-4o",
            "GPT-4o (AIML API)",
            "GPT-4o via AIML API gateway.",
            128000,
            16384,
            True,
        ),
        _entry(
            "gpt-4o-mini",
            "GPT-4o Mini (AIML API)",
            "GPT-4o Mini via AIML API gateway.",
            128000,
            16384,
            True,
        ),
        _entry(
            "claude-3-5-sonnet-20240620",
            "Claude 3.5 Sonnet (AIML API)",
            "Claude 3.5 Sonnet via AIML API gateway.",
            8192,
            2048,
            True,
        ),
        _entry(
            "deepseek-chat",
            "DeepSeek Chat (AIML API)",
            "DeepSeek Chat via AIML API gateway.",
            128000,
            16000,
            True,
        ),
        _entry(
            "google/gemini-2-0-flash",
            "Gemini 2.0 Flash (AIML API)",
            "Gemini 2.0 Flash via AIML API gateway.",
            1000000,
            32768,
            True,
        ),
        _entry(
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "Mixtral 8x7B (AIML API)",
            "Mixtral 8x7B Instruct via AIML API gateway.",
            64000,
            8000,
            True,
        ),
    ],
    "proxy/burncloud": [
        _entry(
            "claude-opus-4-1-20250805",
            "Claude Opus 4.1 (BurnCloud)",
            "Claude Opus 4.1 via BurnCloud gateway.",
            200000,
            8192,
            True,
        ),
        _entry(
            "claude-sonnet-4-20250514",
            "Claude Sonnet 4 (BurnCloud)",
            "Claude Sonnet 4 via BurnCloud gateway.",
            200000,
            8192,
            True,
        ),
        _entry(
            "gpt-5",
            "GPT-5 (BurnCloud)",
            "GPT-5 via BurnCloud gateway.",
            200000,
            16384,
            True,
        ),
        _entry(
            "gpt-4.1",
            "GPT-4.1 (BurnCloud)",
            "GPT-4.1 via BurnCloud gateway.",
            128000,
            16384,
            True,
        ),
        _entry(
            "gpt-4o",
            "GPT-4o (BurnCloud)",
            "GPT-4o via BurnCloud gateway.",
            128000,
            16384,
            True,
        ),
    ],
    "proxy/nvidia": [
        _entry(
            "meta/llama-3.3-70b-instruct",
            "Llama 3.3 70B (NVIDIA NIM)",
            "Meta Llama 3.3 70B Instruct on NVIDIA NIM.",
            131072,
            4096,
            True,
        ),
        _entry(
            "meta/llama-3.1-70b-instruct",
            "Llama 3.1 70B (NVIDIA NIM)",
            "Meta Llama 3.1 70B Instruct on NVIDIA NIM.",
            131072,
            4096,
            True,
        ),
        _entry(
            "deepseek-ai/deepseek-r1",
            "DeepSeek R1 (NVIDIA NIM)",
            "DeepSeek R1 on NVIDIA NIM.",
            65536,
            8192,
            False,
        ),
        _entry(
            "qwen/qwen2.5-72b-instruct",
            "Qwen2.5 72B (NVIDIA NIM)",
            "Qwen2.5 72B Instruct on NVIDIA NIM.",
            32768,
            8192,
            True,
        ),
        _entry(
            "mistralai/mixtral-8x7b-instruct-v0.1",
            "Mixtral 8x7B (NVIDIA NIM)",
            "Mixtral 8x7B Instruct on NVIDIA NIM.",
            32768,
            4096,
            True,
        ),
    ],
    "proxy/vercel": [
        _entry(
            "openai/gpt-5.2",
            "GPT-5.2 (Vercel)",
            "GPT-5.2 via Vercel AI Gateway.",
            400000,
            128000,
            True,
        ),
        _entry(
            "openai/gpt-4o-mini",
            "GPT-4o Mini (Vercel)",
            "GPT-4o Mini via Vercel AI Gateway.",
            128000,
            16384,
            True,
        ),
        _entry(
            "anthropic/claude-sonnet-4.5",
            "Claude Sonnet 4.5 (Vercel)",
            "Claude Sonnet 4.5 via Vercel AI Gateway.",
            200000,
            64000,
            True,
        ),
        _entry(
            "google/gemini-2.5-pro",
            "Gemini 2.5 Pro (Vercel)",
            "Gemini 2.5 Pro via Vercel AI Gateway.",
            1000000,
            64000,
            True,
        ),
    ],
    "proxy/xai": [
        _entry("grok-4", "Grok 4", "Grok 4 by xAI.", 262144, 32768, True),
        _entry(
            "grok-4-fast", "Grok 4 Fast", "Grok 4 Fast by xAI.", 262144, 32768, True
        ),
        _entry("grok-3", "Grok 3", "Grok 3 by xAI.", 131072, 32768, True),
        _entry(
            "grok-3-mini", "Grok 3 Mini", "Grok 3 Mini by xAI.", 131072, 32768, True
        ),
    ],
    "proxy/groq": [
        _entry(
            "llama-3.3-70b-versatile",
            "Llama 3.3 70B Versatile (Groq)",
            "Meta Llama 3.3 70B on Groq LPU inference.",
            131072,
            32768,
            True,
        ),
        _entry(
            "llama-3.1-8b-instant",
            "Llama 3.1 8B Instant (Groq)",
            "Meta Llama 3.1 8B on Groq LPU inference.",
            131072,
            32768,
            True,
        ),
        _entry(
            "openai/gpt-oss-120b",
            "GPT-OSS 120B (Groq)",
            "OpenAI GPT-OSS 120B on Groq LPU inference.",
            131072,
            32768,
            True,
        ),
        _entry(
            "qwen/qwen3-32b",
            "Qwen3 32B (Groq)",
            "Qwen3 32B on Groq LPU inference.",
            131072,
            40960,
            True,
        ),
    ],
    "proxy/mistral": [
        _entry(
            "mistral-large-latest",
            "Mistral Large",
            "Mistral Large, flagship model by Mistral AI.",
            131072,
            32768,
            True,
        ),
        _entry(
            "mistral-medium-latest",
            "Mistral Medium",
            "Mistral Medium by Mistral AI.",
            131072,
            32768,
            True,
        ),
        _entry(
            "mistral-small-latest",
            "Mistral Small",
            "Mistral Small by Mistral AI.",
            131072,
            32768,
            True,
        ),
        _entry(
            "codestral-latest",
            "Codestral",
            "Codestral, coding-focused model by Mistral AI.",
            262144,
            32768,
            True,
        ),
    ],
}


def _first_paragraph(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    para = text.strip().split("\n", 1)[0].strip()
    if len(para) > DESCRIPTION_MAX_CHARS:
        para = para[: DESCRIPTION_MAX_CHARS - 3].rstrip() + "..."
    return para or None


def _map_upstream_entry(model_id: str, md: Dict[str, Any]) -> Dict[str, Any]:
    limit = md.get("limit") or {}
    return {
        "model": model_id,
        "name": md.get("name") or model_id,
        "description": _first_paragraph(md.get("description")),
        "context_length": limit.get("context"),
        "max_output_length": limit.get("output"),
        "function_calling": bool(md.get("tool_call")),
        "status": md.get("status"),
        "last_updated": md.get("release_date") or "",
    }


def _sort_key(entry: Dict[str, Any]) -> str:
    # Newest first; entries without a date sink to the end (stable).
    return entry.get("last_updated") or "0000-00-00"


def fetch_upstream() -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(MODELS_DEV_URL, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"WARN: fetch {MODELS_DEV_URL} failed ({e}); running offline merge.")
        return None


def build_upstream_catalog(upstream: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    catalog: Dict[str, List[Dict[str, Any]]] = {}
    unmapped = []
    for dev_id, dev_provider in upstream.items():
        target = PROVIDER_MAP.get(dev_id)
        if not target:
            unmapped.append(dev_id)
            continue
        entries = [
            _map_upstream_entry(model_id, md)
            for model_id, md in (dev_provider.get("models") or {}).items()
        ]
        entries.sort(key=_sort_key, reverse=True)
        catalog[target] = entries[:MAX_MODELS_PER_PROVIDER]
    if unmapped:
        print(f"WARN: unmapped models.dev provider ids: {sorted(unmapped)}")
    return catalog


def merge(
    existing: Dict[str, Any],
    incoming: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = json.loads(json.dumps(existing))  # deep copy
    for provider, entries in incoming.items():
        if provider not in merged:
            merged[provider] = {"models": entries}
            continue
        old = {m["model"]: m for m in merged[provider].get("models", [])}
        seen = set()
        combined: List[Dict[str, Any]] = []
        for entry in entries:
            seen.add(entry["model"])
            combined.append(entry)
        for model_id, entry in old.items():
            if model_id not in seen:
                combined.append(entry)
        combined.sort(key=_sort_key, reverse=True)
        merged[provider]["models"] = combined[:MAX_MODELS_PER_PROVIDER]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the network fetch and only merge HAND_CURATED entries.",
    )
    args = parser.parse_args()

    existing = json.loads(CATALOG_PATH.read_text())
    upstream = None if args.offline else fetch_upstream()

    incoming: Dict[str, List[Dict[str, Any]]] = {}
    if upstream:
        incoming.update(build_upstream_catalog(upstream))
    # Hand-curated entries fill providers upstream does not cover; they are
    # merged per-model so upstream data wins when both exist.
    for provider, entries in HAND_CURATED.items():
        if upstream and provider in incoming:
            continue
        incoming[provider] = entries

    merged = merge(existing, incoming)
    CATALOG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")

    total = sum(len(v.get("models", [])) for v in merged.values())
    print(
        f"Wrote {CATALOG_PATH}: {len(merged)} providers, {total} models "
        f"(upstream={'fetched' if upstream else 'offline'})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
