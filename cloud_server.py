"""Cloud gateway and remote MCP server for AutoUI.

Prototype auth is environment-backed. Replace token maps with your identity
provider/database before onboarding real customers.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import Context, FastMCP, Image
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

# JSON maps: device_id -> device token; bearer user token -> user_id;
# device_id -> owner user_id.
DEVICE_TOKENS: dict[str, str] = json.loads(os.getenv("AUTOUI_DEVICE_TOKENS", "{}"))
USER_TOKENS: dict[str, str] = json.loads(os.getenv("AUTOUI_USER_TOKENS", "{}"))
DEVICE_OWNERS: dict[str, str] = json.loads(os.getenv("AUTOUI_DEVICE_OWNERS", "{}"))
COMMAND_TIMEOUT = float(os.getenv("AUTOUI_COMMAND_TIMEOUT", "45"))

devices: dict[str, WebSocket] = {}
pending: dict[str, tuple[str, asyncio.Future]] = {}

mcp = FastMCP("AutoUI Cloud", streamable_http_path="/")


def user_from_context(ctx: Context) -> str:
    headers = ctx.headers or {}
    authorization = headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PermissionError("Connect your AutoUI account before using device tools.")
    user_id = USER_TOKENS.get(token)
    if not user_id:
        raise PermissionError("Invalid or expired AutoUI access token.")
    return user_id


def owned_device(user_id: str, device_id: str) -> WebSocket:
    if DEVICE_OWNERS.get(device_id) != user_id:
        raise PermissionError("This device is not registered to your account.")
    websocket = devices.get(device_id)
    if websocket is None:
        raise ConnectionError(f"Device {device_id!r} is offline.")
    return websocket


async def send_command(user_id: str, device_id: str, command: str,
                       payload: dict[str, Any] | None = None) -> dict[str, Any]:
    websocket = owned_device(user_id, device_id)
    request_id = str(uuid.uuid4())
    future = asyncio.get_running_loop().create_future()
    pending[request_id] = (device_id, future)
    try:
        await websocket.send_json({
            "type": "command",
            "request_id": request_id,
            "command": command,
            "payload": payload or {},
        })
        return await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
    finally:
        pending.pop(request_id, None)


async def agent_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    device_id: str | None = None
    try:
        registration = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        if registration.get("type") != "register":
            await websocket.close(code=4400, reason="Registration required")
            return
        candidate_id = str(registration.get("device_id", ""))
        supplied_token = str(registration.get("device_token", ""))
        expected_token = DEVICE_TOKENS.get(candidate_id, "")
        if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
            await websocket.close(code=4401, reason="Invalid device credentials")
            return
        device_id = candidate_id
        previous = devices.get(device_id)
        devices[device_id] = websocket
        if previous is not None and previous is not websocket:
            await previous.close(code=4001, reason="Replaced by a newer connection")
        await websocket.send_json({"type": "registered", "device_id": device_id})

        while True:
            message = await websocket.receive_json()
            if message.get("type") != "command_result":
                continue
            request_id = str(message.get("request_id", ""))
            entry = pending.get(request_id)
            if entry is None:
                continue
            expected_device, future = entry
            if expected_device != device_id or future.done():
                continue
            future.set_result(message)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if device_id and devices.get(device_id) is websocket:
            devices.pop(device_id, None)
        if device_id:
            for request_id, (pending_device, future) in list(pending.items()):
                if pending_device == device_id and not future.done():
                    future.set_exception(ConnectionError("Device disconnected."))


@mcp.tool()
async def list_devices(ctx: Context) -> list[dict[str, Any]]:
    """List the computers registered to your account and whether they are online."""
    user_id = user_from_context(ctx)
    return [
        {"device_id": device_id, "online": device_id in devices}
        for device_id, owner_id in DEVICE_OWNERS.items()
        if owner_id == user_id
    ]


@mcp.tool()
async def get_screenshot(device_id: str, ctx: Context) -> Image:
    """Capture the current screen of one of your connected computers."""
    user_id = user_from_context(ctx)
    result = await send_command(user_id, device_id, "get_screenshot")
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Screenshot failed."))
    encoded = result.get("image_base64")
    if not isinstance(encoded, str):
        raise RuntimeError("Agent returned no screenshot.")
    return Image(data=base64.b64decode(encoded), format="png")


@mcp.tool()
async def execute_action(device_id: str, action: dict[str, Any], ctx: Context) -> str:
    """Execute one supported desktop action on one of your computers.

    Supported action types: click, double_click, type, key, hotkey, scroll,
    wait, and click_text. Use get_screenshot first to ground the action in the
    current screen. This tool does not execute shell commands or arbitrary code.
    """
    user_id = user_from_context(ctx)
    result = await send_command(user_id, device_id, "execute_action", {"action": action})
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Action failed."))
    return json.dumps(result.get("result", {"success": True}), ensure_ascii=False)


@asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        WebSocketRoute("/agent/ws", agent_socket),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("cloud_server:app", host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8000")), reload=False)
