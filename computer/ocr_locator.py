from PIL import ImageOps , Image
import pytesseract
from pytesseract import Output
from difflib import SequenceMatcher


# =========================================================
# SETTINGS
# =========================================================

OCR_SCALE = 3
TESSERACT_CONFIG = "--psm 6"

# Minimum combined score required for a fuzzy match.
# This allows small OCR mistakes such as:
#     Search -> earch
FUZZY_MATCH_THRESHOLD = 0.80


# =========================================================
# PREPROCESS FOR OCR
# =========================================================

def preprocess_for_ocr(image):
    """Convert image to grayscale and upscale it 3x."""

    gray = ImageOps.grayscale(image)

    scaled = gray.resize(
        (
            gray.width * OCR_SCALE,
            gray.height * OCR_SCALE,
        ),
        Image.Resampling.LANCZOS,
    )

    return scaled


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):
    """Normalize OCR text while ignoring punctuation/symbols."""

    return "".join(
        character
        for character in text.strip().lower()
        if character.isalnum() or character.isspace()
    )


def word_similarity(a, b):
    """Return fuzzy similarity between two words."""

    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


# =========================================================
# OCR
# =========================================================

def find_text(image, target):
    """
    Find target text using fuzzy, confidence-aware OCR.

    The complete target does not need to be OCR-perfect.

    Example:

        Target: Search or enter web address
        OCR:    earch or enter web address

    is accepted because the other words match strongly.
    """

    processed = preprocess_for_ocr(image)

    data = pytesseract.image_to_data(
        processed,
        config=TESSERACT_CONFIG,
        output_type=Output.DICT,
    )

    words = []

    for i in range(len(data["text"])):

        text = data["text"][i].strip()

        if not text:
            continue

        try:
            confidence = float(data["conf"][i])
        except (ValueError, TypeError):
            confidence = 0.0

        normalized = normalize_text(text)

        if not normalized:
            continue

        words.append({
            "text": text,
            "normalized": normalized,
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "width": int(data["width"][i]),
            "height": int(data["height"][i]),
            "confidence": max(0.0, min(100.0, confidence)),
            "block": data["block_num"][i],
            "par": data["par_num"][i],
            "line": data["line_num"][i],
        })

    target_normalized = normalize_text(target)
    target_words = target_normalized.split()

    if not target_words:
        return []

    # =====================================================
    # SINGLE WORD
    # =====================================================

    if len(target_words) == 1:

        matches = []

        for word in words:

            similarity = word_similarity(
                target_words[0],
                word["normalized"],
            )

            score = (
                similarity * 0.65
                + (word["confidence"] / 100.0) * 0.35
            )

            if score >= FUZZY_MATCH_THRESHOLD:

                result = convert_result_to_original(word)

                result["match_score"] = score
                result["text_similarity"] = similarity
                result["average_confidence"] = word["confidence"]

                matches.append(result)

        return sorted(
            matches,
            key=lambda item: item["match_score"],
            reverse=True,
        )

    # =====================================================
    # MULTI-WORD FUZZY MATCH
    # =====================================================

    matches = []
    target_count = len(target_words)

    for start_index in range(len(words)):

        candidate_words = []

        for index in range(start_index, len(words)):

            word = words[index]

            # Keep the candidate phrase on one OCR line.
            if candidate_words:
                previous = candidate_words[-1]

                if (
                    word["block"] != previous["block"]
                    or word["par"] != previous["par"]
                    or word["line"] != previous["line"]
                ):
                    break

            candidate_words.append(word)

            if len(candidate_words) > target_count:
                break

            if len(candidate_words) != target_count:
                continue

            similarities = [
                word_similarity(
                    target_word,
                    candidate_word["normalized"],
                )
                for target_word, candidate_word
                in zip(target_words, candidate_words)
            ]

            average_similarity = (
                sum(similarities) / len(similarities)
            )

            average_confidence = (
                sum(word["confidence"] for word in candidate_words)
                / len(candidate_words)
            )

            # Strong matches matter because one bad OCR word
            # should not destroy an otherwise excellent phrase.
            strong_match_ratio = (
                sum(similarity >= 0.80 for similarity in similarities)
                / len(similarities)
            )

            # Combined score:
            #   55% text similarity
            #   25% OCR confidence
            #   20% strong word matches
            score = (
                average_similarity * 0.55
                + (average_confidence / 100.0) * 0.25
                + strong_match_ratio * 0.20
            )

            if score >= FUZZY_MATCH_THRESHOLD:
                matches.append({
                    "words": candidate_words,
                    "similarities": similarities,
                    "average_similarity": average_similarity,
                    "average_confidence": average_confidence,
                    "strong_match_ratio": strong_match_ratio,
                    "match_score": score,
                })

    # =====================================================
    # CONVERT MATCHES
    # =====================================================

    converted = []

    for match in matches:

        result = combine_words(match["words"])

        result["match_score"] = match["match_score"]
        result["text_similarity"] = match["average_similarity"]
        result["average_confidence"] = match["average_confidence"]
        result["strong_match_ratio"] = match["strong_match_ratio"]

        converted.append(result)

    converted.sort(
        key=lambda item: (
            item["match_score"],
            item["average_confidence"],
            item["text_similarity"],
        ),
        reverse=True,
    )

    return converted


