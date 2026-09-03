import json
import re

from google import genai
from google.genai import types

from config import API_KEY, MODEL
from computer.screen import image_to_bytes


COLUMNS = 6
ROWS = 4


# =========================================================
# GEMINI CLIENT
# =========================================================

if not API_KEY:
    raise RuntimeError(
        "No Gemini API key found. "
        "Add GEMINI_API_KEY2 or GEMINI_API_KEY to .env."
    )


client = genai.Client(
    api_key=API_KEY
)


# =========================================================
# PARSE GEMINI JSON
# =========================================================

def parse_model_json(text):

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return json.loads(
        text
    )


# =========================================================
# IDENTIFY TARGET REGION
# =========================================================

def identify_target_region(
    task,
    image,
    rows=ROWS,
    columns=COLUMNS,
):

    prompt = f"""
You are locating a UI target visually.

USER TASK:

{task}


=========================================================
GRID
=========================================================

The screenshot has a {columns} × {rows} grid.

The cells are numbered left to right,
then top to bottom:

    1    2    3    4    5    6
    7    8    9   10   11   12
   13   14   15   16   17   18
   19   20   21   22   23   24


The red lines and numbers are ONLY visual reference
guides.

They are NOT part of the actual interface.


=========================================================
TARGET
=========================================================

Identify the EXACT UI element required by the task.


=========================================================
CELL SELECTION
=========================================================

Return the SMALLEST SET OF GRID CELLS that contains the
COMPLETE target.

The returned cells MUST contain the complete visible
target.

A cell must be included if ANY visible part of the target
lies inside that cell.

Do NOT return a cell merely because it is close to the
target.

Do NOT omit a cell containing any part of the target.

For every visible part of the target, make sure its cell
is included.

For every returned cell, make sure some part of the actual
target lies inside that cell.

If the target crosses a grid boundary, return EVERY cell
needed to contain the complete target.

Do NOT return pixel coordinates.


=========================================================
CONTEXT
=========================================================

Do NOT simply choose the first matching element.

Consider the surrounding UI context.

If multiple similar elements exist, distinguish the
element that actually satisfies the user's task.


=========================================================
TEXT PREFERENCE
=========================================================

Prefer a clearly visible TEXT-LABELLED interactive element
when an equivalent text-based element is available.

For example:

- icon-only control
- text-labelled control doing the same thing

Prefer the text-labelled control.

This is a preference, not an absolute rule.

Do NOT select ordinary text merely because it contains
matching words.

The selected text must belong to the requested interactive
element.


=========================================================
OCR TEXT
=========================================================

Also return the exact visible text that OCR should search
for.

"target" describes the UI element semantically.

"text" contains ONLY the visible text that OCR should
search for.

Do NOT include words such as:

button
field
input
link
box

unless those words are actually visible.

Example:

Target:
Sign in button

Text:
Sign in


=========================================================
RESPONSE FORMAT
=========================================================

Return ONLY valid JSON.

Use exactly:

{{
    "target": "precise description of the requested UI element",
    "text": "exact visible text that OCR should search for",
    "cells": [14, 15],
    "reason": "Briefly explain why these cells contain the complete target."
}}
"""


    # =====================================================
    # GEMINI REQUEST
    # =====================================================

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_text(
                text=prompt
            ),
            types.Part.from_bytes(
                data=image_to_bytes(image),
                mime_type="image/png",
            ),
        ],
    )


    # =====================================================
    # RESPONSE
    # =====================================================

    text = (
        response.text or ""
    ).strip()


    print(
        "\n========== TARGET REGION =========="
    )

    print( 
        text
    )


    return parse_model_json(
        text
    )