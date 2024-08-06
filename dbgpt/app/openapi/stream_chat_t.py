import asyncio
import json
from datetime import datetime

import aiohttp
import httpx
import requests


async def run(headers, payload):
    api_prod = "https://df-pre.alipay.com/openapi/v1/chat/completions"

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(api_prod, json=payload) as resp:
            while not resp.content.at_eof():
                line = await resp.content.readline()

                decoded_line = line.decode("utf-8")
                now = datetime.now()
                print(f"\n\n[DEBUG]{now.strftime('%Y-%m-%d %H:%M:%S')}__{decoded_line}")


async def run_https(api, headers, payload):
    timeout = httpx.Timeout(10.0, read=90.0)  # 例如，连接超时10秒，读取超时30秒
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", api, data=json.dumps(payload), headers=headers
        ) as response:
            if (
                response.status_code == httpx.codes.OK
                and response.headers["content-type"] == "text/event-stream"
            ):
                async for chunk in response.aiter_lines():
                    # Do something with the streamed data
                    now = datetime.now()
                    try:
                        decoded_line = chunk.decode("utf-8")

                        print(
                            f"\n\n[DEBUG]{now.strftime('%Y-%m-%d %H:%M:%S')}__{decoded_line}"
                        )
                    except Exception as e:
                        print(
                            f"\n\n[DEBUG2]{now.strftime('%Y-%m-%d %H:%M:%S')}__{chunk}"
                        )


def run_inner():
    inner_api = "https://df.alipay.com/api/v1/chat/completions"
    payload = {
        "chat_mode": "chat_agent",
        "model_name": "bailing_65b_v21_0520_proxyllm",
        "user_input": "昨天上午十点左右，m2o_gzcommon集群有没有异常",
        "app_code": "488a4292-0058-11ef-bba5-02420bbda2f2",
        "conv_uid": "uid_i123578",
    }

    headers = {
        "User-Id": "d24923f980b0415fa1d56f425f029466",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        url=inner_api, data=json.dumps(payload), headers=headers, stream=True
    )
    resp.raise_for_status()
    from datetime import datetime

    # 获取当前的日期和时间
    for line in resp.iter_lines():
        if line:
            decoded_line = line.decode("utf-8")
            now = datetime.now()
            print(f"\n\n[DEBUG]{now.strftime('%Y-%m-%d %H:%M:%S')}__{decoded_line}")


if __name__ == "__main__":
    api_prod = "https://df.alipay.com/openapi/v1/chat/completions"
    app_code_prod = "488a4292-0058-11ef-bba5-02420bbda2f2"

    api_dev = "http://local.alipay.net/openapi/v1/chat/completions"
    app_code_dev = "f1e3e4f6-11c9-11ef-b7f7-2e66c21b34b8"
    # dev
    llm_context = {}
    payload = {
        "chat_type": "app",
        "stream": True,
        "user_input": "今天天上午11左右，m2o_gzcommon集群有没有异常",
        "conv_uid": "uid_123490",
        "context": {
            "model": "bailing_proxyllm",
            "app_code": app_code_prod,
            "enable_verbose": True,
        },
    }

    headers = {
        "DBGPT_API_KEY": "antdbgpt",
        "DBGPT_API_TOKEN": "83a292ba-70d4-4bb0-a402-6743524c131c",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    asyncio.run(run(headers, payload))

    # asyncio.run(run_https(api_prod, headers, payload))

    # run_inner()

    #
    # resp = requests.post(url=api_prod, data=json.dumps(payload), headers=headers, stream=True)
    # resp.raise_for_status()
    # from datetime import datetime
    #
    # # 获取当前的日期和时间
    # for line in resp.iter_lines(chunk_size=16 * 1024):
    #     if line:
    #         decoded_line = line.decode('utf-8')
    #         now = datetime.now()
    #         print(f"\n\n[DEBUG]{now.strftime('%Y-%m-%d %H:%M:%S')}__{decoded_line}")
