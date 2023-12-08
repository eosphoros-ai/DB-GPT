#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import abc
import functools
import time


# TODO Rewrite this
def retry_stream_api(
    num_retries: int = 10, backoff_base: float = 2.0, warn_user: bool = True
):
    """Retry an Vicuna Server call.

    Args:
        num_retries int: Number of retries. Defaults to 10.
        backoff_base float: Base for exponential backoff. Defaults to 2.
        warn_user bool: Whether to warn the user. Defaults to True.
    """
    retry_limit_msg = f"Error: Reached rate limit, passing..."
    backoff_msg = f"Error: API Bad gateway. Waiting {{backoff}} seconds..."

    def _wrapper(func):
        @functools.wraps(func)
        def _wrapped(*args, **kwargs):
            user_warned = not warn_user
            num_attempts = num_retries + 1  # +1 for the first attempt
            for attempt in range(1, num_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if (e.http_status != 502) or (attempt == num_attempts):
                        raise

                backoff = backoff_base ** (attempt + 2)
                time.sleep(backoff)

        return _wrapped

    return _wrapper


class ChatIO(abc.ABC):
    @abc.abstractmethod
    def prompt_for_input(self, role: str) -> str:
        """Prompt for input from a role."""

    @abc.abstractmethod
    def prompt_for_output(self, role: str) -> str:
        """Prompt for output from a role."""

    @abc.abstractmethod
    def stream_output(self, output_stream, skip_echo_len: int):
        """Stream output."""


class SimpleChatIO(ChatIO):
    def prompt_for_input(self, role: str) -> str:
        return input(f"{role}: ")

    def prompt_for_output(self, role: str) -> str:
        print(f"{role}: ", end="", flush=True)

    def stream_output(self, output_stream, skip_echo_len: int):
        pre = 0
        for outputs in output_stream:
            outputs = outputs[skip_echo_len:].strip()
            now = len(outputs) - 1
            if now > pre:
                print(" ".join(outputs[pre:now]), end=" ", flush=True)
                pre = now

        print(" ".join(outputs[pre:]), flush=True)
        return " ".join(outputs)
