# autoUI

## Architecture

- main.py: application entry point
- agent/: planning, prompting, verification, task loop
- computer/: screenshot capture, coordinate conversion, execution
- communication/: WebSocket client and frontend events
- memory/: compact confirmed progress
- utils/: validation
- server.py: communication relay server

## Important coordinate behavior

Gemini receives a clean screenshot.

Gemini returns coordinates in screenshot coordinates.

Before execution:

real_x = model_x * (real_screen_width / screenshot_width)
real_y = model_y * (real_screen_height / screenshot_height)

No artificial calibration dots are used.

## Run

1. Create a .env file from .env.example.
2. Install requirements:
   pip install -r requirements.txt
3. Start server:
   python server.py
4. Start agent:
   python main.py
