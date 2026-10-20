from __future__ import annotations

import os
import threading

import uvicorn
from api import create_app
from constants import SMART_HOME_PORT
from controller_service import SmartHomeController

controller = SmartHomeController()
app = create_app(controller)


def run_server() -> None:
    host = os.getenv("SMART_HOME_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=SMART_HOME_PORT, log_level="warning")


def main() -> None:
    controller.init_devices()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print(f"Smart Home Controller running on http://127.0.0.1:{SMART_HOME_PORT}")

    while controller.supervisor.step(controller.time_step) != -1:
        controller.step_simulation()


if __name__ == "__main__":
    main()