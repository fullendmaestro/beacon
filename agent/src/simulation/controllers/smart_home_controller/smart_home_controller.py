from __future__ import annotations

import threading

import uvicorn
from api import create_app
from controller_service import SmartHomeController

controller = SmartHomeController()
app = create_app(controller)


def run_server() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


def main() -> None:
    controller.init_devices()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("Smart Home Controller running on http://127.0.0.1:8000")

    while controller.supervisor.step(controller.time_step) != -1:
        controller.step_simulation()


if __name__ == "__main__":
    main()