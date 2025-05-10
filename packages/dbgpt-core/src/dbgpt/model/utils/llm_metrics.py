import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMPerformanceMetrics:
    """Performance metrics for LLM inference, including prefill and decode phases"""

    # Token counts
    input_token_count: int = 0
    total_tokens_generated: int = 0
    prev_tokens_count: int = 0

    # Time measurements in nanoseconds
    start_time_ns: int = field(default_factory=time.time_ns)
    prefill_start_time_ns: Optional[int] = None
    prefill_end_time_ns: Optional[int] = None
    prefill_time_ns: Optional[int] = None
    decode_start_time_ns: Optional[int] = None
    total_time_ns: Optional[int] = None

    # Timestamps and measurements
    token_timestamps_ns: List[int] = field(default_factory=list)
    decode_times_ns: List[int] = field(default_factory=list)

    # Calculated metrics (tokens per second)
    prefill_tokens_per_second: Optional[float] = None
    decode_tokens_per_second: Optional[float] = None
    end_to_end_tokens_per_second: Optional[float] = None

    # Additional computed values
    avg_decode_time: Optional[float] = None

    def to_dict(self) -> Dict[str, any]:
        """Convert metrics to a dictionary for API response, with times in seconds"""
        metrics = {
            "input_token_count": self.input_token_count,
            "total_tokens_generated": self.total_tokens_generated,
        }

        # Add time metrics in seconds
        if self.prefill_time_ns is not None:
            metrics["prefill_time"] = self.prefill_time_ns / 1e9
            metrics["prefill_tokens_per_second"] = self.prefill_tokens_per_second or 0

        if self.total_time_ns is not None:
            metrics["total_time"] = self.total_time_ns / 1e9

        if self.decode_times_ns:
            metrics["avg_decode_time"] = self.avg_decode_time
            metrics["decode_tokens_per_second"] = self.decode_tokens_per_second or 0

        # Add throughput metrics
        metrics["end_to_end_tokens_per_second"] = self.end_to_end_tokens_per_second or 0

        return metrics


class LLMPerformanceMonitor:
    """Generic performance monitor for LLM inference that tracks prefill and decode
    phases"""

    def __init__(self, input_token_count: int = 0):
        # Performance metrics
        self.metrics = LLMPerformanceMetrics(input_token_count=input_token_count)

        # Phase flags
        self.prefill_started: bool = False
        self.first_token_received: bool = False

    def start_prefill(self) -> int:
        """Mark the beginning of the prefill phase using nanosecond timestamp"""
        timestamp = time.time_ns()
        self.metrics.prefill_start_time_ns = timestamp
        self.prefill_started = True
        return timestamp

    def on_tokens_received(self, current_token_count: int) -> Dict[str, any]:
        """
        Called when new tokens are received from LLM
        Returns updated performance metrics
        """
        current_time_ns = time.time_ns()

        # Calculate new tokens received in this batch
        new_tokens = current_token_count - self.metrics.prev_tokens_count

        # Auto-detect the end of prefill / start of decode phase
        if self.prefill_started and not self.first_token_received and new_tokens > 0:
            # This is the first tokens batch - mark the end of prefill phase
            self.metrics.prefill_end_time_ns = current_time_ns
            self.metrics.prefill_time_ns = (
                self.metrics.prefill_end_time_ns - self.metrics.prefill_start_time_ns
            )

            # Convert nanoseconds to seconds for calculation and logging
            prefill_time_sec = self.metrics.prefill_time_ns / 1e9

            # Calculate prefill speed
            if self.metrics.input_token_count > 0 and prefill_time_sec > 0:
                self.metrics.prefill_tokens_per_second = (
                    self.metrics.input_token_count / prefill_time_sec
                )
                logger.info(
                    f"Prefill speed: {self.metrics.prefill_tokens_per_second:.2f} "
                    f"tokens/s for {self.metrics.input_token_count} tokens"
                )

            # Mark the beginning of decode phase
            self.metrics.decode_start_time_ns = current_time_ns
            self.first_token_received = True

        # Record token generation data
        if self.first_token_received and new_tokens > 0:
            # If we've already received tokens, add decode time for this batch
            if len(self.metrics.token_timestamps_ns) > 0:
                last_timestamp_ns = self.metrics.token_timestamps_ns[-1]
                token_decode_time_ns = current_time_ns - last_timestamp_ns

                # Distribute the time evenly across all new tokens in this batch
                time_per_token = token_decode_time_ns / new_tokens
                for _ in range(new_tokens):
                    self.metrics.decode_times_ns.append(time_per_token)

        # Record the current token batch timestamp
        self.metrics.token_timestamps_ns.append(current_time_ns)
        self.metrics.total_tokens_generated += new_tokens
        self.metrics.prev_tokens_count = current_token_count

        # Calculate current metrics
        self._update_metrics(current_time_ns)

        return self.get_metrics_dict()

    def _update_metrics(self, current_time_ns: Optional[int] = None) -> None:
        """Update the performance metrics based on current state"""
        if current_time_ns is None:
            current_time_ns = time.time_ns()

        # Record total time
        self.metrics.total_time_ns = current_time_ns - self.metrics.start_time_ns

        # Calculate average decode speed
        if self.metrics.decode_times_ns:
            # Convert to seconds
            decode_times_sec = [t / 1e9 for t in self.metrics.decode_times_ns]
            self.metrics.avg_decode_time = sum(decode_times_sec) / len(decode_times_sec)
            self.metrics.decode_tokens_per_second = 1.0 / self.metrics.avg_decode_time

        # Calculate end-to-end throughput
        total_time_sec = self.metrics.total_time_ns / 1e9
        if total_time_sec > 0:
            total_tokens = (
                self.metrics.input_token_count + self.metrics.total_tokens_generated
            )
            self.metrics.end_to_end_tokens_per_second = total_tokens / total_time_sec

    def end_generation(self) -> Dict[str, any]:
        """Mark the end of generation and finalize metrics"""
        current_time_ns = time.time_ns()
        self._update_metrics(current_time_ns)

        # Log final performance data
        total_time_sec = self.metrics.total_time_ns / 1e9
        logger.info(f"Generation complete. Total time: {total_time_sec:.6f}s")

        if self.metrics.prefill_tokens_per_second:
            logger.info(
                f"Final prefill speed: {self.metrics.prefill_tokens_per_second:.2f} "
                "tokens/s"
            )

        if self.metrics.decode_tokens_per_second:
            logger.info(
                f"Final decode speed: {self.metrics.decode_tokens_per_second:.2f} "
                "tokens/s"
            )

        if self.metrics.end_to_end_tokens_per_second:
            logger.info(
                "End-to-end throughput: "
                f"{self.metrics.end_to_end_tokens_per_second:.2f} tokens/s"
            )

        return self.get_metrics_dict()

    def get_metrics_dict(self) -> Dict[str, any]:
        """Get performance metrics as dictionary, converting nanoseconds to seconds
        for external use"""
        return self.metrics.to_dict()
