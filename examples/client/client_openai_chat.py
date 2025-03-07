# /// script
# dependencies = [
#   "openai",
# ]
# [tool.uv]
# exclude-newer = "2025-03-07T00:00:00Z"
# ///
"""Chat With Your DB-GPT's API by OpenAI Client

Sample Usage:
```bash
uv run examples/client/client_openai_chat.py -m Qwen/QwQ-32B --input "Hello"
```

More examples:

1. Chat Normal Mode:
```bash
uv run examples/client/client_openai_chat.py -m Qwen/QwQ-32B \
    --input "Which is bigger, 9.8 or 9.11?"
```

2. Chat Database Mode(chat_with_db_qa):

```bash
uv run examples/client/client_openai_chat.py -m Qwen/QwQ-32B \
    --chat-mode chat_with_db_qa \
    --param "sqlite_dbgpt" \
    --input "Which table stores database connection information?"
```

3. Chat With Your Data(chat_data):
```bash
uv run examples/client/client_openai_chat.py -m Qwen/QwQ-32B \
    --chat-mode chat_data \
    --param "sqlite_dbgpt" \
    --input "Which database can I currently connect to? What is its name and type?"
```

4. Chat With Knowledge(chat_knowledge):
```bash
uv run examples/client/client_openai_chat.py -m Qwen/QwQ-32B \
    --chat-mode chat_knowledge \
    --param "awel" \
    --input "What is AWEL?"
```   


5. Chat With Third-party API(chat_third_party):
```bash
uv run examples/client/client_openai_chat.py -m deepseek-chat \
    --input "Which is bigger, 9.8 or 9.11?" \
    --chat-mode none \
    --api-key $DEEPSEEK_API_KEY \
    --api-base https://api.deepseek.com/v1
```

"""  # noqa

import argparse

from openai import OpenAI

DBGPT_API_KEY = "dbgpt"


def handle_output(response):
    has_thinking = False
    print("=" * 80)
    reasoning_content = ""
    for chunk in response:
        delta_content = chunk.choices[0].delta.content
        if hasattr(chunk.choices[0].delta, "reasoning_content"):
            reasoning_content = chunk.choices[0].delta.reasoning_content
        if reasoning_content:
            if not has_thinking:
                print("<thinking>", flush=True)
            print(reasoning_content, end="", flush=True)
            has_thinking = True
        if delta_content:
            if has_thinking:
                print("</thinking>", flush=True)
            print(delta_content, end="", flush=True)
            has_thinking = False


def main():
    parser = argparse.ArgumentParser(description="OpenAI Chat Client")
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="deepseek-chat",
        help="Model name",
    )
    parser.add_argument(
        "-c",
        "--chat-mode",
        type=str,
        default="chat_normal",
        help="Chat mode. Default is chat_normal",
    )
    parser.add_argument(
        "-p",
        "--param",
        type=str,
        default=None,
        help="Chat param",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="Hello, how are you?",
        help="User input",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=DBGPT_API_KEY,
        help="API key",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default="http://localhost:5670/api/v2",
        help="Base URL",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Max tokens",
    )
    args = parser.parse_args()

    client = OpenAI(
        api_key=args.api_key,
        base_url=args.api_base,
    )

    messages = [
        {
            "role": "user",
            "content": args.input,
        },
    ]

    extra_body = {}
    if args.chat_mode != "none":
        extra_body["chat_mode"] = args.chat_mode
    if args.param:
        extra_body["chat_param"] = args.param

    response = client.chat.completions.create(
        model=args.model,
        messages=messages,
        extra_body=extra_body,
        stream=True,
        max_tokens=args.max_tokens,
    )
    handle_output(response)


if __name__ == "__main__":
    main()
