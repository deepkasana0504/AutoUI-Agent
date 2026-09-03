import os

from dotenv import load_dotenv


load_dotenv()


# =========================================================
# GEMINI
# =========================================================

MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash",
)

API_KEY = (
    os.getenv("GEMINI_API_KEY2")
    or
    os.getenv("GEMINI_API_KEY")
)


# =========================================================
# COMMUNICATION SERVER
# =========================================================

SERVER_URL = os.getenv(
    "AUTOUI_SERVER_URL",
    "ws://localhost:8080",
)


# =========================================================
# AGENT
# =========================================================

MAX_STEPS = None

PREPARE_DELAY = 10