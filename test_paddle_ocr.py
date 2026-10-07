import time
import pyautogui
import numpy as np
from paddleocr import PaddleOCR


print("Taking screenshot...")

image = pyautogui.screenshot()

print(f"Full screenshot: {image.width} x {image.height}")


# Smaller search region
crop = image.crop((1300, 150, 1700, 400))

print(f"Crop size: {crop.width} x {crop.height}")

image_np = np.array(crop)


print("\nInitializing PaddleOCR...")

start = time.perf_counter()

ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

init_time = time.perf_counter() - start

print(f"Initialization: {init_time:.4f} seconds")


print("\nRunning OCR on SMALL CROP...")

start = time.perf_counter()

results = ocr.predict(image_np)

ocr_time = time.perf_counter() - start

print(f"OCR time: {ocr_time:.4f} seconds")


print("\n========== RESULTS ==========")

for result in results:

    texts = result["rec_texts"]
    scores = result["rec_scores"]
    boxes = result["rec_boxes"]

    for text, score, box in zip(texts, scores, boxes):

        print(
            f"Text: {text!r} | "
            f"Confidence: {score:.4f} | "
            f"Box: {box.tolist()}"
        )

        if "login" in text.lower():

            x1, y1, x2, y2 = map(int, box)

            # Convert crop coordinates back to screen coordinates
            x1 += 1300
            x2 += 1300
            y1 += 150
            y2 += 150

            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            print("\n========== LOGIN FOUND ==========")
            print(f"Screen box: ({x1}, {y1}) -> ({x2}, {y2})")
            print(f"Screen center: ({center_x}, {center_y})")
            print("=================================")