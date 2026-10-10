import threading
import queue
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controller import Supervisor

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)

supervisor = Supervisor()
TIME_STEP = int(supervisor.getBasicTimeStep())
command_queue = queue.Queue()

# Cache to store light node references and default intensities
light_nodes = {}
LIGHT_TYPES = ['CeilingLight', 'FloorLight', 'CeilingSpotLight']

def update_lights_cache():
    global light_nodes
    
    # The Webots Python Field class lacks getMFNode(). 
    # Since Webots assigns Node IDs sequentially on load, scanning 
    # a reasonable ID range bypasses the API limitation and seamlessly 
    # catches lights deeply nested inside Pose groups.
    for i in range(100000):
        node = supervisor.getFromId(i)
        if node:
            type_name = node.getTypeName()
            if type_name in LIGHT_TYPES:
                light_nodes[node.getId()] = node
                
    print(f"Cached {len(light_nodes)} lights across the home.")

@app.get("/api/lights")
def get_lights():
    lights = []
    for node_id, node in light_nodes.items():
        type_name = node.getTypeName()
        name_field = node.getField('name')
        name = name_field.getSFString() if name_field else type_name
        
        intensity_field = node.getField('spotLightIntensity') if type_name == 'CeilingSpotLight' else node.getField('pointLightIntensity')
        intensity = intensity_field.getSFFloat() if intensity_field else 0
        
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

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    update_lights_cache()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    print("Smart Home Controller running on http://127.0.0.1:8000")
    
    while supervisor.step(TIME_STEP) != -1:
        while not command_queue.empty():
            cmd = command_queue.get()
            if cmd["action"] == "toggle":
                node = light_nodes.get(cmd["node_id"])
                if node:
                    type_name = node.getTypeName()
                    i_field = node.getField('spotLightIntensity') if type_name == 'CeilingSpotLight' else node.getField('pointLightIntensity')
                    
                    if i_field:
                        current = i_field.getSFFloat()
                        # Default to intensity 3.0 when turning back on
                        i_field.setSFFloat(0.0 if current > 0 else 3.0)