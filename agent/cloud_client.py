"""Outbound WebSocket client used by a customer-installed AutoUI agent."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import time
from typing import Any

import websockets

from computer.screen import take_screenshot
from computer.ocr_locator import locate_target
from computer.executor import execute_action

GRID_COLUMNS = 12
GRID_ROWS = 8
ALLOWED_ACTIONS = {"click", "double_click", "type", "key", "hotkey", "scroll", "wait"}


def _perform_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    action_type = action.get("action")

    if action_type == "click_text":
        text = action.get("text")
        cells = action.get("cells")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("click_text requires non-empty text")
        if not isinstance(cells, list) or not cells:
            raise ValueError("click_text requires grid cells from the latest screenshot")
        if not all(isinstance(cell, int) and 1 <= cell <= GRID_COLUMNS * GRID_ROWS for cell in cells):
            raise ValueError("grid cells must be integers from 1 to 96")
        screenshot = take_screenshot()
        location = locate_target(screenshot, text, cells, GRID_COLUMNS, GRID_ROWS)
        execute_action({"action": "click", "x": int(location["x"]), "y": int(location["y"])})
        return {"action": "click_text", "text": text, "location": location}

    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported action: {action_type!r}")
    if action_type in {"click", "double_click"}:
        if not all(isinstance(action.get(k), int) for k in ("x", "y")):
            raise ValueError(f"{action_type} requires integer x and y")
    elif action_type == "type" and not isinstance(action.get("text"), str):
        raise ValueError("type requires text")
    elif action_type == "key" and not isinstance(action.get("key"), str):
        raise ValueError("key requires key")
    elif action_type == "hotkey":
        keys = action.get("keys")
        if not isinstance(keys, list) or not keys or not all(isinstance(k, str) for k in keys):
            raise ValueError("hotkey requires a non-empty list of keys")
    elif action_type == "scroll":
        amount = action.get("scroll_amount", action.get("amount", 1))
        if not isinstance(amount, (int, float)) or abs(amount) > 20:
            raise ValueError("scroll amount must be between -20 and 20")
    elif action_type == "wait":
        seconds = action.get("seconds", 1)
        if not isinstance(seconds, (int, float)) or not 0 <= seconds <= 10:
            raise ValueError("wait must be between 0 and 10 seconds")

    execute_action(action)
    return {"action": action_type, "executed": action}


async def handle_command(websocket, message: dict[str, Any]) -> None:
    request_id = str(message.get("request_id", ""))
    command = message.get("command")
    try:
        if command == "get_screenshot":
            screenshot = await asyncio.to_thread(take_screenshot)
            from io import BytesIO
            buffer = BytesIO()
            screenshot.save(buffer, format="PNG")
            response = {
                "type": "command_result", "request_id": request_id,
                "success": True, "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
            }
        elif command == "execute_action":
            action = (message.get("payload") or {}).get("action")
            result = await asyncio.to_thread(_perform_action, action)
            response = {"type": "command_result", "request_id": request_id,
                        "success": True, "result": result}
        else:
            response = {"type": "command_result", "request_id": request_id,
                        "success": False, "error": f"Unknown command: {command}"}
    except Exception as exc:
        response = {"type": "command_result", "request_id": request_id,
                    "success": False, "error": str(exc)}
    await websocket.send(json.dumps(response))


async def run_cloud_agent() -> None:
    url = os.environ["AUTOUI_GATEWAY_URL"]  # e.g. wss://api.example.com/agent/ws
    device_id = os.environ["AUTOUI_DEVICE_ID"]
    device_token = os.environ["AUTOUI_DEVICE_TOKEN"]
    delay = 1.0
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=20 * 1024 * 1024) as ws:
                await ws.send(json.dumps({
                    "type": "register", "device_id": device_id, "device_token": device_token,
                }))
                acknowledgement = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if acknowledgement.get("type") != "registered":
                    raise RuntimeError("Gateway did not confirm device registration")
                delay = 1.0
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") == "command":
                        await handle_command(ws, message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Cloud gateway connection failed: {exc}")
            await asyncio.sleep(min(delay, 30) + random.random())
            delay = min(delay * 2, 30)


if __name__ == "__main__":
    asyncio.run(run_cloud_agent())
