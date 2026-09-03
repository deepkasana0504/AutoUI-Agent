import time

from communication.client import (
    start_communication,
    wait_until_connected,
)

from communication.events import (
    incoming_messages,
    send_agent_status,
)

from agent.runner import (
    run_task,
)


# =========================================================
# START
# =========================================================

def main():

    print(
        "Starting AutoUI agent..."
    )


    # -----------------------------------------------------
    # CONNECT TO COMMUNICATION SERVER
    # -----------------------------------------------------

    print(
        "Starting communication..."
    )

    start_communication()


    print(
        "Waiting for communication server..."
    )

    if not wait_until_connected(
        timeout=30
    ):

        print(
            "Could not connect to communication server."
        )

        return


    print(
        "Agent connected."
    )


    send_agent_status(
        "ready",
        "Agent is ready and waiting for a task.",
    )


    # =====================================================
    # WAIT FOR PHONE TASK
    # =====================================================

    while True:

        print(
            "\nWaiting for task from phone..."
        )

        message = (
            incoming_messages.get()
        )


        if message.get(
            "type"
        ) != "user_message":

            continue


        task = (
            message.get(
                "text",
                "",
            )
            .strip()
        )


        if not task:

            continue


        print(
            "\n========================================"
        )

        print(
            "Received task:"
        )

        print(
            task
        )

        print(
            "========================================"
        )


        # -------------------------------------------------
        # RUN TASK
        # -------------------------------------------------

        try:

            run_task(
                task
            )

        except KeyboardInterrupt:

            print(
                "\nAgent stopped by user."
            )

            send_agent_status(
                "stopped",
                "Agent stopped by user.",
            )

            return


        except Exception as e:

            print(
                "\nFatal agent error:"
            )

            print(
                e
            )

            send_agent_status(
                "error",
                "Agent stopped because of an unexpected error.",
                {
                    "error": str(e),
                },
            )


        print(
            "\nTask runner finished."
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()