"""Apply the connector's existing confirmation policy to direct tool calls."""

import asyncio
import uuid


def make_connector_gate(manager, selected_tool_names):
    async def gate(name: str, args: dict):
        if manager is None or name not in selected_tool_names:
            return None
        from dbgpt.agent.resource.connector.confirmation import _PENDING_CONFIRMATIONS

        # Policy/registry failures must not silently authorize a connector write.
        interceptor = manager.get_confirmation_interceptor()
        if not interceptor.should_confirm(name, args):
            return None
        registry = manager.get_confirmation_registry()
        confirm_id = str(uuid.uuid4())
        registry.register(confirm_id)
        _PENDING_CONFIRMATIONS[confirm_id] = {
            "confirm_id": confirm_id,
            "tool_name": name,
            "args_summary": interceptor._summarize_args(args),
            "message": f"即将执行写操作 {name}，是否确认？",
            "timeout": 300,
        }
        try:
            approved = await asyncio.wait_for(registry.wait_for(confirm_id), 300)
        except asyncio.TimeoutError:
            approved = False
        finally:
            _PENDING_CONFIRMATIONS.pop(confirm_id, None)
        return None if approved else "用户拒绝或确认超时，连接器操作已取消。"

    return gate
