import { NextResponse } from "next/server";
import type { RobotDevice } from "@/lib/smart-home-api";

const TIAGO_URL = process.env.TIAGO_API_URL || "http://127.0.0.1:8001";
const HUB_URL =
  process.env.NEXT_PUBLIC_SMART_HOME_API_URL || "http://127.0.0.1:8000";

const ROOM_NODES: { id: string; name: string; room: string; x: number; y: number }[] = [
  { id: "front_door", name: "Front Entrance", room: "Foyer", x: -0.91, y: -7.62 },
  { id: "master_junction", name: "Master Bedroom Junction", room: "Foyer", x: -2.15, y: -7.62 },
  { id: "foyer", name: "Foyer Dock", room: "Foyer", x: -3.1, y: -7.62 },
  { id: "bathroom_junction", name: "Bathroom Junction", room: "Corridor", x: -4.94, y: -7.62 },
  { id: "hallway", name: "West Corridor Corner", room: "Corridor", x: -5.35, y: -7.62 },
  { id: "study_junction", name: "Study Bedroom Junction", room: "Corridor", x: -6.24, y: -7.62 },
  { id: "utility_room", name: "Utility Closet", room: "Utility", x: -0.91, y: -5.9 },
  { id: "master_bedroom", name: "Master Bedroom", room: "Master Bedroom", x: -2.15, y: -9.8 },
  { id: "bathroom", name: "Main Bathroom", room: "Bathroom", x: -4.94, y: -9.3 },
  { id: "study_bedroom", name: "Study Bedroom", room: "Study Bedroom", x: -6.24, y: -9.8 },
  { id: "kitchen_approach", name: "Kitchen Door Approach", room: "Living Room", x: -5.35, y: -3.95 },
  { id: "living_room", name: "Living Room", room: "Living Room", x: -5.35, y: -1.8 },
  { id: "kitchen", name: "Kitchen", room: "Kitchen", x: -2.35, y: -3.95 },
  { id: "dining_room", name: "Dining Room", room: "Dining Room", x: -9.2, y: -1.8 },
];

function inferNearestRoom(x: number, y: number): { room: string; node: string; dist: number } {
  let bestDist = Infinity;
  let best = { room: "Foyer", node: "foyer", dist: Infinity };
  for (const n of ROOM_NODES) {
    const d = Math.hypot(x - n.x, y - n.y);
    if (d < bestDist) {
      bestDist = d;
      best = { room: n.room, node: n.id, dist: d };
    }
  }
  return best;
}

function inferStatus(task: string | undefined, room: string, isDockedNode: boolean): string {
  if (!task || task === "idle") {
    return isDockedNode ? "Docked" : "Idle";
  }
  const t = task.toLowerCase();
  if (t.includes("navigat")) return "Navigating";
  if (t.includes("pick") || t.includes("plac")) return "Manipulating";
  if (t.includes("errand") || t.includes("deliver") || t.includes("fetch")) return "Executing Errand";
  return task;
}

