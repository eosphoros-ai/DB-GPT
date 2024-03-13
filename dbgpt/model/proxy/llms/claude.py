from dbgpt.model.proxy.llms.proxy_model import ProxyModel


def claude_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    yield "claude LLM was not supported!"
