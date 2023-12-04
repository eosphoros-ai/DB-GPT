from pydantic import Field, BaseModel

DEFAULT_CONTEXT_WINDOW = 3900
DEFAULT_NUM_OUTPUTS = 256


class LLMMetadata(BaseModel):
    model_name: str = (
        Field(
            default="unknown",
            description=(
                "The model's name used for logging, testing, and sanity checking. For some"
                " models this can be automatically discerned. For other models, like"
                " locally loaded models, this must be manually specified."
            ),
        ),
    )
    context_window: int = (
        Field(
            default=DEFAULT_CONTEXT_WINDOW,
            description=(
                "Total number of tokens the model can be input and output for one response."
            ),
        ),
    )
    max_chat_iteration: int = (
        Field(
            default=5,
            description=("""max iteration chat with llm model"""),
        ),
    )
    concurrency_limit: int = (
        Field(
            default=3,
            description=("""concurrency call llm model service thread limit"""),
        ),
    )
    num_output: int = Field(
        default=DEFAULT_NUM_OUTPUTS,
        description="Number of tokens the model can output when generating a response.",
    )
    is_chat_model: bool = Field(
        default=False,
        description=(
            "Set True if the model exposes a chat interface (i.e. can be passed a"
            " sequence of messages, rather than text), like OpenAI's"
            " /v1/chat/completions endpoint."
        ),
    )
    is_function_calling_model: bool = Field(
        default=False,
        # SEE: https://openai.com/blog/function-calling-and-other-api-updates
        description=(
            "Set True if the model supports function calling messages, similar to"
            " OpenAI's function calling API. For example, converting 'Email Anya to"
            " see if she wants to get coffee next Friday' to a function call like"
            " `send_email(to: string, body: string)`."
        ),
    )
    model_name: str = Field(
        default="unknown",
        description=(
            "The model's name used for logging, testing, and sanity checking. For some"
            " models this can be automatically discerned. For other models, like"
            " locally loaded models, this must be manually specified."
        ),
    )
