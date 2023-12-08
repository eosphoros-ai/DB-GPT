#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import List
import logging
import importlib.metadata as metadata
from dbgpt.model.proxy.llms.proxy_model import ProxyModel
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
import httpx

logger = logging.getLogger(__name__)


def _initialize_openai(params: ProxyModelParameters):
    try:
        import openai
    except ImportError as exc:
        raise ValueError(
            "Could not import python package: openai "
            "Please install openai by command `pip install openai` "
        ) from exc

    api_type = params.proxy_api_type or os.getenv("OPENAI_API_TYPE", "open_ai")

    api_base = params.proxy_api_base or os.getenv(
        "OPENAI_API_TYPE",
        os.getenv("AZURE_OPENAI_ENDPOINT") if api_type == "azure" else None,
    )
    api_key = params.proxy_api_key or os.getenv(
        "OPENAI_API_KEY",
        os.getenv("AZURE_OPENAI_KEY") if api_type == "azure" else None,
    )
    api_version = params.proxy_api_version or os.getenv("OPENAI_API_VERSION")

    if not api_base and params.proxy_server_url:
        # Adapt previous proxy_server_url configuration
        api_base = params.proxy_server_url.split("/chat/completions")[0]
    if api_type:
        openai.api_type = api_type
    if api_base:
        openai.api_base = api_base
    if api_key:
        openai.api_key = api_key
    if api_version:
        openai.api_version = api_version
    if params.http_proxy:
        openai.proxy = params.http_proxy

    openai_params = {
        "api_type": api_type,
        "api_base": api_base,
        "api_version": api_version,
        "proxy": params.http_proxy,
    }

    return openai_params


def _initialize_openai_v1(params: ProxyModelParameters):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ValueError(
            "Could not import python package: openai "
            "Please install openai by command `pip install openai"
        )

    api_type = params.proxy_api_type or os.getenv("OPENAI_API_TYPE", "open_ai")

    base_url = params.proxy_api_base or os.getenv(
        "OPENAI_API_TYPE",
        os.getenv("AZURE_OPENAI_ENDPOINT") if api_type == "azure" else None,
    )
    api_key = params.proxy_api_key or os.getenv(
        "OPENAI_API_KEY",
        os.getenv("AZURE_OPENAI_KEY") if api_type == "azure" else None,
    )
    api_version = params.proxy_api_version or os.getenv("OPENAI_API_VERSION")

    if not base_url and params.proxy_server_url:
        # Adapt previous proxy_server_url configuration
        base_url = params.proxy_server_url.split("/chat/completions")[0]

    proxies = params.http_proxy
    openai_params = {
        "api_key": api_key,
        "base_url": base_url,
    }
    return openai_params, api_type, api_version, proxies


def _build_request(model: ProxyModel, params):
    history = []

    model_params = model.get_params()
    logger.info(f"Model: {model}, model_params: {model_params}")

    messages: List[ModelMessage] = params["messages"]
    # Add history conversation
    for message in messages:
        if message.role == ModelMessageRoleType.HUMAN:
            history.append({"role": "user", "content": message.content})
        elif message.role == ModelMessageRoleType.SYSTEM:
            history.append({"role": "system", "content": message.content})
        elif message.role == ModelMessageRoleType.AI:
            history.append({"role": "assistant", "content": message.content})
        else:
            pass

    # Move the last user's information to the end
    temp_his = history[::-1]
    last_user_input = None
    for m in temp_his:
        if m["role"] == "user":
            last_user_input = m
            break
    if last_user_input:
        history.remove(last_user_input)
        history.append(last_user_input)

    payloads = {
        "temperature": params.get("temperature"),
        "max_tokens": params.get("max_new_tokens"),
        "stream": True,
    }
    proxyllm_backend = model_params.proxyllm_backend

    if metadata.version("openai") >= "1.0.0":
        openai_params, api_type, api_version, proxies = _initialize_openai_v1(
            model_params
        )
        proxyllm_backend = proxyllm_backend or "gpt-3.5-turbo"
        payloads["model"] = proxyllm_backend
    else:
        openai_params = _initialize_openai(model_params)
        if openai_params["api_type"] == "azure":
            # engine = "deployment_name".
            proxyllm_backend = proxyllm_backend or "gpt-35-turbo"
            payloads["engine"] = proxyllm_backend
        else:
            proxyllm_backend = proxyllm_backend or "gpt-3.5-turbo"
            payloads["model"] = proxyllm_backend

    logger.info(f"Send request to real model {proxyllm_backend}")
    return history, payloads


def chatgpt_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    if metadata.version("openai") >= "1.0.0":
        model_params = model.get_params()
        openai_params, api_type, api_version, proxies = _initialize_openai_v1(
            model_params
        )
        history, payloads = _build_request(model, params)
        if api_type == "azure":
            from openai import AzureOpenAI

            client = AzureOpenAI(
                api_key=openai_params["api_key"],
                api_version=api_version,
                azure_endpoint=openai_params["base_url"],
                http_client=httpx.Client(proxies=proxies),
            )
        else:
            from openai import OpenAI

            client = OpenAI(**openai_params, http_client=httpx.Client(proxies=proxies))
        res = client.chat.completions.create(messages=history, **payloads)
        text = ""
        for r in res:
            # logger.info(str(r))
            # Azure Openai reponse may have empty choices body in the first chunk
            # to avoid index out of range error
            if len(r.choices) == 0:
                continue
            if r.choices[0].delta.content is not None:
                content = r.choices[0].delta.content
                text += content
                yield text

    else:
        import openai

        history, payloads = _build_request(model, params)

        res = openai.ChatCompletion.create(messages=history, **payloads)

        text = ""
        for r in res:
            if len(r.choices) == 0:
                continue
            if r["choices"][0]["delta"].get("content") is not None:
                content = r["choices"][0]["delta"]["content"]
                text += content
                yield text


async def async_chatgpt_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    if metadata.version("openai") >= "1.0.0":
        model_params = model.get_params()
        openai_params, api_type, api_version, proxies = _initialize_openai_v1(
            model_params
        )
        history, payloads = _build_request(model, params)
        if api_type == "azure":
            from openai import AsyncAzureOpenAI

            client = AsyncAzureOpenAI(
                api_key=openai_params["api_key"],
                api_version=api_version,
                azure_endpoint=openai_params["base_url"],
                http_client=httpx.AsyncClient(proxies=proxies),
            )
        else:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                **openai_params, http_client=httpx.AsyncClient(proxies=proxies)
            )

        res = await client.chat.completions.create(messages=history, **payloads)
        text = ""
        for r in res:
            if not r.get("choices"):
                continue
            if r.choices[0].delta.content is not None:
                content = r.choices[0].delta.content
                text += content
                yield text
    else:
        import openai

        history, payloads = _build_request(model, params)

        res = await openai.ChatCompletion.acreate(messages=history, **payloads)

        text = ""
        async for r in res:
            if not r.get("choices"):
                continue
            if r["choices"][0]["delta"].get("content") is not None:
                content = r["choices"][0]["delta"]["content"]
                text += content
                yield text
