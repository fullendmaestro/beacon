# Beacon

**Beacon** is an intelligent, event-driven smart home and domestic robotics digital twin that orchestrates IoT devices and a PAL Robotics **TIAGo** mobile manipulator to assist, guide, and protect residents in real time.

## 🏆 Hackathon Details

This project was designed and built for the **Amazon App Dev 2026** Devpost hackathon.

| Field | Details |
| --- | --- |
| **Hackathon** | Amazon App Dev 2026 |
| **Track** | Alexa+ |
| **Submission URL** | [amazonappdev2026.devpost.com](https://amazonappdev2026.devpost.com/) |

## ✨ Core Capabilities

- **Decoupled Control Plane & Event Broker**: Standalone FastAPI hub (`beacon_hub`) backed by a SQLite WAL registry and an async pub/sub event bus with zero-polling WebSocket multiplexing (`/ws/events`, `/ws/sim-bridge`).
- **Dual-Mode Physics Twin**: Seamlessly hot-swaps between a live **Webots R2025a 3D** simulation (`world_spawner` + `iot_device_controller`) and an in-process **Virtual Physics Fallback Worker** when Webots is offline.
- **Dynamic IoT Provisioning**: Spawn or remove lights, motorized doors/gates, window blinds, HVAC radiators, smart appliances, cameras, and sensors at runtime via REST/MCP or the Web UI.
- **Autonomous TIAGo Errand Bot**: Orthogonal Manhattan route planning with automatic blocking-door detection, wheel-odometry navigation, 7-DoF arm/gripper manipulation, and multi-step `fetch` / `deliver` errands.
- **Interactive 2D Floorplan & Generative Tool UI**: Next.js + Assistant UI interface featuring a live SVG floorplan mini-map, click-to-dispatch robot navigation, and real-time Manhattan route preview cards.

## 🏗️ Architecture

```text
Next.js Web & Assistant UI  ──(WS /ws/events + REST)──►  Beacon Core Hub (FastAPI :8000)
                                                          ├─ SQLite WAL (beacon_state.db)
                                                          ├─ Async Pub/Sub Event Broker
                                                          ├─ MCP Suites (smarthome_mcp + tiago_mcp)
                                                          └─ Virtual Physics Worker ◄─► Webots 3D Bridge
```

## 🚀 Quick Start

### 1. Backend Agent & Core Hub (`agent/`)

```bash
cd agent
uv sync

# Start the standalone Smart Home Hub on port 8000 (optional, auto-starts with LangGraph)
uv run python -m beacon_hub.main

# Start the LangGraph agent server on port 2024
uv run langgraph dev --allow-blocking
```

### 2. Web UI (`web/`)

```bash
cd web
bun install
bun dev
```

Open [http://localhost:3000/home](http://localhost:3000/home) to use the chat assistant, live 2D floorplan mini-map, and smart home device controls. To attach the 3D physics scene, open `agent/src/simulation/worlds/beacon_home.wbt` in **Webots R2025a**.

