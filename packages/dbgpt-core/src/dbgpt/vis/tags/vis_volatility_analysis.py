"""Vis Volatility Analysis."""

import logging
from typing import Any, Dict, Optional

from ..base import Vis

logger = logging.getLogger(__name__)


class VisVolatilityAnalysis(Vis):
    """VisVolatilityAnalysis."""

    @classmethod
    def vis_tag(cls):
        """Return current vis protocol module tag name."""
        return "volatility-analysis"

    def sync_generate_param(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Generate the parameters required by the vis protocol."""
        return kwargs.get("content", {})

    async def display(self, content: Dict[str, Any]) -> Optional[str]:
        """Display the visualization content in the required format.

        Format:
        1. First line: metric name, baseline total, current total, dimension
        2. Following lines: for each factor, show baseline value, current value,
           contribution rate
        """
        if not content:
            return None

        try:
            metric_name = content.get("metric_name", "Unknown Metric")
            baseline_total = content.get("baseline_total", 0)
            current_total = content.get("current_total", 0)
            dimension = content.get("dimension", "Unknown Dimension")
            factors = content.get("factors", [])

            result_lines = []

            first_line = (
                f"{metric_name} 基期值:{baseline_total:.2f} 当期值:{current_total:.2f} "
                f"归因维度:{dimension}"
            )
            result_lines.append(first_line)

            for factor_info in factors:
                factor = factor_info.get("factor", "Unknown Factor")
                baseline_value = factor_info.get("baseline_value", 0)
                current_value = factor_info.get("current_value", 0)
                contribution_rate = factor_info.get("contribution_rate", 0)

                factor_line = (
                    f"{factor} 基期值:{baseline_value:.2f} 当期值:{current_value:.2f} "
                    f"贡献度:{contribution_rate:.2%}"
                )
                result_lines.append(factor_line)

            return "\n\n".join(result_lines)
        except Exception as e:
            logger.error(f"Error in displaying volatility analysis: {e}")
            return f"Error displaying volatility analysis: {str(e)}"
