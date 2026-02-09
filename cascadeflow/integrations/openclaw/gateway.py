"""
OpenClaw gateway frame adapter.

Accepts OpenClaw protocol frames and routes supported requests to Cascadeflow.
This is a minimal bridge intended to be called by an OpenClaw transport layer.
"""

from typing import Any, Optional

from .wrapper import OpenClawAdapter, OpenClawAdapterConfig


class OpenClawGatewayAdapter:
    """Handle OpenClaw frames and produce response frames."""

    def __init__(self, adapter: OpenClawAdapter):
        self.adapter = adapter

    @classmethod
    def from_agent(cls, agent, config: Optional[OpenClawAdapterConfig] = None):
        return cls(OpenClawAdapter(agent=agent, config=config))

    async def handle_frame(self, frame: dict[str, Any]) -> Optional[dict[str, Any]]:
        frame_type = frame.get("type")
        if frame_type == "req":
            return await self._handle_request(frame)
        if frame_type == "event":
            return await self._handle_event(frame)
        return None

    async def _handle_request(self, frame: dict[str, Any]) -> dict[str, Any]:
        request_id = frame.get("id")
        method = frame.get("method")
        params = frame.get("params") or {}

        try:
            result = await self.adapter.run_frame(
                method=method,
                params=params,
                payload=None,
            )
        except Exception as exc:
            return {
                "type": "res",
                "id": request_id or "unknown",
                "ok": False,
                "error": {
                    "code": "cascadeflow_error",
                    "message": str(exc),
                },
            }

        return {
            "type": "res",
            "id": request_id or "unknown",
            "ok": True,
            "payload": {
                "message": result.content,
                "model_used": result.model_used,
                "metadata": result.metadata,
            },
        }

    async def _handle_event(self, frame: dict[str, Any]) -> Optional[dict[str, Any]]:
        """No-op for now; OpenClaw events are handled by the gateway itself."""
        return None


__all__ = ["OpenClawGatewayAdapter"]
