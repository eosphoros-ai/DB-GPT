import logging

from transformers import TextIteratorStreamer

from .llm_metrics import LLMPerformanceMonitor

logger = logging.getLogger(__name__)


class PerformanceMonitoringStreamer(TextIteratorStreamer):
    """
    Extended TextIteratorStreamer that monitors LLM inference performance.
    Uses the generic LLMPerformanceMonitor for performance tracking.
    """

    def __init__(
        self,
        tokenizer,
        skip_prompt=False,
        timeout=None,
        input_token_count=0,
        **decode_kwargs,
    ):
        super().__init__(
            tokenizer, skip_prompt=skip_prompt, timeout=timeout, **decode_kwargs
        )

        # Initialize the performance monitor
        self.perf_monitor = LLMPerformanceMonitor(input_token_count=input_token_count)

        # Additional flags for streamer-specific behavior
        self.is_prompt_token = True  # Flag to track if current tokens are from prompt

    def start_prefill(self):
        """Mark the beginning of the prefill phase"""
        self.perf_monitor.start_prefill()

    def put(self, value):
        """
        Receive tokens and track performance metrics.
        Automatically detects prefill/decode phase transitions.
        """
        # Skip counting if these are prompt tokens and skip_prompt is True
        if self.skip_prompt and self.is_prompt_token:
            self.is_prompt_token = False  # Mark that we've processed the prompt tokens
            logger.debug("Skipping prompt tokens for performance measurement")
            super().put(value)  # Call parent method to continue flow
            return

        # Calculate number of new tokens
        token_count = len(value.tolist())
        total_token_count = self.perf_monitor.metrics.prev_tokens_count + token_count

        # Update performance metrics
        self.perf_monitor.on_tokens_received(total_token_count)

        # Call the parent method to continue the original flow
        super().put(value)

    def end(self):
        """End generation and finalize performance metrics"""
        # Finalize metrics
        self.perf_monitor.end_generation()

        # Call the parent method to continue the original flow
        super().end()

    def get_performance_metrics(self):
        """Get performance metrics in a format suitable for API responses"""
        return self.perf_monitor.get_metrics_dict()
