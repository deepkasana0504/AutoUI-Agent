import asyncio
import base64
import json
import subprocess
from io import BytesIO
from pathlib import Path


class OCRWorker:

    def __init__(self):

        project_root = Path(__file__).resolve().parent

        worker_script = project_root / "ocr_worker.py"

        ocr_python = (
            project_root.parent
            / ".venv-ocr"
            / "Scripts"
            / "python.exe"
        )

        if not ocr_python.exists():
            raise RuntimeError(
                f"OCR Python not found: {ocr_python}"
            )

        if not worker_script.exists():
            raise RuntimeError(
                f"OCR worker not found: {worker_script}"
            )

        print("Starting OCR worker...", flush=True)

        self.process = subprocess.Popen(
            [
                str(ocr_python),
                str(worker_script),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Wait until PaddleOCR has initialized.
        ready_line = self.process.stdout.readline()

        if not ready_line:
            raise RuntimeError(
                "OCR worker exited during startup."
            )

        ready = json.loads(ready_line)

        if not ready.get("ready"):
            raise RuntimeError(
                f"OCR worker failed to initialize: {ready}"
            )

        print("OCR worker ready.", flush=True)

    def locate(
        self,
        image_bytes: bytes,
        text: str,
        cells: list[int],
    ):

        request = {
            "image": base64.b64encode(
                image_bytes
            ).decode("ascii"),

            "text": text,

            "cells": cells,
        }

        self.process.stdin.write(
            json.dumps(request) + "\n"
        )

        self.process.stdin.flush()

        response_line = (
            self.process.stdout.readline()
        )

        if not response_line:
            raise RuntimeError(
                "OCR worker stopped unexpectedly."
            )

        response = json.loads(
            response_line
        )

        if not response.get("ok"):
            raise RuntimeError(
                response.get(
                    "error",
                    "Unknown OCR worker error"
                )
            )

        return response["result"]

    def close(self):

        if self.process.poll() is None:

            self.process.terminate()

            try:
                self.process.wait(
                    timeout=5
                )
            except subprocess.TimeoutExpired:
                self.process.kill()


# One persistent worker for the MCP server.
ocr_worker = OCRWorker()


async def locate_target(
    text: str,
    cells: list[int],
):
    """
    Locate text using the persistent
    Python 3.11 PaddleOCR worker.
    """

    # Import the module itself so we always
    # get the current screenshot global.
    from computer import screenshot

    image = screenshot.current_screenshot

    if image is None:
        raise RuntimeError(
            "No screenshot available."
        )

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    image_bytes = buffer.getvalue()

    result = await asyncio.to_thread(
        ocr_worker.locate,
        image_bytes,
        text,
        cells,
    )

    if result is None:
        raise RuntimeError(
            f"Could not find '{text}' "
            f"in cells {cells}"
        )

    return {
        "x": result["center"]["x"],
        "y": result["center"]["y"],
        "bbox": result["bbox"],
        "confidence": result["confidence"],
        "cell": result["cell"],
    }