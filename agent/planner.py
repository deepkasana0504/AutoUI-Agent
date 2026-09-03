import json
import re

from google import genai
from google.genai import types

from config import API_KEY, MODEL
from computer.screen import image_to_bytes, add_target_grid


# =========================================================
# GRID
# =========================================================

COLUMNS = 12
ROWS = 8


# =========================================================
# GEMINI
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
# PARSE JSON
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

    return json.loads(text)


# =========================================================
# GET NEXT ACTION
# =========================================================

def get_next_action(
    task,
    image,
    progress_history,
    pending_action,
):

    # =====================================================
    # PREVIOUS ACTION
    # =====================================================

    if pending_action is None:

        previous_status = "none"

        previous_result = (
            "No previous action."
        )

    else:

        status = pending_action.get(
            "execution_status",
            "executed",
        )

        if status == "not_executed":

            previous_status = "not_executed"

            previous_result = (
                "The previous action was not executed."
            )

        elif status == "error":

            previous_status = "failed"

            previous_result = (
                "The previous action failed."
            )

        else:

            previous_status = "passed"

            previous_result = (
                "The previous action was executed. "
                "Verify its result from the current screenshot."
            )


    # =====================================================
    # HISTORY
    # =====================================================

    if progress_history:

        history = json.dumps(
            progress_history[-10:],
            ensure_ascii=False,
            indent=2,
        )

    else:

        history = "No previous progress."


    # =====================================================
    # GRID
    # =====================================================

    grid_image = add_target_grid(
        image,
        columns=COLUMNS,
        rows=ROWS,
    )


    # =====================================================
    # PROMPT
    # =====================================================

    prompt = f"""
You control a computer using screenshots.

USER TASK:

{task}


=========================================================
PREVIOUS ACTION
=========================================================

{json.dumps(
    pending_action,
    ensure_ascii=False,
    indent=2,
) if pending_action else "None"}


PREVIOUS ACTION STATUS:

{previous_status}


PREVIOUS ACTION RESULT:

{previous_result}


=========================================================
RECENT HISTORY
=========================================================

{history}


=========================================================
GRID
=========================================================

The screenshot uses a {COLUMNS} × {ROWS} grid.

There are 96 cells.

Cells are numbered left-to-right, then top-to-bottom:

     1   2   3   4   5   6   7   8   9  10  11  12
    13  14  15  16  17  18  19  20  21  22  23  24
    25  26  27  28  29  30  31  32  33  34  35  36
    37  38  39  40  41  42  43  44  45  46  47  48
    49  50  51  52  53  54  55  56  57  58  59  60
    61  62  63  64  65  66  67  68  69  70  71  72
    73  74  75  76  77  78  79  80  81  82  83  84
    85  86  87  88  89  90  91  92  93  94  95  96

The red grid and numbers are visual guides only.


=========================================================
CRITICAL CELL SELECTION RULE
=========================================================

For a click or double_click target:

The selected cells MUST contain the COMPLETE visible
text that OCR will be asked to find.

This is the MOST IMPORTANT requirement.

The complete target text must be inside the selected
region.

Do NOT select a region that cuts off even part of the
target text.

For example, if the target text is:

    Launch instance

the selected cells must contain BOTH:

    Launch
    instance

completely.

It is OK if the selected region also contains:

- other buttons
- other text
- icons
- surrounding UI
- another nearby control

Extra content is acceptable.

Do NOT sacrifice complete target coverage just to make the
region smaller.


=========================================================
MULTIPLE MATCHES
=========================================================

If the same target text appears more than once:

Choose the occurrence that actually satisfies the user's
task.

Prefer the occurrence whose surrounding UI context matches
the requested action.

If possible, select a region containing the intended
occurrence while avoiding another occurrence of the SAME
target text.

If one occurrence is unique and another occurrence is
ambiguous, choose the unique intended occurrence.

Do NOT select a region containing multiple identical
candidate texts when another region can uniquely identify
the intended target.


=========================================================
REGION SIZE
=========================================================

After ensuring the COMPLETE target text is inside the
region, keep the region reasonably small.

Priority:

1. COMPLETE target text must be inside the region.
2. Select the correct occurrence.
3. Avoid another identical target when reasonably possible.
4. Keep the region reasonably small.

Complete coverage is more important than minimal size.


=========================================================
OCR TEXT
=========================================================

For click actions:

"target" describes the UI element.

"text" must contain the visible text that OCR should search.

Example:

"target": "Migrate a server button"

"text": "Migrate a server"

Do not add words such as "button" unless they are actually
visible in the interface.


=========================================================
VERIFICATION
=========================================================

The CURRENT screenshot is the source of truth.

If the previous action was executed, inspect the screenshot
and determine whether the intended result actually occurred.

If it occurred:

"previous_action_status": "passed"

Then immediately give the next action.

If it did not occur:

"previous_action_status": "failed"

Choose a recovery action.

If the previous action was not physically executed:

"previous_action_status": "not_executed"


=========================================================
AVAILABLE ACTIONS
=========================================================

click
double_click
type
key
hotkey
scroll
wait
ask_user
end


=========================================================
CLICK FORMAT
=========================================================

For click actions ALWAYS return:

"target"
"text"
"cells"


Example:

{{
    "previous_action_status": "none",
    "previous_action_result": "No previous action.",
    "action": "click",
    "target": "Sign in button",
    "text": "Sign in",
    "cells": [43, 44],
    "reason": "The Sign in button is the intended control.",
    "expected_result": "The sign-in action begins."
}}


=========================================================
SCROLL FORMAT
=========================================================

For a scroll action, provide ONLY the direction.

Do NOT provide a scroll amount.

The only valid values are:

"direction": "up"

or

"direction": "down"

Example:

{{
    "action": "scroll",
    "direction": "down",
    "reason": "Scroll down to reveal the next part of the page.",
    "expected_result": "More content below becomes visible."
}}

The runner supplies a fixed scroll amount automatically.

=========================================================
TYPE FORMAT
=========================================================

{{
    "previous_action_status": "passed",
    "previous_action_result": "The search field is focused.",
    "action": "type",
    "text": "anshuman kasana",
    "reason": "Enter the requested contact name.",
    "expected_result": "The search results show the contact."
}}


=========================================================
KEY FORMAT
=========================================================

{{
    "previous_action_status": "passed",
    "previous_action_result": "The contact is selected.",
    "action": "key",
    "key": "enter",
    "reason": "Open the selected contact.",
    "expected_result": "The contact chat opens."
}}


=========================================================
END FORMAT
=========================================================

When the task is completely finished:

{{
    "previous_action_status": "passed",
    "previous_action_result": "The requested task is complete.",
    "action": "end",
    "message": "Task completed successfully."
}}


=========================================================
FINAL REQUIREMENTS
=========================================================

Return ONLY valid JSON.

Do NOT return markdown.

Do NOT return pixel coordinates.

For click and double_click:

- Always provide the OCR text.
- Always provide cells.
- The cells MUST contain the COMPLETE OCR text.
- Extra surrounding content is acceptable.
- Prefer a region where the intended target text is unique.

For scroll actions:
- Always provide "direction".
- Use only "up" or "down".
- Never provide "amount".
- Never invent a scroll magnitude.
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
                data=image_to_bytes(
                    grid_image
                ),
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
        "\nGemini raw response:"
    )

    print(
        text
    )

    return parse_model_json(
        text
    )