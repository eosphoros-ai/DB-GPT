# LLMs

In the underlying large model integration, we have designed an open interface that supports integration with various large models. At the same time, we have a very strict control and evaluation mechanism for the effectiveness of the integrated models. In terms of accuracy, the integrated models need to align with the capability of ChatGPT at a level of 85% or higher. We use higher standards to select models, hoping to save users the cumbersome testing and evaluation process in the process of use.

##  Multi LLMs Usage
To use multiple models, modify the LLM_MODEL parameter in the .env configuration file to switch between the models.

Notice: you can create .env file from .env.template, just use command like this:
```
cp .env.template .env
LLM_MODEL=vicuna-13b
MODEL_SERVER=http://127.0.0.1:8000
```
now we support models vicuna-13b, vicuna-7b, chatglm-6b, flan-t5-base, guanaco-33b-merged, falcon-40b, gorilla-7b, llama-2-7b, llama-2-13b.

if you want use other model, such as chatglm-6b, you just need update .env config file.
```
LLM_MODEL=chatglm-6b
```
or chatglm2-6b, which  is the second-generation version of the open-source bilingual (Chinese-English) chat model ChatGLM-6B. 
```
LLM_MODEL=chatglm2-6b
```



## Run Model with cpu.
we alse support smaller models, like gpt4all.  you can use it with cpu/mps(M1/M2), Download from [gpt4all model](https://gpt4all.io/models/ggml-gpt4all-j-v1.3-groovy.bin)

put it in the models path, then change .env config.
```
LLM_MODEL=gptj-6b
```

DB-GPT provides a model load adapter and chat adapter. load adapter which allows you to easily adapt load different LLM models by inheriting the BaseLLMAdapter. You just implement match() and loader() method.

vicuna llm load adapter

```
class VicunaLLMAdapater(BaseLLMAdaper):
    """Vicuna Adapter"""

    def match(self, model_path: str):
        return "vicuna" in model_path

    def loader(self, model_path: str, from_pretrained_kwagrs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
        model = AutoModelForCausalLM.from_pretrained(
            model_path, low_cpu_mem_usage=True, **from_pretrained_kwagrs
        )
        return model, tokenizer
```

chatglm load adapter
```

class ChatGLMAdapater(BaseLLMAdaper):
    """LLM Adatpter for THUDM/chatglm-6b"""

    def match(self, model_path: str):
        return "chatglm" in model_path

    def loader(self, model_path: str, from_pretrained_kwargs: dict):
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        if DEVICE != "cuda":
            model = AutoModel.from_pretrained(
                model_path, trust_remote_code=True, **from_pretrained_kwargs
            ).float()
            return model, tokenizer
        else:
            model = (
                AutoModel.from_pretrained(
                    model_path, trust_remote_code=True, **from_pretrained_kwargs
                )
                .half()
                .cuda()
            )
            return model, tokenizer
```
chat adapter which allows you to easily adapt chat different LLM models by inheriting the BaseChatAdpter.you just implement match() and get_generate_stream_func() method

vicuna llm chat adapter
```
class VicunaChatAdapter(BaseChatAdpter):
 """Model chat Adapter for vicuna"""

    def match(self, model_path: str):
        return "vicuna" in model_path

    def get_generate_stream_func(self):
        return generate_stream
```

chatglm llm chat adapter
```
class ChatGLMChatAdapter(BaseChatAdpter):
    """Model chat Adapter for ChatGLM"""

    def match(self, model_path: str):
        return "chatglm" in model_path

    def get_generate_stream_func(self):
        from pilot.model.llm_out.chatglm_llm import chatglm_generate_stream

        return chatglm_generate_stream
```
 if you want to integrate your own model, just need to inheriting BaseLLMAdaper and BaseChatAdpter and implement the methods

## Multi Proxy LLMs
### 1. Openai proxy
 If you haven't deployed a private infrastructure for a large model, or if you want to use DB-GPT in a low-cost and high-efficiency way, you can also use OpenAI's large model as your underlying model.

- If your environment deploying DB-GPT has access to OpenAI, then modify the .env configuration file as below will work.
```
LLM_MODEL=proxyllm
MODEL_SERVER=127.0.0.1:8000
PROXY_API_KEY=sk-xxx
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
```

- If you can't access OpenAI locally but have an OpenAI proxy service, you can configure as follows.
```
LLM_MODEL=proxyllm
MODEL_SERVER=127.0.0.1:8000
PROXY_API_KEY=sk-xxx
PROXY_SERVER_URL={your-openai-proxy-server/v1/chat/completions}
```
