from pilot.model.proxy.llms.proxy_model import ProxyModel


def tongyi_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    yield "tongyi LLM was not supported!"
