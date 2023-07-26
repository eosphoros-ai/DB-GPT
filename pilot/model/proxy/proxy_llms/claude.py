from pilot.configs.config import Config

CFG = Config()


def claude_generate_stream(model, tokenizer, params, device, context_len=2048):
    yield "claude LLM was not supported!"
