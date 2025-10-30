"""
DB-GPT Sandbox Main Entry Point
"""

import argparse
import logging
import sys

from .user_layer.service import initialize_sandbox

logger = logging.getLogger(__name__)


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="DB-GPT Sandbox Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level",
    )
    return parser.parse_args()


def run_sandbox_server(
    host: str = "0.0.0.0", port: int = 8000, log_level: str = "info"
):
    """运行沙箱服务器"""
    setup_logging()

    logger.info(f"Starting DB-GPT Sandbox server on {host}:{port}")

    try:
        initialize_sandbox(host=host, port=port, log_level=log_level)
    except KeyboardInterrupt:
        logger.info("Shutting down DB-GPT Sandbox server...")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


def main():
    """默认入口函数"""
    args = parse_args()
    run_sandbox_server(args.host, args.port, args.log_level)


if __name__ == "__main__":
    main()
