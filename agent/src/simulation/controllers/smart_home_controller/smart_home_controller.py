import threading
import queue
import uvicorn
import time
import io
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import cast
from controller import Supervisor, Camera
from PIL import Image

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)

supervisor = Supervisor()
TIME_STEP = int(supervisor.getBasicTimeStep())
command_queue = queue.Queue()

light_nodes = {}
LIGHT_TYPES = ['CeilingLight', 'FloorLight', 'CeilingSpotLight']

cameras = {}
camera_frames = {}

# Add this list near your other constants at the top of the file
CAMERA_NAMES = [
    "Living Room Camera",
    "Kitchen Camera",
    "Bedroom Camera",
    "Front Door Camera"
]

def update_devices_cache():
    global light_nodes, cameras
    
    # 1. Cache Lights via ID scan
    for i in range(100000):
        node = supervisor.getFromId(i)
        if node and node.getTypeName() in LIGHT_TYPES:
            light_nodes[node.getId()] = node
                
    # 2. Cache Cameras by explicitly fetching them by name
    for name in CAMERA_NAMES:
        device = supervisor.getDevice(name)
        if device:
            # Tell the linter this is specifically a Camera
            cam = cast(Camera, device) 
            cam.enable(TIME_STEP)
            cameras[name] = cam
            camera_frames[name] = None
            
    print(f"Cached {len(light_nodes)} lights and {len(cameras)} cameras.")

# --- API ENDPOINTS ---

@app.get("/api/lights")
def get_lights():
    lights = []
    for node_id, node in light_nodes.items():
        type_name = node.getTypeName()
        name_field = node.getField('name')
        name = name_field.getSFString() if name_field else type_name
        
        i_field = node.getField('spotLightIntensity') if type_name == 'CeilingSpotLight' else node.getField('pointLightIntensity')
        intensity = i_field.getSFFloat() if i_field else 0
        
        lights.append({
            "id": node_id,
            "name": name,
            "state": "On" if intensity > 0 else "Off",
            "metadata": f"Intensity at {intensity:.1f}",
            "type": type_name
        })
    return lights

@app.post("/api/lights/{node_id}/toggle")
def toggle_light(node_id: int):
    if node_id not in light_nodes:
        return {"error": "Light not found"}
    command_queue.put({"action": "toggle", "node_id": node_id})
    return {"status": "command_queued"}

@app.get("/api/cameras")
def get_cameras():
    return [
        {
            "id": name,
            "name": name,
            "state": "Online",
            "metadata": f"Live • {cam.getWidth()}x{cam.getHeight()}",
            "type": "Camera"
        }
        for name, cam in cameras.items()
    ]

def generate_camera_stream(name: str):
    cam = cameras.get(name)
    if not cam:
        return
        
    width = cam.getWidth()
    height = cam.getHeight()
    
    while True:
        raw = camera_frames.get(name)
        if raw:
            try:
                # Convert Webots raw BGRA bytes to JPEG
                img = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
                buf = io.BytesIO()
                img.convert('RGB').save(buf, format='JPEG', quality=60)
                frame = buf.getvalue()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception:
                pass
        time.sleep(0.05) # ~20 FPS limit

@app.get("/api/cameras/{name}/stream")
def camera_stream(name: str):
    return StreamingResponse(generate_camera_stream(name), media_type="multipart/x-mixed-replace; boundary=frame")


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    update_devices_cache()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("Smart Home Controller running on http://127.0.0.1:8000")
    
    while supervisor.step(TIME_STEP) != -1:
        # Update camera image cache each tick
        for name, cam in cameras.items():
            img = cam.getImage()
            if img:
                camera_frames[name] = img
                
        # Process light toggles
        while not command_queue.empty():
            cmd = command_queue.get()
            if cmd["action"] == "toggle":
                node = light_nodes.get(cmd["node_id"])
                if node:
                    type_name = node.getTypeName()
                    i_field = node.getField('spotLightIntensity') if type_name == 'CeilingSpotLight' else node.getField('pointLightIntensity')
                    if i_field:
                        current = i_field.getSFFloat()
                        i_field.setSFFloat(0.0 if current > 0 else 3.0)