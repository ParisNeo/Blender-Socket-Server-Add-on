# Blender JSON Socket Server Add-on (v2.4)

A robust, non-blocking asynchronous TCP socket server add-on engineered for **Blender (4.0+)**. It allows external multi-agent frameworks, automated test suites, or external IDEs to control Blender via structured JSON payloads without ever freezing or locking up the user interface.

## 🚀 Key Improvements in v2.4
- **Hardened Asynchronous Loop:** Fixed a critical loop crash where `BlockingIOError` would propagate and kill Blender's timer loop when no clients were waiting. The server now safely polls indefinitely.
- **Fixed Render Resolution Typo:** Corrected an internal duplicate property assignment bug that prevented the `height` parameter from being applied properly to the render engine.
- **Bi-directional JSON Communication:** Every request and response follows a rigid JSON contract, terminated strictly by a newline (`\n`) delimiter.
- **Robust Exception Marshalling:** Server-side Python errors are captured, categorized, and safely packaged into error dictionaries rather than causing socket crashes.
- **Full Tool Suite Integration:** Built-in endpoint handlers mapped to accommodate 9 essential automation tools (mesh instantiation, material creation, scene queries, transformations, and rendering setups).

---

## 📥 Installation

1. Copy the updated server code and save it locally as `blender_json_server.py`.
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

## 💻 Full Connection & Render Example

Since the client and Blender run on the same machine (`127.0.0.1`), they share the same hard drive. The cleanest way to receive a rendered image is to have Blender save it to a shared temporary directory (`/tmp`) and have the client read it right after getting a successful JSON response.

### External Tool Python Client (`client_render.py`)
Run this standalone test script to trigger a scene render and fetch the raw image bytes:

```python
import socket
import json
import os

def render_and_get_image(output_filename="api_render.png"):
    host = '127.0.0.1'
    port = 65432
    
    # Define a shared temporary path depending on the OS
    target_dir = "/tmp" if os.name != "nt" else os.environ.get("TEMP", "C:\\TEMP")
    absolute_target_path = os.path.join(target_dir, output_filename)
    
    # 1. Prepare the structured JSON payload
    payload = {
        "action": "render_scene",
        "params": {
            "output_path": absolute_target_path,
            "width": 640,
            "height": 480,
            "engine": "BLENDER_WORKBENCH"
        }
    }
    
    raw_message = json.dumps(payload) + "\n"
    
    # 2. Send the render command to Blender
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(raw_message.encode('utf-8'))
        
        # Read the single line JSON stream response
        response_bytes = b""
        while not response_bytes.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            response_bytes += chunk
            
        response = json.loads(response_bytes.decode('utf-8').strip())
    
    # 3. Process the server output
    if response.get("success"):
        saved_path = response["result"]["output_path"]
        print(f"Blender successfully rendered to: {saved_path}")
        
        # 4. Fetch the binary image data directly from the disk!
        with open(saved_path, "rb") as image_file:
            binary_image_data = image_file.read()
            
        print(f"Client retrieved the image! Size: {len(binary_image_data)} bytes.")
        return binary_image_data
    else:
        print(f"Render failed: {response.get('error')}")
        return None

if __name__ == "__main__":
    image_bytes = render_and_get_image()
```

---

## 🛠️ Supported Router Actions

The `v2.4` server handles the following standard actions natively:
* `ping`: System heartbeat query returning the active Blender software version string.
* `clear_scene`: Deletes meshes, lamps, and cameras from the active view layer.
* `get_scene_info`: Gathers names, upper-case object types, rendering engine parameters, and active selections.
* `add_object`: Spawns primitives (`cube`, `sphere`, `cylinder`, `cone`) with an optional custom `name` and exact data contract outputs.
* `remove_object`: Deletes a targeted object from the scene by its precise string identifier.
* `set_object_location`: Multi-axis structural placement translation via `x`, `y`, and `z` vectors.
* `create_material`: Generates a fully compiled node-based material block supporting custom `base_color`, `metallic`, and `roughness`.
* `assign_material`: Pairs an existing material block to a designated mesh object.
* `set_camera_view`: Dynamically positions and rotates target cameras toward a specified 3D target coordinate.
* `render_scene`: Triggers background viewport rendering engine jobs, handling resolution dimensions and absolute output directory mapping.

## ⚠️ Security Notice
The socket binds by default to `127.0.0.1` (**localhost**). This restricts all networking pipelines purely to transactions originating locally from your own computer. Avoid binding to `0.0.0.0` or opening public ports unless you are isolating the instances inside encrypted subnets, as unauthorized local network packets could execute custom programmatic adjustments to your system data through Blender.
