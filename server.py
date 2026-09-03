import asyncio
import json
import websockets


phone = None
agent = None


FORWARD_TO_PHONE = {
    "ask_user",
    "agent_status",
    "agent_event",
    "agent_action",
    "agent_verification",
    "agent_progress",
    "agent_error",
    "task_completed",
}


async def handle_client(websocket):
    global phone
    global agent

    print("New client connected")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                print("Received invalid JSON")
                continue

            message_type = data.get("type")

            if message_type == "register":
                role = data.get("role")

                if role == "phone":
                    phone = websocket
                    print("Phone connected")

                elif role == "agent":
                    agent = websocket
                    print("Agent connected")

                continue

            if message_type == "user_message":
                print("Phone says:", data.get("text"))

                if agent:
                    await agent.send(json.dumps(data))
                else:
                    print("Agent is not connected")

            elif message_type in FORWARD_TO_PHONE:
                print("Agent event:", data)

                if phone:
                    await phone.send(json.dumps(data))
                else:
                    print("Phone is not connected")

            else:
                print("Unknown message:", data)

    except websockets.ConnectionClosed:
        print("Client disconnected")

    finally:
        if websocket == phone:
            phone = None
            print("Phone disconnected")

        if websocket == agent:
            agent = None
            print("Agent disconnected")


async def main():
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        8080,
    ):
        print("Server running on port 8080")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
