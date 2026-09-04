import pyautogui


# One scroll unit corresponds approximately to one grid-cell height.
# Gemini should provide the number of grid-cell heights to scroll.
SCROLL_UNITS_PER_CELL = 5


def execute_action(action):

    action_type = action["action"]


    # =====================================================
    # CLICK
    # =====================================================

    if action_type == "click":

        x = action["x"]
        y = action["y"]

        print(
            f"Clicking at ({x}, {y})"
        )

        pyautogui.click(
            x,
            y,
        )

        return


    # =====================================================
    # DOUBLE CLICK
    # =====================================================

    if action_type == "double_click":

        x = action["x"]
        y = action["y"]

        print(
            f"Double-clicking at ({x}, {y})"
        )

        pyautogui.doubleClick(
            x,
            y,
        )

        return


    # =====================================================
    # TYPE
    # =====================================================

    if action_type == "type":

        text = action["text"]

        print(
            f"Typing: {text}"
        )

        pyautogui.write(
            text,
            interval=0.01,
        )

        return


    # =====================================================
    # KEY
    # =====================================================

    if action_type == "key":

        key = action["key"]

        print(
            f"Pressing key: {key}"
        )

        pyautogui.press(
            key
        )

        return


    # =====================================================
    # HOTKEY
    # =====================================================

    if action_type == "hotkey":

        keys = action["keys"]

        print(
            f"Pressing hotkey: {keys}"
        )

        pyautogui.hotkey(
            *keys
        )

        return


    # =====================================================
    # SCROLL
    # =====================================================

    if action_type == "scroll":

        x = action.get(
            "x"
        )

        y = action.get(
            "y"
        )

        # Gemini provides this value in grid-cell units.
        grid_amount = action.get(
            "scroll_amount",
            action.get(
                "amount",
                1,
            ),
        )

        # Convert grid-cell units into PyAutoGUI scroll units.
        amount = int(
            grid_amount * SCROLL_UNITS_PER_CELL
        )

        print(
            f"Scrolling at "
            f"({x}, {y}) "
            f"by {grid_amount} grid units "
            f"({amount} PyAutoGUI units)"
        )

        if (
            x is not None
            and y is not None
        ):

            pyautogui.moveTo(
                x,
                y,
            )

        pyautogui.scroll(
            amount
        )

        return


    # =====================================================
    # WAIT
    # =====================================================

    if action_type == "wait":

        import time

        seconds = action.get(
            "seconds",
            5,
        )

        print(
            f"Waiting {seconds} seconds..."
        )

        time.sleep(
            seconds
        )

        return


    # =====================================================
    # UNSUPPORTED
    # =====================================================

    raise ValueError(
        f"Unsupported action: {action_type}"
    )