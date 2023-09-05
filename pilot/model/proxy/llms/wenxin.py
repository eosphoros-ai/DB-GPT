from pilot.model.proxy.llms.proxy_model import ProxyModel


def wenxin_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    yield "wenxin LLM is not supported!"
