from io import BytesIO

import pyautogui
from PIL import ImageDraw, ImageFont


current_screenshot = None

def add_target_grid(
    image,
    columns=12,
    rows=8,
):
    """
    Add a numbered grid to a copy of the image.

    IMPORTANT:
    This image is ONLY for Gemini's visual reference.

    OCR and clicking always use the ORIGINAL screenshot.
    """

    grid_image = image.copy()

    draw = ImageDraw.Draw(
        grid_image
    )

    width, height = image.size

    cell_width = width / columns
    cell_height = height / rows

    # -----------------------------------------------------
    # FONT
    # -----------------------------------------------------

    try:

        font = ImageFont.truetype(
            "arial.ttf",
            16,
        )

    except Exception:

        font = ImageFont.load_default()


    # -----------------------------------------------------
    # GRID
    # -----------------------------------------------------

    cell_number = 1

    for row in range(rows):

        for column in range(columns):

            x1 = int(
                column * cell_width
            )

            y1 = int(
                row * cell_height
            )

            x2 = int(
                (column + 1)
                * cell_width
            )

            y2 = int(
                (row + 1)
                * cell_height
            )

            # ---------------------------------------------
            # GRID LINE
            # ---------------------------------------------

            draw.rectangle(
                (
                    x1,
                    y1,
                    x2,
                    y2,
                ),
                outline="red",
                width=2,
            )

            # ---------------------------------------------
            # CELL NUMBER
            # ---------------------------------------------

            label = str(
                cell_number
            )

            # Small white background behind number
            bbox = draw.textbbox(
                (0, 0),
                label,
                font=font,
            )

            text_width = (
                bbox[2] - bbox[0]
            )

            text_height = (
                bbox[3] - bbox[1]
            )

            padding = 3

            label_x = (
                x1 + 4
            )

            label_y = (
                y1 + 4
            )

            draw.rectangle(
                (
                    label_x - padding,
                    label_y - padding,
                    label_x
                    + text_width
                    + padding,
                    label_y
                    + text_height
                    + padding,
                ),
                fill="white",
            )

            draw.text(
                (
                    label_x,
                    label_y,
                ),
                label,
                fill="red",
                font=font,
            )

            cell_number += 1


    return grid_image


   

def take_screenshot():
    global current_screenshot
    current_screenshot = pyautogui.screenshot()

    grid_image = add_target_grid(current_screenshot)

    buffer = BytesIO()
    grid_image.save(buffer, format="PNG")

    return buffer.getvalue()