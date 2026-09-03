import time
from pathlib import Path

from computer.screen import take_screenshot
from computer.ocr_locator import locate_target, preprocess_for_ocr
from agent.planner import get_next_action
from computer.executor import execute_action

from communication.events import (
    send_agent_status,
    send_agent_event,
    publish_action_status,
    publish_progress,
)


# =========================================================
# SETTINGS
# =========================================================

COLUMNS = 12
ROWS = 8

DEBUG_DIR = Path("debug")

DEBUG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# DEBUG IMAGE
# =========================================================

def save_debug_image(image, filename):

    path = DEBUG_DIR / filename

    image.save(path)

    print(
        f"Debug image saved: {path}"
    )

    return path


# =========================================================
# FRONTEND HELPERS
# =========================================================

def frontend_status(
    status,
    message=None,
    data=None,
):
    try:
        send_agent_status(
            status,
            message,
            data,
        )
    except Exception as e:
        print(
            f"Frontend status error: {e}"
        )


def frontend_event(
    event,
    data=None,
):
    try:
        send_agent_event(
            event,
            data,
        )
    except Exception as e:
        print(
            f"Frontend event error: {e}"
        )


# =========================================================
# RUN TASK
# =========================================================

def run_task(task):

    print(
        "\n========================================"
    )

    print(
        f"Received task:\n{task}"
    )

    print(
        "========================================"
    )

    frontend_status(
        "working",
        "Agent started working on the task.",
        {
            "task": task,
        },
    )

    frontend_event(
        "task_received",
        {
            "task": task,
        },
    )

    progress_history = []

    pending_action = None

    step = 0

    # =====================================================
    # MAIN LOOP
    # =====================================================

    while True:

        step += 1

        print(
            f"\n========== STEP {step} =========="
        )

        frontend_event(
            "step_started",
            {
                "step": step,
            },
        )

        frontend_status(
            "working",
            f"Working on step {step}.",
            {
                "step": step,
            },
        )

        # =================================================
        # SCREENSHOT
        # =================================================

        print(
            "\nTaking screenshot..."
        )

        screenshot = take_screenshot()

        print(
            f"Screenshot size: "
            f"{screenshot.size}"
        )

        save_debug_image(
            screenshot,
            f"step_{step:03d}_screenshot.png",
        )

        frontend_event(
            "screenshot_taken",
            {
                "step": step,
                "width": screenshot.width,
                "height": screenshot.height,
            },
        )

        # =================================================
        # PLANNER
        # =================================================

        try:

            action = get_next_action(
                task=task,
                image=screenshot,
                progress_history=progress_history,
                pending_action=pending_action,
            )

        except Exception as e:

            print(
                "\nPlanner error:"
            )

            print(
                str(e)
            )

            frontend_status(
                "error",
                "Planner failed.",
                {
                    "step": step,
                    "error": str(e),
                },
            )

            frontend_event(
                "planner_error",
                {
                    "step": step,
                    "error": str(e),
                },
            )

            break

        print(
            "\n========== GEMINI ACTION =========="
        )

        print(
            action
        )

        frontend_event(
            "action_planned",
            {
                "step": step,
                "action": action,
            },
        )

        # =================================================
        # COMPLETION
        # =================================================

        if action.get("action") in (
            "task_completed",
            "completed",
            "finish",
            "end",
        ):

            message = action.get(
                "message",
                "Task completed successfully.",
            )

            print(
                "\n========== TASK COMPLETED =========="
            )

            print(
                message
            )

            frontend_status(
                "completed",
                message,
                {
                    "step": step,
                    "task": task,
                    "result": message,
                },
            )

            frontend_event(
                "task_completed",
                {
                    "task": task,
                    "message": message,
                    "step": step,
                },
            )

            break

        # =================================================
        # PUBLISH VERIFICATION
        # =================================================

        previous_status = action.get(
            "previous_action_status"
        )

        previous_result = action.get(
            "previous_action_result"
        )

        if previous_status in (
            "passed",
            "failed",
            "not_executed",
        ):

            print(
                "\n========== VERIFICATION =========="
            )

            print(
                f"Status: {previous_status}"
            )

            print(
                f"Result: {previous_result}"
            )

            frontend_event(
                "verification",
                {
                    "step": step,
                    "status": previous_status,
                    "result": previous_result,
                },
            )

            if previous_status == "passed":

                frontend_status(
                    "working",
                    "Previous action verified.",
                    {
                        "step": step,
                        "verification": "passed",
                    },
                )

            elif previous_status == "failed":

                frontend_status(
                    "working",
                    "Previous action failed. Recovering.",
                    {
                        "step": step,
                        "verification": "failed",
                    },
                )

            elif previous_status == "not_executed":

                frontend_status(
                    "working",
                    "Previous action was not executed. Continuing.",
                    {
                        "step": step,
                        "verification": "not_executed",
                    },
                )

        # =================================================
        # TARGET LOCALIZATION
        # =================================================

        if action.get("action") == "click":

            target = action.get(
                "text"
            )

            if not target:

                target = action.get(
                    "target"
                )

            cells = action.get(
                "cells",
                [],
            )

            print(
                "\n========== TARGET =========="
            )

            print(
                f"Target: {action.get('target')}"
            )

            print(
                f"OCR text: {target}"
            )

            print(
                f"Cells: {cells}"
            )

            frontend_event(
                "target_identified",
                {
                    "step": step,
                    "target": action.get(
                        "target"
                    ),
                    "text": target,
                    "cells": cells,
                },
            )

            try:

                location = locate_target(
                    image=screenshot,
                    target=target,
                    cells=cells,
                    columns=COLUMNS,
                    rows=ROWS,
                )

            except Exception as e:

                print(
                    "\nOCR localization failed:"
                )

                print(
                    str(e)
                )

                frontend_event(
                    "ocr_failed",
                    {
                        "step": step,
                        "target": target,
                        "cells": cells,
                        "error": str(e),
                    },
                )

                publish_action_status(
                    "click",
                    "not_executed",
                    {
                        "target": action.get(
                            "target"
                        ),
                        "text": target,
                        "cells": cells,
                        "error": str(e),
                    },
                )

                progress_history.append({
                    "action": action,
                    "execution_status":
                        "not_executed",
                    "execution_result":
                        str(e),
                })

                pending_action = {
                    "action": action,
                    "status": "not_executed",
                    "result": str(e),
                }

                continue

            # =================================================
            # LOCATION FOUND
            # =================================================

            print(
                "\n========== TARGET LOCALIZATION =========="
            )

            print(
                f"Target: {target}"
            )

            print(
                f"Cells: {cells}"
            )

            print(
                f"Region: "
                f"{location['region']}"
            )

            print(
                f"OCR result: "
                f"{location['ocr']}"
            )

            print(
                f"Final click coordinate: "
                f"({location['x']}, "
                f"{location['y']})"
            )

            frontend_event(
                "target_located",
                {
                    "step": step,
                    "target": action.get(
                        "target"
                    ),
                    "text": target,
                    "cells": cells,
                    "region": location[
                        "region"
                    ],
                    "x": location["x"],
                    "y": location["y"],
                    "ocr": location["ocr"],
                },
            )

            # =================================================
            # SAVE ORIGINAL CROP
            # =================================================

            x1, y1, x2, y2 = (
                location["region"]
            )

            crop = screenshot.crop(
                (
                    x1,
                    y1,
                    x2,
                    y2,
                )
            )

            crop_path = save_debug_image(
                crop,
                f"step_{step:03d}_crop.png",
            )

            # =================================================
            # SAVE OCR IMAGE
            # =================================================

            ocr_image = preprocess_for_ocr(
                crop
            )

            ocr_path = save_debug_image(
                ocr_image,
                f"step_{step:03d}_ocr.png",
            )

            frontend_event(
                "debug_images",
                {
                    "step": step,
                    "crop": str(
                        crop_path
                    ),
                    "ocr": str(
                        ocr_path
                    ),
                },
            )

            # =================================================
            # ADD COORDINATES
            # =================================================

            action["x"] = location[
                "x"
            ]

            action["y"] = location[
                "y"
            ]

            action["ocr"] = location[
                "ocr"
            ]

            action["region"] = location[
                "region"
            ]

        # =================================================
        # NORMALIZE SCROLL
        # =================================================
        #
        # Gemini only decides UP or DOWN.
        # The executor expects a numeric amount.
        # Keep the amount fixed here.
        # =================================================

        if action.get("action") == "scroll":

            direction = str(
                action.get("direction", "")
            ).strip().lower()

            if direction == "up":

                action["amount"] = 5

            elif direction == "down":

                action["amount"] = -5

            else:

                execution_status = "error"

                execution_result = (
                    "Invalid scroll direction. "
                    "Expected 'up' or 'down'."
                )

                print(
                    "\nExecution error:"
                )

                print(
                    execution_result
                )

                frontend_status(
                    "error",
                    execution_result,
                    {
                        "step": step,
                        "action": action,
                    },
                )

                frontend_event(
                    "execution_error",
                    {
                        "step": step,
                        "action": action,
                        "error": execution_result,
                    },
                )

                progress_history.append({
                    "action": action,
                    "execution_status": execution_status,
                    "execution_result": execution_result,
                })

                pending_action = {
                    "action": action,
                    "execution_status": execution_status,
                    "result": execution_result,
                }

                continue

            print(
                f"Scroll direction: {direction}"
            )

            print(
                f"Fixed scroll amount: {action['amount']}"
            )

        # =================================================
        # EXECUTE
        # =================================================

        print(
            "\n========== EXECUTING =========="
        )

        print(
            action
        )

        frontend_event(
            "executing_action",
            {
                "step": step,
                "action": action,
            },
        )

        try:

            execute_action(
                action
            )

            execution_status = (
                "executed"
            )

            execution_result = (
                "Action executed successfully."
            )

            print(
                execution_result
            )

        except Exception as e:

            execution_status = (
                "error"
            )

            execution_result = str(e)

            print(
                "\nExecution error:"
            )

            print(
                execution_result
            )

        # =================================================
        # FRONTEND ACTION RESULT
        # =================================================

        publish_action_status(
            action.get(
                "action",
                "unknown",
            ),
            execution_status,
            {
                "target": action.get(
                    "target"
                ),
                "text": action.get(
                    "text"
                ),
                "x": action.get(
                    "x"
                ),
                "y": action.get(
                    "y"
                ),
                "cells": action.get(
                    "cells"
                ),
                "region": action.get(
                    "region"
                ),
                "result":
                    execution_result,
            },
        )

        frontend_event(
            "action_executed",
            {
                "step": step,
                "status": execution_status,
                "result": execution_result,
                "action": action,
            },
        )

        # =================================================
        # SAVE HISTORY
        # =================================================

        progress_history.append({
            "action": action,
            "execution_status":
                execution_status,
            "execution_result":
                execution_result,
        })

        pending_action = {
            "action": action,
            "status": execution_status,
            "result": execution_result,
        }

        # =================================================
        # ERROR
        # =================================================

        if execution_status == "error":

            frontend_status(
                "error",
                "Action execution failed.",
                {
                    "step": step,
                    "error": execution_result,
                },
            )

            frontend_event(
                "execution_error",
                {
                    "step": step,
                    "action": action,
                    "error": execution_result,
                },
            )

        else:

            frontend_status(
                "working",
                "Action executed. Verifying next screen state.",
                {
                    "step": step,
                },
            )

        # =================================================
        # SMALL PAUSE
        # =================================================

        time.sleep(1)


    # =====================================================
    # TASK RUNNER FINISHED
    # =====================================================

    print(
        "\nTask runner finished."
    )

    frontend_event(
        "runner_finished",
        {
            "task": task,
        },
    )