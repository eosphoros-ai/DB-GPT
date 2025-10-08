"""Vis Anomaly Detection."""

from typing import Any, Dict, Optional

from ..base import Vis


class VisAnomalyDetection(Vis):
    """VisAnomalyDetection."""

    @classmethod
    def vis_tag(cls):
        """Vis tag name.

        Returns:
            str: The tag name associated with the visualization.
        """
        return "anomaly-detection"

    async def display(self, content: Dict[str, Any]) -> Optional[str]:
        """Display the visualization content."""
        if not content:
            return None

        is_anomaly = content.get("is_anomaly", False)
        metric_name = content.get("metric_name", "Unknown Metric")
        fluctuation_rate = content.get("fluctuation_rate", 0)
        threshold = content.get("threshold", 0)

        if is_anomaly:
            anomaly_type = content.get("anomaly_type", "unknown")
            direction = "上升" if anomaly_type == "increase" else "下降"
            result = f"[异常检测] {metric_name} 检测到{direction}异常\n"
            result += f"  波动率: {fluctuation_rate * 100:.2f}%\n"
            result += f"  阈值: {threshold * 100:.2f}%\n"
        else:
            result = f"[异常检测] {metric_name} 未检测到异常\n"
            result += f"  波动率: {fluctuation_rate * 100:.2f}%\n"
            result += f"  阈值: {threshold * 100:.2f}%\n"

        return result
