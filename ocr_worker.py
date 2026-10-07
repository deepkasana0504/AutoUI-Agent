import sys
import json
import base64
import re
from io import BytesIO
from difflib import SequenceMatcher

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR


# ============================================================
# SETTINGS
# ============================================================

COLUMNS = 12
ROWS = 8

OCR_SCALE = 3

FUZZY_MATCH_THRESHOLD = 0.80


# ============================================================
# INITIALIZE PADDLEOCR
# ============================================================

print(
    "Initializing PaddleOCR...",
    file=sys.stderr,
    flush=True
)

ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
)

print(
    "PaddleOCR initialized.",
    file=sys.stderr,
    flush=True
)


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):
    """
    Normalize OCR text.

    Example:

        "3 Configuration"
        -> "3 configuration"

        "Configuration"
        -> "configuration"
    """

    if text is None:
        return ""

    text = str(text).strip().lower()

    return "".join(
        character
        for character in text
        if character.isalnum() or character.isspace()
    )


def compact_text(text):
    """
    Remove spaces so that:

        "Configuration"
        "Config uration"

    can still be compared.
    """

    return re.sub(
        r"\s+",
        "",
        normalize_text(text)
    )


def word_similarity(a, b):
    """
    Fuzzy similarity between two strings.
    """

    a = compact_text(a)
    b = compact_text(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# ============================================================
# PREPROCESS IMAGE
# ============================================================

def preprocess_for_ocr(image):
    """
    Same basic strategy as the old Tesseract implementation:

        grayscale
        +
        3x upscale
    """

    
    rgb = image.convert("RGB")
    
    scaled = rgb.resize(
        (
            rgb.width * OCR_SCALE,
            rgb.height * OCR_SCALE,
        ),
        Image.Resampling.LANCZOS,
    )

    

    return scaled


# ============================================================
# CELL BOUNDS
# ============================================================

def get_cell_bounds(
    width,
    height,
    cell
):
    """
    Convert 1-based grid cell number to screen coordinates.

    12 x 8 grid:

        1   2   3 ... 12
        13  14  15 ... 24
        ...
        49  50  51 ... 60
        ...
        85  86  87 ... 96
    """

    if cell < 1 or cell > COLUMNS * ROWS:
        raise ValueError(
            f"Invalid grid cell: {cell}"
        )

    index = cell - 1

    row = index // COLUMNS
    column = index % COLUMNS

    cell_width = width / COLUMNS
    cell_height = height / ROWS

    x1 = int(column * cell_width)
    y1 = int(row * cell_height)

    x2 = int((column + 1) * cell_width)
    y2 = int((row + 1) * cell_height)

    return x1, y1, x2, y2


# ============================================================
# GET PADDLE OCR VALUES
# ============================================================

def get_result_value(
    result,
    key,
    default=None
):

    try:
        if hasattr(result, "get"):
            value = result.get(
                key,
                default
            )

            if value is not None:
                return value
    except Exception:
        pass

    try:
        return result[key]
    except Exception:
        pass

    try:
        return getattr(
            result,
            key,
            default
        )
    except Exception:
        return default


# ============================================================
# PADDLE OCR
# ============================================================

def run_paddle_ocr(image):
    """
    Run PaddleOCR and convert its output into
    word/segment records similar to Tesseract image_to_data().
    """

    image_np = np.array(image)

    results = ocr.predict(
        image_np
    )

    words = []

    for result in results:

        texts = get_result_value(
            result,
            "rec_texts",
            []
        )

        scores = get_result_value(
            result,
            "rec_scores",
            []
        )

        boxes = get_result_value(
            result,
            "rec_boxes",
            []
        )

        if texts is None:
            texts = []

        if scores is None:
            scores = []

        if boxes is None:
            boxes = []

        for text, score, box in zip(
            texts,
            scores,
            boxes
        ):

            text = str(text).strip()

            if not text:
                continue

            try:
                score = float(score)
            except Exception:
                score = 0.0

            box = np.asarray(
                box
            ).flatten()

            if len(box) < 4:
                continue

            x1 = int(box[0])
            y1 = int(box[1])
            x2 = int(box[2])
            y2 = int(box[3])

            words.append({
                "text": text,
                "normalized": normalize_text(text),

                "x": x1,
                "y": y1,

                "width": x2 - x1,
                "height": y2 - y1,

                "confidence": max(
                    0.0,
                    min(
                        1.0,
                        score
                    )
                ),
            })

    return words


# ============================================================
# FIND TARGET INSIDE OCR DETECTION
# ============================================================

def find_target_inside_detection(
    detection,
    target
):
    """
    PaddleOCR sometimes returns:

        "3 Configuration"

    as one detection.

    We need to find the bounding box of:

        "Configuration"

    inside that larger detection.

    This is the important difference from the
    previous implementation.
    """

    detected_text = detection["text"]

    target_normalized = compact_text(
        target
    )

    detected_normalized = compact_text(
        detected_text
    )

    if not target_normalized:
        return None

    # --------------------------------------------------------
    # Exact substring
    # --------------------------------------------------------

    position = detected_normalized.find(
        target_normalized
    )

    if position >= 0:

        total_chars = len(
            detected_normalized
        )

        target_chars = len(
            target_normalized
        )

        detected_width = detection["width"]

        # Approximate character width.
        char_width = (
            detected_width
            / max(total_chars, 1)
        )

        target_x = (
            detection["x"]
            + position * char_width
        )

        target_width = (
            target_chars * char_width
        )

        return {
            "x": int(target_x),
            "y": detection["y"],
            "width": int(target_width),
            "height": detection["height"],
            "confidence": detection["confidence"],
            "text": detected_text,
        }

    # --------------------------------------------------------
    # Whole detection fuzzy match
    # --------------------------------------------------------

    similarity = word_similarity(
        target,
        detected_text
    )

    if similarity >= FUZZY_MATCH_THRESHOLD:

        return {
            "x": detection["x"],
            "y": detection["y"],
            "width": detection["width"],
            "height": detection["height"],
            "confidence": detection["confidence"],
            "text": detected_text,
        }

    return None


# ============================================================
# FIND TEXT
# ============================================================

def find_text(
    image,
    target
):
    """
    Find target using PaddleOCR.

    Designed to behave similarly to the old
    Tesseract find_text().
    """

    processed = preprocess_for_ocr(
        image
    )

    words = run_paddle_ocr(
        processed
    )

    print(
        f"[OCR] Detected {len(words)} segments",
        file=sys.stderr,
        flush=True
    )

    matches = []

    for word in words:

        print(
            f"[OCR] Detected: "
            f"{word['text']!r} "
            f"confidence={word['confidence']:.3f}",
            file=sys.stderr,
            flush=True
        )

        result = find_target_inside_detection(
            word,
            target
        )

        if result is None:
            continue

        similarity = word_similarity(
            target,
            word["text"]
        )

        score = (
            similarity * 0.65
            +
            word["confidence"] * 0.35
        )

        if score < FUZZY_MATCH_THRESHOLD:
            continue

        result["match_score"] = score
        result["text_similarity"] = similarity

        matches.append(
            result
        )

    matches.sort(
        key=lambda item: (
            item["match_score"],
            item["confidence"],
            item["text_similarity"],
        ),
        reverse=True
    )

    return matches


# ============================================================
# LOCATE TARGET
# ============================================================

def locate_target(
    image,
    target,
    cells
):
    """
    Crop the selected cells as ONE region,
    OCR that region, then convert the result
    back to screen coordinates.

    This follows the same architecture as
    the previous Tesseract implementation.
    """

    width, height = image.size

    if not cells:
        raise RuntimeError(
            "No grid cells were supplied."
        )

    print(
        f"[OCR] Searching for {target!r}",
        file=sys.stderr,
        flush=True
    )

    print(
        f"[OCR] Cells: {cells}",
        file=sys.stderr,
        flush=True
    )

    # ========================================================
    # GET CELL BOUNDS
    # ========================================================

    bounds = [
        get_cell_bounds(
            width,
            height,
            cell
        )
        for cell in cells
    ]

    for cell, bound in zip(
        cells,
        bounds
    ):

        print(
            f"[OCR] Cell {cell}: {bound}",
            file=sys.stderr,
            flush=True
        )

    # ========================================================
    # COMBINE SELECTED CELLS
    # ========================================================

    region_x1 = min(
        bound[0]
        for bound in bounds
    )

    region_y1 = min(
        bound[1]
        for bound in bounds
    )

    region_x2 = max(
        bound[2]
        for bound in bounds
    )

    region_y2 = max(
        bound[3]
        for bound in bounds
    )

    print(
        f"[OCR] Region: "
        f"({region_x1},{region_y1}) -> "
        f"({region_x2},{region_y2})",
        file=sys.stderr,
        flush=True
    )

    # ========================================================
    # CROP
    # ========================================================

    cropped = image.crop(
        (
            region_x1,
            region_y1,
            region_x2,
            region_y2,
        )
    )
    debug_path = "debug_crop_cell_50.png"

    cropped.save(debug_path)

    print(
    f"[OCR DEBUG] Saved crop to: {debug_path}",
    file=sys.stderr,
    flush=True
    )

    results = find_text(
    cropped,
    target
    )

    # ========================================================
    # OCR
    # ========================================================

    results = find_text(
        cropped,
        target
    )

    if not results:

        raise RuntimeError(
            f'Target "{target}" was not found '
            f'inside selected cells {cells}.'
        )

    # ========================================================
    # BEST RESULT
    # ========================================================

    result = max(
        results,
        key=lambda item: (
            item["match_score"],
            item["confidence"],
            item["text_similarity"],
        )
    )

    # ========================================================
    # OCR -> ORIGINAL CROP COORDINATES
    # ========================================================

    original_x = (
        region_x1
        + int(result["x"] / OCR_SCALE)
    )

    original_y = (
        region_y1
        + int(result["y"] / OCR_SCALE)
    )

    original_width = int(
        result["width"]
        / OCR_SCALE
    )

    original_height = int(
        result["height"]
        / OCR_SCALE
    )

    # ========================================================
    # CLICK CENTER
    # ========================================================

    click_x = (
        original_x
        + original_width // 2
    )

    click_y = (
        original_y
        + original_height // 2
    )

    print(
        f"[OCR] FOUND: "
        f"{result['text']!r}",
        file=sys.stderr,
        flush=True
    )

    print(
        f"[OCR] Target box: "
        f"x={original_x}, "
        f"y={original_y}, "
        f"w={original_width}, "
        f"h={original_height}",
        file=sys.stderr,
        flush=True
    )

    print(
        f"[OCR] Click: "
        f"({click_x}, {click_y})",
        file=sys.stderr,
        flush=True
    )

    return {
        "x": click_x,
        "y": click_y,

        "bbox": {
            "x1": original_x,
            "y1": original_y,
            "x2": original_x + original_width,
            "y2": original_y + original_height,
        },

        "center": {
            "x": click_x,
            "y": click_y,
        },

        "confidence": result["confidence"],

        "match_score": result["match_score"],

        "text": result["text"],

        "cell": cells[0] if len(cells) == 1 else cells,
    }


# ============================================================
# REQUEST PROCESSING
# ============================================================

def process_request(request):

    image_bytes = base64.b64decode(
        request["image"]
    )

    image = Image.open(
        BytesIO(image_bytes)
    ).convert("RGB")

    return locate_target(
        image,
        request["text"],
        request["cells"]
    )


# ============================================================
# MAIN WORKER
# ============================================================

def main():

    # stdout is reserved for JSON communication.
    print(
        json.dumps({
            "ready": True
        }),
        flush=True
    )

    for line in sys.stdin:

        line = line.strip()

        if not line:
            continue

        try:

            request = json.loads(
                line
            )

            result = process_request(
                request
            )

            print(
                json.dumps({
                    "ok": True,
                    "result": result
                }),
                flush=True
            )

        except Exception as e:
            
            import traceback
            
            traceback.print_exc(
                file = sys.stderr
            )
            

            print(
                json.dumps({
                    "ok": False,
                    "error": str(e)
                }),
                flush=True
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()