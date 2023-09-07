from pilot.model.proxy.llms.proxy_model import ProxyModel


def zhipu_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    proxy_api_key = model_params.proxy_api_key
    proxy_server_url = model_params.proxy_server_url
    proxyllm_backend = model_params.proxyllm_backend

    if not proxyllm_backend:
        proxyllm_backend = "chatglm_pro"
    # TODO
    yield "Zhipu LLM was not supported!"
