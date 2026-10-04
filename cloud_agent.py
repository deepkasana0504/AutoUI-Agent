"""Entry point for a customer device connecting to the cloud gateway.

Run this instead of main.py when ChatGPT is the reasoning client.
The legacy phone + Gemini entry point remains available as main.py.
"""
import asyncio
from agent.cloud_client import run_cloud_agent

if __name__ == "__main__":
    asyncio.run(run_cloud_agent())