# =========================================================
# CONVERT OCR COORDINATES
# =========================================================

def convert_result_to_original(result):

    return {
        "text": result["text"],

        "x": int(result["x"] / OCR_SCALE),
        "y": int(result["y"] / OCR_SCALE),

        "width": int(result["width"] / OCR_SCALE),
        "height": int(result["height"] / OCR_SCALE),

        "confidence": result["confidence"],
    }


# =========================================================
# COMBINE MULTIPLE OCR WORDS
# =========================================================

def combine_words(words):

    x1 = min(word["x"] for word in words)
    y1 = min(word["y"] for word in words)

    x2 = max(
        word["x"] + word["width"]
        for word in words
    )

    y2 = max(
        word["y"] + word["height"]
        for word in words
    )

    confidence = min(
        word["confidence"]
        for word in words
    )

    return {
        "text": " ".join(
            word["text"]
            for word in words
        ),

        "x": int(x1 / OCR_SCALE),
        "y": int(y1 / OCR_SCALE),

        "width": int((x2 - x1) / OCR_SCALE),
        "height": int((y2 - y1) / OCR_SCALE),

        "confidence": confidence,
    }


# =========================================================
# LOCATE TARGET
# =========================================================

def locate_target(
    image,
    target,
    cells,
    columns=6,
    rows=4,
):
    """
    Crop the selected grid cells and locate the target.

    Returns screen coordinates.

    Fuzzy OCR means a small OCR error no longer forces the
    planner to repeat the same action.
    """

    width, height = image.size

    if not cells:
        raise RuntimeError(
            "No grid cells were supplied."
        )

    # =====================================================
    # CELL BOUNDS
    # =====================================================

    def get_cell_bounds(cell_number):

        index = cell_number - 1

        row = index // columns
        column = index % columns

        cell_width = width / columns
        cell_height = height / rows

        x1 = int(column * cell_width)
        y1 = int(row * cell_height)

        x2 = int((column + 1) * cell_width)
        y2 = int((row + 1) * cell_height)

        return x1, y1, x2, y2

    # =====================================================
    # REGION
    # =====================================================

    bounds = [
        get_cell_bounds(cell)
        for cell in cells
    ]

    region_x1 = min(bound[0] for bound in bounds)
    region_y1 = min(bound[1] for bound in bounds)

    region_x2 = max(bound[2] for bound in bounds)
    region_y2 = max(bound[3] for bound in bounds)

    # =====================================================
    # CROP
    # =====================================================

    cropped = image.crop(
        (
            region_x1,
            region_y1,
            region_x2,
            region_y2,
        )
    )

    # =====================================================
    # OCR
    # =====================================================

    results = find_text(
        cropped,
        target,
    )

    if not results:

        raise RuntimeError(
            f'Target "{target}" was not found '
            f'inside the selected cells {cells} '
            f'even with fuzzy OCR matching.'
        )

    # =====================================================
    # BEST RESULT
    # =====================================================

    result = max(
        results,
        key=lambda item: (
            item.get(
                "match_score",
                item.get("confidence", 0.0),
            ),
            item.get(
                "average_confidence",
                item.get("confidence", 0.0),
            ),
        ),
    )

    # =====================================================
    # CROP -> SCREEN
    # =====================================================

    original_x = region_x1 + result["x"]
    original_y = region_y1 + result["y"]

    # =====================================================
    # CLICK CENTER
    # =====================================================

    click_x = original_x + result["width"] // 2
    click_y = original_y + result["height"] // 2

    return {
        "x": click_x,
        "y": click_y,

        "ocr": result,

        "region": (
            region_x1,
            region_y1,
            region_x2,
            region_y2,
        ),
    }
