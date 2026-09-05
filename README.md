# AutoUI

AutoUI is an AI-powered computer-use agent that can perform tasks directly on a graphical user interface.

Instead of relying on fixed UI scripts or hardcoded selectors, AutoUI looks at the current screen, understands what is visible, and decides what action should be taken next.

## Why AutoUI?

Traditional UI automation scripts can be fragile.

A small change in a website's DOM, layout, element position, text, or UI structure can cause a hardcoded script to fail.

For example, a script may expect a button at a particular location or depend on a specific DOM element. If the website changes slightly, the script may no longer find or interact with it.

AutoUI takes a different approach:

**Look at the screen → Understand it → Decide an action → Execute it → Look again**

This allows the agent to work with interfaces based on what is actually visible rather than depending entirely on the underlying page structure.

## What AutoUI Does

AutoUI can:

- Understand the current UI from screenshots
- Decide what action should be performed next
- Click UI elements
- Type text
- Press keys and hotkeys
- Scroll through pages
- Wait for pages or UI elements to load
- Use OCR to locate text on the screen
- Use grid-based localization to help the AI identify where a target is
- Re-evaluate the screen after every action
- Handle ambiguous UI elements by changing the viewport
- Ask the user for clarification when an important choice cannot safely be determined

For example, if a user asks:

> "Buy 1 Infosys share"

and the interface requires choices such as Intraday/Regular or Market/Limit, AutoUI can identify those choices and ask the user instead of blindly selecting one.

## Architecture

- `main.py` — application entry point
- `agent/` — planning, prompting, verification, and task loop
- `computer/` — screenshot capture, coordinate conversion, and execution
- `communication/` — WebSocket client and frontend events
- `memory/` — compact confirmed progress
- `utils/` — validation
- `server.py` — communication relay server

## How It Works

The agent follows a continuous visual interaction loop:

1. Capture a screenshot of the current screen.
2. Send the screenshot and task context to Gemini.
3. Gemini determines the next action.
4. The action is returned in a structured format.
5. OCR/grid localization is used when necessary to locate the target.
6. The executor performs the action.
7. A new screenshot is captured.
8. Gemini evaluates the new screen and decides the next action.
9. The process continues until the task is completed.

This means the agent does not need to know the entire UI workflow beforehand.

## Grid-Based UI Localization

For difficult or ambiguous UI elements, the screenshot can be divided into a grid.

Gemini identifies the grid cells containing the target, for example:

```text
Target: Launch instance
Cells: [75, 76, 77]
