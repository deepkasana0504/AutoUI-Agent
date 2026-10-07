import os

from mcp.server.fastmcp import FastMCP, Image

from computer.screenshot import take_screenshot

from dotenv import load_dotenv
from ocr_client import locate_target
import pyautogui


mcp = FastMCP(
    "AutoUI-Agent",
    streamable_http_path="/",
    host="0.0.0.0",
)


@mcp.tool()
async def get_screenshot() -> Image:
    """Capture the current screen with a numbered grid for visual grounding and to verify
    the current screen state and to ensure if action executed successfully."""

    image_bytes = take_screenshot()

    return Image(
        data=image_bytes,
        format="png",
    )


@mcp.tool()
async def target_location(
    text: str,
    cells: list[int]
) -> dict:
    """Find the given text on the screen and return its bounding box coordinates"""

    result = await locate_target(
        text,
        cells
    )

    

    return {
        "x": result["x"],
        "y": result["y"],
        "bbox": result["bbox"],
        "confidence": result["confidence"],
        "cell": result["cell"],
    }
    
@mcp.tool()
async def execute_click(x: int, y: int) -> dict:
    """Click the mouse at the specified screen coordinates."""

    pyautogui.click(x, y)

    return {
        "success": True,
        "action": "click",
        "x": x,
        "y": y,
    }

@mcp.tool()
async def execute_double_click(x: int, y: int) -> dict:
    """Double-click the mouse at the specified screen coordinates."""

    pyautogui.doubleClick(x, y)

    return {
        "success": True,
        "action": "double_click",
        "x": x,
        "y": y,
    }
    
@mcp.tool()
async def execute_type(txt: str) -> dict:
    """Type the specified text into the currently focused application."""

    pyautogui.write(
        txt,
        interval=0.01,
    )

    return {
        "success": True,
        "action": "type",
        "text": txt,
    }
    
@mcp.tool()
async def execute_key(key: str) -> dict:
    """Press a keyboard key."""

    pyautogui.press(key)

    return {
        "success": True,
        "action": "key",
        "key": key,
    }
    
@mcp.tool()
async def execute_hotkey(
    keys: list[str],
) -> dict:
    """Press a keyboard shortcut."""

    pyautogui.hotkey(*keys)

    return {
        "success": True,
        "action": "hotkey",
        "keys": keys,
    }
    
@mcp.tool()
async def execute_scroll(amount: int) -> dict:
    """Scroll the mouse wheel by the specified amount. Positive scrolls up, negative scrolls down."""

    pyautogui.scroll(amount)

    return {
        "success": True,
        "action": "scroll",
        "amount": amount,
    }  
    

if __name__ == "__main__":
    import uvicorn

    app = mcp.streamable_http_app()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )