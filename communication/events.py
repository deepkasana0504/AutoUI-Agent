import asyncio
import json
import queue


# =========================================================
# INCOMING USER MESSAGES
# =========================================================

incoming_messages = queue.Queue()


# =========================================================
# CONNECTION STATE
# =========================================================

_agent_socket = None
_agent_loop = None


# =========================================================
# SET CONNECTION
# =========================================================

def set_connection(socket, loop):
    global _agent_socket
    global _agent_loop

    _agent_socket = socket
    _agent_loop = loop


# =========================================================
# SEND TO PHONE
# =========================================================

def send_to_phone(payload):

    if (
        _agent_socket is None
        or _agent_loop is None
    ):
        print(
            "Cannot send event: "
            "communication server is not connected"
        )

        return False

    async def send():

        await _agent_socket.send(
            json.dumps(payload)
        )

    future = asyncio.run_coroutine_threadsafe(
        send(),
        _agent_loop,
    )

    try:

        future.result(
            timeout=10
        )

        return True

    except Exception as e:

        print(
            "Failed to send message to phone:",
            e,
        )

        return False


# =========================================================
# AGENT STATUS
# =========================================================

def send_agent_status(
    status,
    message=None,
    data=None,
):

    return send_to_phone({

        "type": "agent_status",

        "status": status,

        "message": message,

        "data": data,

    })


# =========================================================
# AGENT EVENT
# =========================================================

def send_agent_event(
    event,
    data=None,
):

    return send_to_phone({

        "type": "agent_event",

        "event": event,

        "data": data,

    })


# =========================================================
# ACTION STATUS
# =========================================================

def publish_action_status(
    action,
    status,
    result=None,
):

    return send_agent_event(

        "action_status",

        {
            "action": action,
            "status": status,
            "result": result,
        },

    )


# =========================================================
# PROGRESS
# =========================================================

def publish_progress(message):

    return send_agent_event(

        "progress",

        {
            "message": message,
        },

    )


# =========================================================
# SEND QUESTION
# =========================================================

def send_question(question):

    return send_to_phone({

        "type": "ask_user",

        "question": question,

    })


# =========================================================
# WAIT FOR USER
# =========================================================

def ask_user(question):

    print(
        "\n========================================"
    )

    print(
        "WAITING FOR USER"
    )

    print(
        "========================================"
    )

    print(
        f"Question: {question}"
    )

    # -----------------------------------------------------
    # Tell frontend that agent is waiting
    # -----------------------------------------------------

    send_agent_status(

        "waiting_for_user",

        "Agent needs information from you.",

        {
            "question": question,
        },

    )

    # -----------------------------------------------------
    # Dedicated event
    # -----------------------------------------------------

    send_agent_event(

        "user_question",

        {
            "question": question,
        },

    )

    # -----------------------------------------------------
    # Send actual question to phone
    # -----------------------------------------------------

    send_question(
        question
    )

    print(
        "\nQuestion sent to phone."
    )

    print(
        "Waiting for answer..."
    )

    # -----------------------------------------------------
    # BLOCK UNTIL PHONE ANSWERS
    # -----------------------------------------------------

    while True:

        message = incoming_messages.get()

        if not isinstance(
            message,
            dict,
        ):
            continue

        message_type = message.get(
            "type"
        )

        # -------------------------------------------------
        # USER ANSWER
        # -------------------------------------------------

        if message_type == "user_message":

            answer = message.get(
                "text",
                "",
            )

            answer = str(
                answer
            ).strip()

            print(
                "\n========================================"
            )

            print(
                "USER ANSWER RECEIVED"
            )

            print(
                f"Answer: {answer}"
            )

            print(
                "========================================"
            )

            # ---------------------------------------------
            # Tell frontend that we received it
            # ---------------------------------------------

            send_agent_event(

                "user_answer_received",

                {
                    "question": question,
                    "answer": answer,
                },

            )

            send_agent_status(

                "working",

                "User answered. Continuing the task.",

                {
                    "question": question,
                    "answer": answer,
                },

            )

            return answer