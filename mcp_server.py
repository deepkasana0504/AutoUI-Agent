"""MCP adapter for exposing AutoUI's existing screenshot and executor to an MCP client.

Run on the same machine as the desktop being controlled:
    python mcp_server.py

This is a local stdio MCP server. It deliberately does not start the Gemini
planner or the existing phone/WebSocket task loop.
"""
from __future__ import annotations

import io
import json
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from computer.screen import take_screenshot
from computer.executor import execute_action
from computer.ocr_locator import locate_target

mcp = FastMCP("AutoUI-Agent")

GRID_COLUMNS = 12
GRID_ROWS = 8
ALLOWED_ACTIONS = {
    "click",
    "double_click",
    "type",
    "key",
    "hotkey",
    "scroll",
    "wait",
}


@mcp.tool()
def get_screenshot() -> Image:
    """Capture the current desktop and return it as an image for visual inspection."""
    screenshot = take_screenshot()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    return Image(data=buffer.getvalue(), format="png")


@mcp.tool()
def execute_desktop_action(action_json: str) -> str:
    """Execute one validated desktop action.

    Pass JSON such as {"action":"click","x":400,"y":250},
    {"action":"click_text","text":"Save","cells":[1,2]},
    {"action":"type","text":"hello"}, or
    {"action":"hotkey","keys":["ctrl","l"]}.

    For click_text, cells is an optional list of grid cell IDs from the
    latest screenshot. The operation is localized against a fresh screenshot.
    Only the documented action types are accepted; arbitrary shell/code
    execution is not exposed.
    """
    try:
        action: dict[str, Any] = json.loads(action_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"action_json must be valid JSON: {exc}") from exc

    if not isinstance(action, dict):
        raise ValueError("Action must be a JSON object")

    action_type = action.get("action")
    if action_type == "click_text":
        target = str(action.get("text", "")).strip()
        if not target:
            raise ValueError("click_text requires a non-empty text field")
        screenshot = take_screenshot()
        location = locate_target(
            image=screenshot,
            target=target,
            cells=action.get("cells", []),
            columns=GRID_COLUMNS,
            rows=GRID_ROWS,
        )
        resolved = {
            "action": "click",
            "x": int(location["x"]),
            "y": int(location["y"]),
        }
        execute_action(resolved)
        return json.dumps({
            "success": True,
            "executed": resolved,
            "target": target,
            "region": location.get("region"),
            "ocr": location.get("ocr"),
        })

    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Unsupported action {action_type!r}. Allowed: "
            f"{sorted(ALLOWED_ACTIONS)} plus click_text"
        )

    if action_type in {"click", "double_click"}:
        for field in ("x", "y"):
            if not isinstance(action.get(field), int):
                raise ValueError(f"{action_type} requires integer {field}")
    elif action_type == "type":
        if not isinstance(action.get("text"), str):
            raise ValueError("type requires a text string")
    elif action_type == "key":
        if not isinstance(action.get("key"), str):
            raise ValueError("key requires a key string")
    elif action_type == "hotkey":
        keys = action.get("keys")
        if not isinstance(keys, list) or not keys or not all(
            isinstance(key, str) for key in keys
        ):
            raise ValueError("hotkey requires a non-empty list of key names")
    elif action_type == "scroll":
        amount = action.get("scroll_amount", action.get("amount", 1))
        if not isinstance(amount, (int, float)) or abs(amount) > 20:
            raise ValueError("scroll amount must be numeric and between -20 and 20")
    elif action_type == "wait":
        seconds = action.get("seconds", 1)
        if not isinstance(seconds, (int, float)) or not 0 <= seconds <= 10:
            raise ValueError("wait seconds must be between 0 and 10")

    execute_action(action)
    return json.dumps({"success": True, "executed": action})


if __name__ == "__main__":
    # stdio is suitable for a local MCP client. A cloud-hosted ChatGPT
    # connection needs a reachable, authenticated remote MCP endpoint.
    mcp.run()
