from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


# =========================================================
# SETTINGS
# =========================================================

# Change this if you want to test another image.
IMAGE_PATH = Path("autoUI_project/debug/step_002_crop.png")

# Try several magnifications.
SCALES = [1, 2, 3, 4, 5]

# Thresholds used for simple binary preprocessing.
THRESHOLDS = [160, 180, 200, 220]

OUTPUT_DIR = Path("ocr_variants")

TESSERACT_CONFIG = "--psm 6"


# =========================================================
# HELPERS
# =========================================================

def upscale(image, scale):
    """Upscale using high-quality Lanczos resampling."""
    if scale == 1:
        return image.copy()

    return image.resize(
        (
            image.width * scale,
            image.height * scale,
        ),
        Image.Resampling.LANCZOS,
    )


def otsu_threshold(image):
    """
    Apply Otsu thresholding using only PIL + numpy.
    """
    gray = ImageOps.grayscale(image)

    array = np.asarray(gray)

    histogram = np.bincount(
        array.ravel(),
        minlength=256,
    )

    total = array.size
    total_sum = np.dot(
        np.arange(256),
        histogram,
    )

    weight_background = 0
    sum_background = 0

    best_threshold = 0
    best_variance = -1.0

    for threshold in range(256):

        weight_background += histogram[threshold]

        if weight_background == 0:
            continue

        weight_foreground = (
            total - weight_background
        )

        if weight_foreground == 0:
            break

        sum_background += (
            threshold
            * histogram[threshold]
        )

        mean_background = (
            sum_background
            / weight_background
        )

        mean_foreground = (
            total_sum
            - sum_background
        ) / weight_foreground

        variance = (
            weight_background
            * weight_foreground
            * (
                mean_background
                - mean_foreground
            ) ** 2
        )

        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold

    binary = gray.point(
        lambda pixel:
        255 if pixel > best_threshold else 0
    )

    return binary, best_threshold


def run_ocr(image):
    """Return raw OCR text."""
    return pytesseract.image_to_string(
        image,
        config=TESSERACT_CONFIG,
    ).strip()


def print_result(name, image, text):
    print("\n" + "=" * 60)
    print(f"VERSION: {name}")
    print(f"SIZE: {image.size}")
    print("RAW OCR:")
    print(repr(text))


# =========================================================
# LOAD IMAGE
# =========================================================

if not IMAGE_PATH.exists():
    raise FileNotFoundError(
        f"Image not found: {IMAGE_PATH}\n"
        f"Put the image beside this test file or change "
        f"IMAGE_PATH at the top."
    )

image = Image.open(
    IMAGE_PATH
).convert("RGB")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


print("========== OCR MAGNIFICATION EXPERIMENT ==========")
print(f"Image: {IMAGE_PATH}")
print(f"Original size: {image.size}")
print(f"Scales: {SCALES}")


# =========================================================
# EXPERIMENT
# =========================================================

for scale in SCALES:

    gray = ImageOps.grayscale(
        image
    )

    scaled = upscale(
        gray,
        scale,
    )

    # -----------------------------------------------------
    # 1. GRAYSCALE
    # -----------------------------------------------------

    name = f"gray_{scale}x"

    output = (
        OUTPUT_DIR
        / f"{name}.png"
    )

    scaled.save(output)

    text = run_ocr(
        scaled
    )

    print_result(
        name,
        scaled,
        text,
    )

    # -----------------------------------------------------
    # 2. CONTRAST
    # -----------------------------------------------------

    for factor in (
        1.5,
        2.0,
    ):

        contrasted = (
            ImageEnhance.Contrast(
                scaled
            ).enhance(factor)
        )

        name = (
            f"contrast_{factor}_{scale}x"
        )

        output = (
            OUTPUT_DIR
            / f"{name}.png"
        )

        contrasted.save(
            output
        )

        text = run_ocr(
            contrasted
        )

        print_result(
            name,
            contrasted,
            text,
        )

    # -----------------------------------------------------
    # 3. BLUR + OTSU
    # -----------------------------------------------------

    blurred = scaled.filter(
        ImageFilter.GaussianBlur(
            radius=0.6
        )
    )

    otsu_image, otsu_value = (
        otsu_threshold(
            blurred
        )
    )

    name = (
        f"blur_otsu_{scale}x"
    )

    output = (
        OUTPUT_DIR
        / f"{name}.png"
    )

    otsu_image.save(
        output
    )

    text = run_ocr(
        otsu_image
    )

    print_result(
        name,
        otsu_image,
        text,
    )

    print(
        f"Otsu threshold: {otsu_value}"
    )

    # -----------------------------------------------------
    # 4. FIXED THRESHOLDS
    # -----------------------------------------------------

    for threshold in THRESHOLDS:

        threshold_image = (
            scaled.point(
                lambda pixel,
                t=threshold:
                255 if pixel > t else 0
            )
        )

        name = (
            f"threshold_{threshold}_{scale}x"
        )

        output = (
            OUTPUT_DIR
            / f"{name}.png"
        )

        threshold_image.save(
            output
        )

        text = run_ocr(
            threshold_image
        )

        print_result(
            name,
            threshold_image,
            text,
        )


# =========================================================
# SUMMARY
# =========================================================

print("\n" + "=" * 60)
print("EXPERIMENT COMPLETE")
print("=" * 60)

print(
    f"All processed images are in: {OUTPUT_DIR}"
)
