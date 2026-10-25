# Blender JSON Socket Server Add-on (v2.0)

A lightweight, non-blocking asynchronous TCP socket server add-on engineered for **Blender (4.0+)**. It allows external multi-agent frameworks, automated test suites, or external IDEs to control Blender via structured JSON payloads without ever freezing or locking up the user interface.

## 🚀 Key Improvements in v2.0
- **Zero Raw Execution:** Replaced dangerous `exec()` and plain text methods with a strict action-based JSON router.
- **Bi-directional JSON Communication:** Every request and response follows a rigid JSON contract, terminated by a newline (`\n`) delimiter.
- **Robust Exception Marshalling:** Server-side Python errors are captured, categorized, and safely packaged into error dictionaries rather than causing socket crashes.
- **Full Tool Suite Integration:** Built-in endpoint handlers mapped to accommodate 9 essential automation tools (mesh instantiation, material creation, scene queries, transformations, and rendering setups).

---

## 📥 Installation

1. Copy the updated code and save it locally as `blender_json_server.py`.
2. Launch Blender.
3. Open **Edit > Preferences** and select the **Add-ons** tab.
4. Click **Install...** in the upper-right corner and select your `blender_json_server.py` file.
5. Check the box next to **Development: Blender JSON Socket Server** to activate it.

---

## 🕹️ How to Use

1. Inside Blender's 3D Viewport, press the **`N`** key to unfold the right-hand sidebar.
2. Select the **Socket Server** tab.
3. Click the **Start Target API Server** button.
   * *The server will immediately spin up and begin polling on local address `127.0.0.1` at port `65432`.*

---

## 📡 Protocol Specification & Interaction

Every incoming stream packet must be a valid serialized JSON object formatted as a single line, ending strictly with a newline byte (`\n`). 

### Packet Structure
```json
{
  "action": "action_name",
  "params": { "param_key": "param_value" }
}
```

### Response Structure
```json
{
  "success": true, 
  "result": { "status": "operation_completed" }
}
```
*(In case of failure, `success` returns `false` along with an explicit `error` key outlining the exact Python exception).*

---

## 💻 Connection Examples

### Option A: External Tool Python Library Client (`client.py`)
Run this standalone test script to verify endpoint routing directly against your live Blender instance:

```python
import socket
import json

def send_action(action, params=None):
    host = '127.0.0.1'
    port = 65432
    payload = {
        "action": action,
        "params": params or {}
    }
    
    # Serialize to JSON and append the mandatory newline delimiter
    raw_message = json.dumps(payload) + "\n"
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(raw_message.encode('utf-8'))
        
        # Read the incoming stream line response
        response_bytes = b""
        while not response_bytes.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            response_bytes += chunk
            
        return json.loads(response_bytes.decode('utf-8').strip())

# 1. Ping the server to check connectivity
print("Ping:", send_action("ping"))

# 2. Spawn a custom cylinder in the viewport
print("Add Object:", send_action("add_object", {"object_type": "cylinder", "name": "Engine_Core"}))

# 3. Position the new object in 3D space
print("Move Object:", send_action("set_object_location", {"name": "Engine_Core", "x": 0.0, "y": 2.5, "z": -1.2}))
```

### Option B: Terminal / Command Line Piping
You can push raw network strings natively using `netcat` (`nc`) in Linux, macOS, or Git Bash. Ensure the string contains an explicit newline syntax:

```bash
# Verify connection (Ping)
echo '{"action": "ping"}' | nc 127.0.0.1 65432

# Query the current active scene hierarchy and active objects
echo '{"action": "get_scene_info"}' | nc 127.0.0.1 65432

# Wipe out meshes, cameras, and lights to start clean
echo '{"action": "clear_scene"}' | nc 127.0.0.1 65432
```

---

## 🛠️ Supported Router Actions

The `v2.0` server handles the following standard actions natively:
* `ping`: System heartbeat query returning the active Blender software version string.
* `clear_scene`: Deletes meshes, lamps, and cameras from the active view layer.
* `get_scene_info`: Gathers names, object types, rendering engine parameters, and active selections.
* `add_object`: Spawns primitives (`cube`, `sphere`, `cylinder`, `cone`) with an optional custom `name`.
* `remove_object`: Deletes a targeted object from the scene by its precise string identifier.
* `set_object_location`: Multi-axis structural placement translation via `x`, `y`, and `z` vectors.
* `create_material`: Generates a fully compiled node-based Cycles/Eevee material block.
* `assign_material`: Pairs an existing material block to a designated mesh object.
* `set_camera_view`: Dynamically positions and rotates target cameras for rendering coordinates.
* `render_scene`: Triggers background viewport rendering engine jobs and writes files locally.

## ⚠️ Security Notice
The socket binds by default to `127.0.0.1` (**localhost**). This restricts all networking pipelines purely to transactions originating locally from your own computer. Avoid binding to `0.0.0.0` or opening public ports unless you are isolating the instances inside encrypted subnets, as unauthorized local network packets could execute custom programmatic adjustments to your system data through Blender.
