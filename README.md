# Beacon | Autonomous Smart Home Operations & Domestic Robotics Assistant

**Beacon** is an event-driven, multimodal AI home operations and robotics orchestrator built for the **Amazon App Dev 2026** hackathon (**Alexa+ Track**). It unifies a 51-device smart estate and a **PAL Robotics TIAGo** mobile manipulator inside a synchronized **SQLite WAL Digital Twin** and **Webots R2025a 3D Physics Environment**, empowering residents to converse with, visually inspect, automate, and physically actuate their home in real time.

---

## 🏆 Hackathon Details

| Field         | Details             |
| ------------- | ------------------- |
| **Hackathon** | Amazon App Dev 2026 |

|
| **Track** | Alexa+ (Next-Generation Agentic Home & Ambient Intelligence)

|
| **Submission URL** | [amazonappdev2026.devpost.com](https://amazonappdev2026.devpost.com/)<br> |

---

## ✨ Core Capabilities

- **Dual MCP Tool Orchestration (`smarthome_mcp` + `tiago_mcp`):**

- **Smart Home MCP Suite:** Granular discovery, state control, and dynamic runtime VRML provisioning across **18 smart lights** (RGB + dimming), **9 interior doors & exterior barriers** (Front Entrance, Driveway Sliding Gate, Overhead Garage Door), **4 motorized window blinds**, **6 HVAC radiator zones**, **11 smart appliances & wall plugs** (with real-time Wattage telemetry), **5 motion/daylight sensors**, and **7 live camera streams**.

- **TIAGo Robotics MCP Suite:** Full telemetry and control over a PAL Robotics TIAGo mobile manipulator equipped with a 6-DoF arm, **Robotiq 2F-85 parallel gripper**, and **Orbbec Astra RGB head camera**.

- **Strict Zero-Hallucination Device Protocol:** Fuzzy device guessing is disabled at the database level (`strict_lookup`). Beacon enforces a deterministic discovery-first protocol (`d.id = :identifier OR d.wbt_name = :identifier`) before executing any actuation command.

- **Door-Aware Orthogonal Manhattan Route Planner & Errands:**

- Computes shortest-path trajectories across **14 navigation nodes** and **13 edges** using Dijkstra's algorithm with collinear segment simplification.

- Automatically detects closed or locked doors obstructing a planned route (`blocking_doors`), dispatches `BarrierActuatorWorker` commands to unlock and open them, and executes multi-step `fetch_item` and `deliver_item` errands autonomously.

- **Proactive Event Reactor & Autonomous Agent Wake-Up:**

- An in-process asynchronous Pub/Sub **Event Broker** (`EventBroker`) and **Event Reactor** (`EventReactor`) evaluate wildcard topic subscriptions (`sensor.telemetry.*`, `device.state.*`) with configurable cooldowns.

- When physical sensors trip, Beacon executes immediate deterministic hardware actions, pushes a live **Picture-in-Picture (PiP) toast alert** to the UI, and automatically wakes the LangGraph agent (`EventDrivenAgentBridge`) to inspect live camera feeds and assist the resident.

- **Multimodal Live Vision (`inspect_camera_feed`):** Captures real-time JPEG frames from any of the 6 room/exterior security cameras or TIAGo's POV camera, streaming MJPEG to the UI while passing base64 frames directly into the multimodal LLM for visual scene reasoning.

- **3D Webots Pedestrian & Stimulus Simulator:** Spawn articulated 13-joint Webots `Pedestrian` PROTO actors (`walk`, `loop`, and `stand` gait modes), arriving vehicles, or sudden dusk/nightfall drops directly from the UI to test end-to-end sensor-to-agent reactions.

- **Hot-Swappable Dual-Mode Physics Engine:** Seamlessly transitions between `WEBOTS_ATTACHED` (live 3D Webots R2025a supervisor & per-device controllers) and `VIRTUAL_PHYSICS_FALLBACK` (a 20Hz kinematic and synthetic camera engine in `VirtualPhysicsWorker` when running headlessly) with < 1.5s heartbeat detection.

- **Interactive 2D SVG Floorplan & Generative Tool UI:** Built with Next.js 16, Tailwind CSS, Shadcn UI, and `@assistant-ui/react-langgraph`, featuring real-time radial light glow gradients, animated door/gate actuation, live pedestrian and robot heading cones, and custom interactive tool cards.

---

## 🏗️ System Architecture

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        Next.js 16 Web & Assistant UI (:3000)                      │
│  • Generative Tool UIs (SmartHomeToolUIs, TiagoToolUIs, InspectCameraToolUI)      │
│  • Interactive 2D SVG Floorplan Minimap (50px=1m, Live Glows, Route Polylines)    │
│  • Webots Event Simulator Panel & EventDrivenAgentBridge (Auto-Wake PiP Toasts)   │
└───────────────┬───────────────────────────────────────────────────┬───────────────┘
                │ LangGraph Stream (:2024)                          │ WS /ws/events + REST (:8000)
                ▼                                                   ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│     Beacon LangGraph Agent (:2024)    │   │     Beacon Core Hub (FastAPI :8000)   │
│  • Multi-Provider Model Factory:      │   │  • SQLite WAL Digital Twin            │
│    Amazon Bedrock / Gemini / Vertex   │◄──┤    (beacon_state.db — 13 rooms,       │
│  • In-Process MCP Adapters:           │   │     51 devices, 14 nav nodes, rules)  │
│    ├─ smarthome_mcp (FastMCP)         │   │  • Async Pub/Sub EventBroker          │
│    └─ tiago_mcp (FastMCP)             │   │  • Autonomous EventReactor Engine     │
│  • Vision & Rule Tools:               │   │  • Hot-Swappable VirtualPhysicsWorker │
│    inspect_camera_feed, rules CRUD    │   │    (20Hz Kinematics & Synthetic Cams) │
└───────────────────────────────────────┘   └───────┬───────────────────────┬───────┘
                                                    │ WS /ws/sim-bridge     │ WS /ws/device/{id}
                                                    ▼                       ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        Webots R2025a 3D Simulation Runtime                        │
│  • world_spawner: Dynamic VRML Node Spawner (DEF DYNAMIC_DEVICES) & Interpolator  │
│  • tiago_home_controller (:8001): 4-Phase Manhattan Nav, 6-DoF Arm & 2F-85 Grip   │
│  • iot_device_controller: Process-Isolated Camera (MJPEG) & Sensor Telemetry      │
│  • pedestrian: 13-Joint Articulated Human Gait Controller (Walk / Loop / Stand)   │
└───────────────────────────────────────────────────────────────────────────────────┘


```

---

## 📂 Repository Structure

```text
beacon/
├── agent/                                  # Python Backend, LangGraph Agent & Webots Simulation
│   └── src/
│       ├── beacon_agent/                   # LangGraph agent, system prompt, Bedrock/Gemini model factory
│       ├── beacon_hub/                     # FastAPI Core Hub (:8000), EventBroker, EventReactor
│       │   ├── database/                   # SQLite WAL manager, strict lookup, estate seed data
│       │   ├── fallback/                   # 20Hz VirtualPhysicsWorker & synthetic HUD camera renderer
│       │   └── routers/                    # REST & WebSocket multiplexer (/ws/events, /ws/sim-bridge)
│       ├── smarthome_mcp/                  # FastMCP server for lights, doors, blinds, climate, appliances
│       ├── tiago_mcp/                      # FastMCP server for TIAGo route planning, nav, arm & errands
│       └── simulation/                     # Webots R2025a world & controllers
│           ├── worlds/beacon_home.wbt      # 3D Smart Estate with cutaway roof & PAL Robotics TIAGo
│           └── controllers/                # world_spawner, tiago_home_controller, pedestrian, iot_device
└── web/                                    # Next.js 16 Frontend & Assistant UI
    ├── app/                                # Landing page & /home workspace layout
    ├── components/
    │   ├── assistant.tsx                   # LangGraph runtime provider, Vision Tool UI & Auto-Wake Bridge
    │   ├── assistant-ui/                   # Generative UI cards for Smart Home & TIAGo MCP tools
    │   └── panels/                         # 2D SVG Floorplan, Category Drawers & Event Simulator Panel
    └── lib/                                # Zero-polling WebSocket store, coordinate transforms, REST client


```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**

- **Bun** (or Node.js 20+)

- **Webots R2025a** _(Optional — Beacon runs out-of-the-box in `VIRTUAL_PHYSICS_FALLBACK` mode and hot-attaches automatically whenever Webots is opened)_

### 1. Attach the 3D Webots Simulation (Optional)

1. Open **Webots R2025a** and load `agent/src/simulation/worlds/beacon_home.wbt`.

2. In Webots Preferences (**Tools → Preferences → Python command**), point the Python executable to your `agent/.venv` interpreter:

- **Windows:** `agent/.venv/Scripts/python.exe`

- **macOS / Linux:** `agent/.venv/bin/python`

3. Press **Play** in Webots. `world_spawner` and `tiago_home_controller` will connect to `ws://127.0.0.1:8000/ws/sim-bridge`, dynamically spawn all 51 SQLite devices into `DEF DYNAMIC_DEVICES`, and switch the UI badge to **`Webots 3D Attached`**.

### 2. Configure & Start the Agent + Core Hub (`agent/`)

```bash
cd agent
uv sync

```

Configure your `.env` in `agent/` (supports **Amazon Bedrock**, **Google Gemini**, or **Vertex AI**):

```env
# Option A: Amazon Bedrock (Claude 3.5 Sonnet / Amazon Nova)
BEACON_PROVIDER=bedrock
BEACON_AGENT_MODEL=us.anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1

# Option B: Google Gemini / Vertex AI
# GEMINI_API_KEY=your_api_key_here
# BEACON_AGENT_MODEL=gemini-2.5-flash

```

Start the LangGraph server (which automatically boots the **Beacon Core Hub** on port `8000` in a background daemon thread):

```bash
# Start LangGraph dev server on port 2024 (auto-starts Beacon Core Hub on :8000)
uv run langgraph dev --allow-blocking

# Or run the standalone Core Hub explicitly on port 8000:
uv run python -m beacon_hub.main

```

### 3. Start the Web UI (`web/`)

```bash
cd web
bun install
bun dev

```

Open **[http://localhost:3000/home](http://localhost:3000/home)** to access the Beacon assistant, interactive 2D floorplan map, device drawers, and event simulator.

---

## 🧪 Try These Prompts & Scenarios

- **Discovery & Scene Orchestration:**

> _"Trigger the movie scene and check what mode the Living Room Smart TV is in."_

- **Autonomous Multi-Room Robot Errand (with Door Auto-Clearance):**

> _"Send TIAGo to fetch a cup from the kitchen and bring it back to the foyer."_

- **Multimodal Camera Inspection:**

> _"Inspect the live feed from the Front Door Camera and tell me what you see."_

- **Event-Driven Automation Rule Creation:**

> _"Create an automation rule: when the Living Room Motion Sensor is triggered, turn on the Living Room Main Light to 100% and dispatch TIAGo to the living room."_

- **Live 3D Stimulus Testing:**

Open the **Event Simulator** (⚡ icon in the left sidebar) and click **Spawn** on _"Visitor Walks to Front Door"_ or _"Car Arrives at Driveway Gate"_ to watch the 3D actor trip the Webots ray sensor, trigger deterministic device rules, pop up a live PiP camera toast, and wake the Beacon agent automatically.