export async function GET() {
  // 1. Attempt to fetch primary telemetry directly from TIAGo controller (Port 8001)
  try {
    const res = await fetch(`${TIAGO_URL}/telemetry`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1200),
    });
    if (res.ok) {
      const data = await res.json();
      const pose = data.pose || { x: -3.1, y: -7.62, theta: 1.57 };
      const nearest = inferNearestRoom(pose.x, pose.y);
      const isDocked = nearest.node === "foyer" && nearest.dist < 0.35;
      const status = inferStatus(data.task, nearest.room, isDocked);

      const tiago: RobotDevice = {
        id: "tiago",
        name: "TIAGo",
        model: "PAL Robotics TIAGo",
        type: "Mobile Manipulator",
        status,
        current_room: nearest.room,
        current_node: nearest.node,
        battery_pct: Math.round(data.battery ?? 85),
        pose: {
          x: pose.x,
          y: pose.y,
          theta: pose.theta,
        },
        target_destination: data.task?.includes("navigating to")
          ? data.task.replace("navigating to", "").trim()
          : null,
        arm_pose: data.arm_pose || "home",
        gripper: (data.gripper as "open" | "closed") || "open",
        held_object: data.held_object || "",
        task_description: data.task || "idle",
        online: true,
      };

      return NextResponse.json([tiago]);
    }
  } catch {
    // Port 8001 unavailable, fallback to Smart Home supervisor (Port 8000)
  }

  // 2. Fallback to Smart Home Hub supervisor rover endpoint (Port 8000)
  try {
    const res = await fetch(`${HUB_URL}/api/rover`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1200),
    });
    if (res.ok) {
      const data = await res.json();
      const pos = data.position || [-3.1, -7.62, 0.1];
      const tiago: RobotDevice = {
        id: "tiago",
        name: "TIAGo",
        model: "PAL Robotics TIAGo",
        type: "Mobile Manipulator",
        status: data.status || "Docked",
        current_room: data.current_room || "Foyer",
        current_node: data.current_node || "foyer",
        battery_pct: data.battery_pct ?? 90,
        pose: {
          x: pos[0],
          y: pos[1],
          theta: data.heading_rad ?? 1.57,
        },
        target_destination: data.target_destination || null,
        arm_pose: data.arm_pose || "home",
        gripper: data.gripper === "grip" ? "closed" : "open",
        held_object: "",
        task_description: data.status === "Navigating" ? `navigating to ${data.target_destination}` : "idle",
        online: true,
      };

      return NextResponse.json([tiago]);
    }
  } catch {
    // Both ports unavailable
  }

  // 3. Fallback standby state
  const fallbackTiago: RobotDevice = {
    id: "tiago",
    name: "TIAGo",
    model: "PAL Robotics TIAGo",
    type: "Mobile Manipulator",
    status: "Docked",
    current_room: "Foyer",
    current_node: "foyer",
    battery_pct: 88,
    pose: { x: -3.1, y: -7.5, theta: 1.57 },
    target_destination: null,
    arm_pose: "home",
    gripper: "open",
    held_object: "",
    task_description: "idle",
    online: false,
  };

  return NextResponse.json([fallbackTiago]);
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { action, destination, pose, gripper_state, target } = body;

    // Direct TIAGo controller endpoint dispatch
    if (action === "navigate" && destination) {
      try {
        const res = await fetch(`${TIAGO_URL}/navigate/room`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ room: destination }),
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) return NextResponse.json(await res.json());
      } catch {
        // Fallback to hub
        const hubRes = await fetch(`${HUB_URL}/api/rover/navigate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ destination }),
        });
        return NextResponse.json(await hubRes.json());
      }
    }

    if (action === "stop") {
      try {
        const res = await fetch(`${TIAGO_URL}/stop`, {
          method: "POST",
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) return NextResponse.json(await res.json());
      } catch {
        // Fallback to hub
        const hubRes = await fetch(`${HUB_URL}/api/rover/control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "stop" }),
        });
        return NextResponse.json(await hubRes.json());
      }
    }

    if (action === "arm" && pose) {
      try {
        const res = await fetch(`${TIAGO_URL}/arm/pose`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pose }),
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) return NextResponse.json(await res.json());
      } catch {
        const hubRes = await fetch(`${HUB_URL}/api/rover/control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "arm", arm_pose: pose }),
        });
        return NextResponse.json(await hubRes.json());
      }
    }

    if (action === "gripper" && gripper_state) {
      try {
        const res = await fetch(`${TIAGO_URL}/gripper/set`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ state: gripper_state }),
          signal: AbortSignal.timeout(2000),
        });
        if (res.ok) return NextResponse.json(await res.json());
      } catch {
        const hubRes = await fetch(`${HUB_URL}/api/rover/control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "gripper",
            gripper_state: gripper_state === "closed" ? "grip" : "release",
          }),
        });
        return NextResponse.json(await hubRes.json());
      }
    }

    if (action === "head" && target) {
      const res = await fetch(`${TIAGO_URL}/head/look_at`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target }),
        signal: AbortSignal.timeout(2000),
      });
      return NextResponse.json(await res.json());
    }

    return NextResponse.json({ success: true });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Robot action failed";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
