class LLMChatError(Exception):
    """
    llm conversation result generates exception
    """

    def __init__(self, message="LLM Chat Generrate Error!", original_exception=None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

    def __str__(self):
        if self.original_exception:
            # 返回自定义异常信息和原始异常信息
            return f"{self.message}({self.original_exception})"
        else:
            return self.message
