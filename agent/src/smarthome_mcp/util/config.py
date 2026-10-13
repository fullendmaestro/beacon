import os

# Base URL for the Smart Home Hub Controller (Webots simulation controller or mock hub)
SMART_HOME_HUB_URL = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000")
