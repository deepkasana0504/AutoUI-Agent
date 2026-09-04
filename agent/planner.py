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
# NORMALIZE ACTION
# =========================================================

def normalize_action(action):

    if not isinstance(action, dict):
        raise ValueError(
            "Gemini did not return a JSON object."
        )

    action_type = action.get("action")

    # -----------------------------------------------------
    # WAIT AFTER ACTION
    # -----------------------------------------------------

    if action_type in {
        "click",
        "double_click",
        "type",
        "key",
        "hotkey",
        "scroll",
    }:

        wait_value = action.get(
            "wait_after_action",
            1.0,
        )

        try:
            wait_value = float(
                wait_value
            )
        except (TypeError, ValueError):
            wait_value = 1.0

        action["wait_after_action"] = max(
            0.1,
            min(
                wait_value,
                10.0,
            ),
        )

    # -----------------------------------------------------
    # SCROLL
    # -----------------------------------------------------

    if action_type == "scroll":

        direction = action.get(
            "direction",
            "up",
        ).lower()

        if direction not in {
            "up",
            "down",
        }:
            direction = "up"

        action["direction"] = direction

        amount = action.get(
            "scroll_amount",
            action.get(
                "amount",
                1,
            ),
        )

        try:
            amount = float(
                amount
            )
        except (TypeError, ValueError):
            amount = 1.0

        action["scroll_amount"] = max(
            1.0,
            min(
                amount,
                16.0,
            ),
        )

    # -----------------------------------------------------
    # WAIT
    # -----------------------------------------------------

    elif action_type == "wait":

        seconds = action.get(
            "seconds",
            2,
        )

        try:
            seconds = float(
                seconds
            )
        except (TypeError, ValueError):
            seconds = 2.0

        action["seconds"] = max(
            0.1,
            min(
                seconds,
                10.0,
            ),
        )

    return action


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
            pending_action.get(
                "status",
                "executed",
            ),
        )

        if status == "not_executed":

            previous_status = "not_executed"

            previous_result = (
                pending_action.get(
                    "result",
                    "The previous action was not executed.",
                )
            )

        elif status == "error":

            previous_status = "failed"

            previous_result = (
                pending_action.get(
                    "result",
                    "The previous action failed.",
                )
            )

        else:

            previous_status = "passed"

            previous_result = (
                pending_action.get(
                    "result",
                    "The previous action was executed. "
                    "Verify its result from the current screenshot.",
                )
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

        history = (
            "No previous progress."
        )


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

Your job is to complete the user's task by choosing the
next computer action.

USER TASK:

{task}


=========================================================
CURRENT SCREEN
=========================================================

The screenshot attached to this request is the CURRENT screen.

The CURRENT screenshot is always the source of truth.

Choose exactly ONE next action.


=========================================================
PREVIOUS ACTION
=========================================================

{json.dumps(
    pending_action,
    ensure_ascii=False,
    indent=2
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

IMPORTANT:

The grid numbers in your response refer to the CURRENT
screenshot.

If you scroll, the page changes.

Therefore, after every scroll action, you MUST inspect
the NEW screenshot on the next planning step and return
the NEW grid cells corresponding to the target's NEW
position.

Never reuse old cell numbers after scrolling.


=========================================================
CRITICAL USER CLARIFICATION RULE
=========================================================

Before performing an action, inspect the CURRENT SCREEN
for decisions that the user has not specified.

If the task requires the user to choose between multiple
meaningful options, DO NOT GUESS.

Instead use:

    "action": "ask_user"

Ask the user for the missing choices BEFORE continuing.

Examples of choices that may require clarification:

- order type
- intraday vs regular
- market vs limit
- quantity
- price
- account or environment
- region
- instance type
- operating system
- security settings
- alert/alarm settings
- optional configuration that materially changes the result
- any other important visible choice

IMPORTANT:

Ask about ALL relevant unresolved choices that are visible
or clearly required on the CURRENT SCREEN in ONE question.

Do NOT ask one question at a time if several decisions can
be determined together.

Do NOT ask about irrelevant UI options.

Do NOT invent choices that are not visible or required.

Do NOT assume the user's preferred option.

The user may provide several answers in one response.

Example:

User task:

    Buy 1 Infosys share.

Current screen shows:

    Intraday
    Regular
    Market
    Limit

and an option to create an alert.

Instead of selecting an option yourself, return:

{{
    "action": "ask_user",
    "question": "Before I continue, please specify: Intraday or Regular, Market or Limit, and whether you want a price alert. If you want an alert, tell me the price.",
    "reason": "The current screen contains multiple meaningful choices that were not specified in the user's request."
}}

After the user answers, continue the task using those
answers.

IMPORTANT:

If the user's original request already specifies a choice,
DO NOT ask for that choice again.

For example:

    "Buy 1 Infosys share using a Regular Market order."

Do not ask again about:

    Regular
    Market
    quantity 1

Only ask for other unresolved choices that materially
matter and are visible.


=========================================================
FINANCIAL / DESTRUCTIVE ACTIONS
=========================================================

For actions that can create financial, destructive, or
otherwise consequential changes, never silently guess
important parameters.

If the user has not specified an important parameter
required by the visible interface, use ask_user first.

Examples:

    Buy / sell order
    Payment
    Transfer
    Delete
    Submit
    Launch paid resources

Do not execute the consequential action until the required
choices have been clarified.


=========================================================
TARGET AMBIGUITY RULE
=========================================================

If the target text appears more than once on the visible
screen, DO NOT CLICK yet.

First determine which occurrence is relevant.

Example:

    Launch instance

might appear once as a page heading and once as an actual
button.

If both are visible, OCR text alone is NOT sufficient to
choose between them.

If two occurrences remain genuinely plausible:

    SCROLL FIRST.

Never resolve genuine ambiguity by guessing.


=========================================================
HOW TO RESOLVE AMBIGUITY
=========================================================

When duplicate target text is visible:

1. Identify the intended occurrence using surrounding UI
   context.

2. Identify the unwanted competing occurrence.

3. Determine whether scrolling can separate them.

4. Prefer SCROLLING UP FIRST when it can reasonably move
   the unwanted occurrence out of the viewport while
   keeping the intended target visible.

5. If UP cannot resolve the ambiguity, use DOWN.

6. If DOWN was attempted and did not resolve the ambiguity,
   try UP.

7. Never click an ambiguous target merely because OCR found
   the text.

Always consider both directions.

The goal is:

    ambiguous target
          ↓
    change viewport
          ↓
    target becomes unique


=========================================================
SCROLL DISTANCE
=========================================================

For every scroll action ALWAYS provide:

    "direction"
    "scroll_amount"

"scroll_amount" is measured in approximately GRID-CELL
HEIGHTS.

Use the visible grid to estimate the required movement.

Do NOT automatically use 1.

Do NOT repeatedly make tiny scrolls when a larger movement
is clearly required.

Estimate the vertical distance between the unwanted
occurrence and the viewport edge.

Choose enough grid-cell heights so that the unwanted
occurrence is actually removed from the visible viewport
or the two occurrences become clearly distinguishable.

Examples:

    scroll_amount: 2

means approximately two grid-cell heights.

    scroll_amount: 5

means approximately five grid-cell heights.

    scroll_amount: 8

means approximately one full screen height.

The value MUST be based on the geometry visible in the
CURRENT screenshot.

Prefer a meaningful scroll large enough to actually change
the relevant viewport.

When ambiguity can reasonably be solved in either
direction:

    TRY UP FIRST.

If UP cannot solve it:

    TRY DOWN.

If DOWN cannot solve it:

    TRY UP.

Do not keep repeating the same ineffective direction.


=========================================================
AFTER SCROLLING
=========================================================

A scroll changes the screenshot.

Therefore:

CURRENT SCREENSHOT
        ↓
Gemini chooses scroll
        ↓
executor scrolls
        ↓
NEW SCREENSHOT
        ↓
Gemini reassesses everything
        ↓
NEW target cells
        ↓
click only when unique

After scrolling, NEVER assume the previous cells remain
correct.

The target may have moved to completely different grid
cells.

The next action MUST be based on the NEW screenshot.


=========================================================
CRITICAL CELL SELECTION RULE
=========================================================

For click or double_click:

The selected cells MUST contain the COMPLETE visible text
that OCR will search.

For example, if the target text is:

    Launch instance

the selected cells must contain BOTH:

    Launch
    instance

completely.

Extra surrounding UI is acceptable.

Do NOT select cells that cut off part of the target text.

Priority:

1. Complete target text coverage.
2. Correct target occurrence.
3. Avoid another identical target when reasonably possible.
4. Keep the region reasonably small.


=========================================================
OCR TEXT
=========================================================

For click actions:

"target" describes the UI element.

"text" must contain the visible text that OCR should search.

Do not add words such as "button" unless they are actually
visible in the interface.


=========================================================
WAITING AND LOADING
=========================================================

The computer is asynchronous.

Clicks, navigation, menus, dialogs and network requests can
take time.

Every computer action MUST contain:

    "wait_after_action"

Use:

    0.5 - 1.0 seconds

for normal UI interactions.

Use:

    1.0 - 2.0 seconds

for normal navigation.

Use:

    2.0 - 5.0 seconds

for slow pages, AWS navigation, dialogs, network requests,
large UI transitions, and form submissions.

Do NOT automatically use huge delays.

Estimate the wait from the CURRENT SCREEN, the action, and
the expected result.


=========================================================
EXPLICIT WAIT
=========================================================

If the CURRENT screenshot shows that the interface is still
loading or transitioning, use:

    "action": "wait"

Examples:

- spinner
- skeleton loading
- blank dynamic areas
- partially rendered controls
- loading indicators
- page transition

Do NOT declare a previous click failed merely because the
new page has not finished loading.

Wait and inspect again.

Only declare navigation failed when the screenshot gives
sufficient evidence that the expected transition did not
happen.


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
    "wait_after_action": 1.0,
    "reason": "The Sign in button is uniquely identifiable.",
    "expected_result": "The sign-in action begins."
}}


=========================================================
SCROLL FORMAT
=========================================================

For scroll actions ALWAYS return:

"action"
"direction"
"scroll_amount"

Direction must be:

    "up"

or:

    "down"

scroll_amount must be a positive number representing
approximately how many grid-cell heights to scroll.

Example:

{{
    "action": "scroll",
    "direction": "up",
    "scroll_amount": 6,
    "wait_after_action": 1.0,
    "reason": "The competing occurrence can be moved out of the viewport by scrolling upward.",
    "expected_result": "The intended target becomes uniquely identifiable."
}}


=========================================================
WAIT FORMAT
=========================================================

Example:

{{
    "action": "wait",
    "seconds": 3,
    "reason": "The previous navigation triggered loading and the page is still rendering.",
    "expected_result": "The page finishes rendering."
}}


=========================================================
ASK USER FORMAT
=========================================================

When clarification is required, return:

{{
    "action": "ask_user",
    "question": "Your complete question containing all relevant unresolved choices.",
    "reason": "Explain why these choices cannot safely be assumed."
}}

The question should be concise.

Ask ALL relevant unresolved choices together.

Do not execute another computer action before receiving
the user's answer.


=========================================================
TYPE FORMAT
=========================================================

Example:

{{
    "previous_action_status": "passed",
    "previous_action_result": "The search field is focused.",
    "action": "type",
    "text": "Infosys",
    "wait_after_action": 0.5,
    "reason": "Enter the requested company name.",
    "expected_result": "Search results for Infosys appear."
}}


=========================================================
KEY FORMAT
=========================================================

Example:

{{
    "previous_action_status": "passed",
    "previous_action_result": "The required item is selected.",
    "action": "key",
    "key": "enter",
    "wait_after_action": 1.0,
    "reason": "Confirm the selected item.",
    "expected_result": "The selected item opens."
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

- Always provide OCR text.
- Always provide cells.
- Cells MUST contain the COMPLETE OCR text.
- Extra surrounding content is acceptable.
- Prefer a region where the intended target is unique.
- Never click when identical target occurrences remain
  genuinely ambiguous.
- After scrolling, calculate cells again from the NEW
  screenshot.

For scroll:

- Always provide direction.
- Direction must be "up" or "down".
- Always provide scroll_amount.
- scroll_amount is measured in approximate grid-cell heights.
- Base scroll_amount on the visible geometry.
- Do NOT default to tiny scrolls.
- Prefer UP first when both directions could reasonably
  resolve ambiguity.
- DOWN is valid when clearly better.
- If one direction is ineffective, try the opposite.

For loading:

- Use wait_after_action.
- Use longer waits for navigation and heavy pages.
- Use the wait action when the current screenshot visibly
  shows loading.
- Do not mistake temporary loading for action failure.

For user clarification:

- Use ask_user when important choices are missing.
- Ask all relevant choices visible on the current screen in
  one question.
- Never guess an important user choice.
- Do not ask again for choices already specified by the user.
- After receiving the user's answer, use it for subsequent
  actions.

The CURRENT screenshot is always the source of truth.
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

    action = parse_model_json(
        text
    )

    return normalize_action(
        action
    )