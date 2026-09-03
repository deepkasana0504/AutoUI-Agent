from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
import pyautogui


# =========================================================
# SCREENSHOT
# =========================================================

def take_screenshot():
    """
    Take a screenshot and return it as a PIL Image.
    """

    return pyautogui.screenshot()


# =========================================================
# IMAGE TO BYTES
# =========================================================

def image_to_bytes(image):
    """
    Convert PIL image to PNG bytes.
    """

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


# =========================================================
# GRID
# =========================================================

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


# =========================================================
# COORDINATE CALIBRATION
# =========================================================

def get_coordinate_calibration(
    image,
):
    """
    Return basic screenshot coordinate information.

    Kept for compatibility with the rest of the project.
    """

    width, height = image.size

    return {
        "screen_width": width,
        "screen_height": height,
        "coordinate_origin": "top-left",
        "x_range": [
            0,
            width - 1,
        ],
        "y_range": [
            0,
            height - 1,
        ],
    }