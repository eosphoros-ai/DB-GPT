import os
import json
import base64
import hmac
import hashlib
import websockets 
import asyncio
from datetime import datetime
from typing import List
from time import mktime
from urllib.parse import urlencode
from urllib.parse import urlparse
from wsgiref.handlers import format_date_time
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType
from pilot.model.proxy.llms.proxy_model import ProxyModel

SPARK_DEFAULT_API_VERSION = "v2"

def spark_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    model_params = model.get_params()
    proxy_api_version = os.getenv("XUNFEI_SPARK_API_VERSION") or SPARK_DEFAULT_API_VERSION
    proxy_api_key = os.getenv("XUNFEI_SPARK_API_KEY")
    proxy_api_secret = os.getenv("XUNFEI_SPARK_API_SECRET")
    proxy_app_id = os.getenv("XUNFEI_SPARK_APPID")

    if proxy_api_version == SPARK_DEFAULT_API_VERSION:
        url = "ws://spark-api.xf-yun.com/v2.1/chat"
        domain = "generalv2" 
    else:
        domain = "general"
        url = "ws://spark-api.xf-yun.com/v1.1/chat"

    
    messages: List[ModelMessage] = params["messages"] 
    
    history = []
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
    
    spark_api = SparkAPI(proxy_app_id, proxy_api_key, proxy_api_secret, url)
    request_url = spark_api.gen_url()

    temp_his = history[::-1]
    last_user_input = None
    for m in temp_his:
        if m["role"] == "user":
            last_user_input = m
            break
        
    data = {
        "header": {
            "app_id": proxy_app_id,
            "uid": params.get("request_id", 1)
        },
        "parameter": {
            "chat": {
                "domain": domain,
                "random_threshold": 0.5,
                "max_tokens": context_len,
                "auditing": "default",
                "temperature": params.get("temperature")
            }
        },
        "payload": {
            "message": {
                "text": last_user_input.get("") 
            }
        }
    }

    # TODO
     

async def async_call(request_url, data):
    async with websockets.connect(request_url) as ws:
        await ws.send(json.dumps(data, ensure_ascii=False))
        finish = False
        while not finish:
            chunk =  ws.recv()
            response = json.loads(chunk)
            if response.get("header", {}).get("status") == 2:
                finish = True
            if text := response.get("payload", {}).get("choices", {}).get("text"):
                yield text[0]["content"] 
  
class SparkAPI:
    
    def __init__(self, appid: str, api_key: str, api_secret: str, spark_url: str) -> None:
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = urlparse(spark_url).netloc
        self.path = urlparse(spark_url).path
        
        self.spark_url = spark_url

    
    def gen_url(self):
        
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple())) 

        _signature = "host: " + self.host + "\n"
        _signature += "data: " + date + "\n"
        _signature += "GET " + self.path + " HTTP/1.1"

        _signature_sha = hmac.new(self.api_secret.encode("utf-8"), _signature.encode("utf-8"), 
                                  digestmod=hashlib.sha256).digest()

        _signature_sha_base64 = base64.b64encode(_signature_sha).decode(encoding="utf-8")
        _authorization = f"api_key='{self.api_key}', algorithm='hmac-sha256', headers='host date request-line', signature='{_signature_sha_base64}'"

        authorization = base64.b64encode(_authorization.encode('utf-8')).decode(encoding='utf-8')
    
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }

        url = self.spark_url + "?" + urlencode(v)
        return url 

    