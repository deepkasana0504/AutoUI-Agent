import asyncio
import json
import threading
import time

import websockets

from config import SERVER_URL
from communication.events import (
    incoming_messages,
    set_connection,
)


agent_socket = None
agent_loop = None
connected_event = threading.Event()


async def connect_to_server():
    global agent_socket

    while True:
        try:
            print(f"Connecting to communication server: {SERVER_URL}")

            async with websockets.connect(
                SERVER_URL
            ) as websocket:
                agent_socket = websocket
                set_connection(
                    agent_socket,
                    agent_loop,
                )

                await agent_socket.send(
                    json.dumps({
                        "type": "register",
                        "role": "agent",
                    })
                )

                connected_event.set()
                print("Connected to communication server")

                async for message in agent_socket:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        print("Received invalid JSON from server")
                        continue

                    if data.get("type") == "user_message":
                        text = data.get("text", "").strip()

                        if text:
                            print("\nReceived from phone:")
                            print(text)

                            incoming_messages.put({
                                "type": "user_message",
                                "text": text,
                            })

        except Exception as e:
            connected_event.clear()
            print("Communication error:", e)
            print("Retrying connection in 3 seconds...")
            await asyncio.sleep(3)

        finally:
            agent_socket = None
            set_connection(None, None)


def start_communication():
    def run():
        global agent_loop

        agent_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(agent_loop)

        agent_loop.run_until_complete(
            connect_to_server()
        )

    thread = threading.Thread(
        target=run,
        daemon=True,
    )

    thread.start()


def wait_until_connected(timeout=None):
    print("Waiting for communication server connection...")

    if connected_event.wait(timeout):
        return True

    return False
