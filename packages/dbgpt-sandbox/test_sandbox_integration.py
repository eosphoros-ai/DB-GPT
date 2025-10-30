#!/usr/bin/env python3
"""
DB-GPT Sandbox Integration Test Script
Test code execution functionality of sandbox service
"""

import asyncio
import logging
import sys
from typing import Any, Dict

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SandboxTester:
    """Sandbox test class"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def health_check(self) -> bool:
        """Health check"""
        try:
            response = self.session.get(f"{self.base_url}/api/health", timeout=5)
            return response.status_code == 200 and response.json().get("status") == "ok"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_methods(self) -> Dict[str, Any]:
        """Get available methods"""
        try:
            response = self.session.get(f"{self.base_url}/api/methods", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get available methods: {e}")
            return {}

    def connect(
        self, user_id: str, task_id: str, image_type: str = "python"
    ) -> Dict[str, Any]:
        """Establish sandbox session"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/connect",
                json={
                    "user_id": user_id,
                    "task_id": task_id,
                    "image_type": image_type,
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return {"status": "error", "error": str(e)}

    def execute_code(
        self, session_id: str, code_type: str, code_content: str
    ) -> Dict[str, Any]:
        """Execute code"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/execute",
                json={
                    "session_id": session_id,
                    "code_type": code_type,
                    "code_content": code_content,
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Get execution status"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/status",
                json={"session_id": session_id},
                timeout=5,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {"status": "error", "error": str(e)}

    def disconnect(self, user_id: str, task_id: str) -> Dict[str, Any]:
        """Disconnect session"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/disconnect",
                json={
                    "user_id": user_id,
                    "task_id": task_id,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Disconnection failed: {e}")
            return {"status": "error", "error": str(e)}

    def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions"""
        try:
            response = self.session.get(f"{self.base_url}/api/sessions", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return {"sessions": []}


async def run_integration_tests():
    """Run integration tests"""
    tester = SandboxTester()

    try:
        logger.info("=== Starting Integration Tests ===")

        # Health check
        logger.info("1. Health check")
        if not tester.health_check():
            logger.error(
                "Health check failed, please ensure sandbox service is running"
            )
            logger.error(
                "Run command: SANDBOX_RUNTIME=local uv run --no-sync dbgpt-sandbox"
            )
            return False
        logger.info("✓ Health check passed")

        # Get available methods
        logger.info("2. Get available methods")
        methods = tester.get_methods()
        if not methods:
            logger.error("Failed to get available methods")
            return False
        logger.info(f"✓ Available methods: {len(methods.get('methods', []))}")

        # Test connection
        logger.info("3. Test connection")
        import time

        user_id = "test_user"
        task_id = f"test_task_{int(time.time())}"
        connect_result = tester.connect(user_id, task_id, "python")

        if connect_result.get("status") != "success":
            logger.error(f"Connection failed: {connect_result}")
            return False
        logger.info("✓ Connection successful")

        session_id = f"{user_id}_{task_id}"

        # Test simple Python code execution
        logger.info("4. Test simple Python code execution")
        simple_code = "print('Hello from sandbox!')"
        execute_result = tester.execute_code(session_id, "python", simple_code)

        if execute_result.get("status") != "success":
            logger.error(f"Code execution failed: {execute_result}")
            return False
        logger.info(
            f"✓ Simple code execution successful: {execute_result.get('output')}"
        )

        # Test mathematical calculations
        logger.info("5. Test mathematical calculations")
        math_code = """
import math
result = math.sqrt(16)
print(f"sqrt(16) = {result}")
print(f"2 + 3 * 4 = {2 + 3 * 4}")
"""
        math_result = tester.execute_code(session_id, "python", math_code)

        if math_result.get("status") != "success":
            logger.error(f"Math calculation failed: {math_result}")
            return False
        logger.info(f"✓ Math calculation successful: {math_result.get('output')}")

        # Test string operations
        logger.info("6. Test string operations")
        string_code = """
text = "Hello from sandbox!"
reversed_text = text[::-1]
print(f"Original text: {text}")
print(f"Reversed text: {reversed_text}")
print(f"Text length: {len(text)}")
"""
        string_result = tester.execute_code(session_id, "python", string_code)

        if string_result.get("status") != "success":
            logger.error(f"String operation failed: {string_result}")
            return False
        logger.info(f"✓ String operation successful: {string_result.get('output')}")

        # Test error handling
        logger.info("7. Test error handling")
        error_code = """
# Intentionally trigger an error
result = 1 / 0
"""
        error_result = tester.execute_code(session_id, "python", error_code)

        # This should return error status, which is expected
        if error_result.get("status") == "success":
            logger.warning("Error code unexpectedly executed successfully")
        else:
            logger.info(
                f"✓ Error handling working properly: {error_result.get('error')}"
            )

        # Get session status
        logger.info("8. Get session status")
        status_result = tester.get_status(session_id)
        logger.info(f"✓ Session status: {status_result}")

        # List all sessions
        logger.info("9. List all sessions")
        sessions_result = tester.list_sessions()
        logger.info(f"✓ Active sessions: {sessions_result}")

        # Disconnect
        logger.info("10. Disconnect")
        disconnect_result = tester.disconnect(user_id, task_id)

        if disconnect_result.get("status") != "success":
            logger.error(f"Disconnection failed: {disconnect_result}")
            return False
        logger.info("✓ Disconnection successful")

        logger.info("=== All Integration Tests Passed! ===")
        return True

    except Exception as e:
        logger.error(f"Error occurred during integration testing: {e}")
        return False


def main():
    """Main function"""
    try:
        # Run async tests
        success = asyncio.run(run_integration_tests())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
