# Blender Socket Server Add-on

A lightweight, non-blocking TCP socket server add-on built for **Blender (4.0+)**. It allows external applications, independent Python scripts, or terminal commands to control Blender in real-time without freezing or locking up the user interface.

## 🚀 Features
- **Non-blocking Loop:** Utilizes Blender's `bpy.app.timers` to listen for incoming connections asynchronously.
- **Built-in UI:** Adds a clean control panel inside the 3D Viewport sidebar (N-panel).
- **Out-of-the-box Commands:** Includes basic demo commands to spawn meshes remotely.

---

## 📥 Installation

1. Download or copy the `blender_server_addon.py` file to your computer.
2. Open Blender.
3. Go to **Edit > Preferences** and select the **Add-ons** tab.
4. Click **Install...** in the top-right corner and select your `blender_server_addon.py` file.
5. Check the box next to **Development: Blender Socket Server** to enable it.

---

## 🕹️ How to Use

1. Inside the Blender 3D Viewport, press the **`N`** key to open the right-hand sidebar.
2. Click on the **Socket Server** tab.
3. Click the **Start Server** button.
   * *The server is now live and listening on local address `127.0.0.1` at port `65432`.*

---

## 📡 Testing the Connection (Examples)

You can send raw text data to the server to trigger actions inside Blender. Here are two ways to test it:

### Option A: Via an external Python script (`client.py`)
Create a separate script on your machine to send a remote command:

```python
import socket

def send_command(command):
    host = '127.0.0.1'
    port = 65432
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(command.encode('utf-8'))
        response = s.recv(1024).decode('utf-8')
        print(f"Blender response: {response}")

# Send the command to spawn a cube
send_command("cube")
```

### Option B: Via Terminal / Command Line
Use `netcat` (`nc`) in Linux, macOS, or Git Bash to pipe a string directly into the socket:

```bash
# Spawn a cube
echo "cube" | nc 127.0.0.1 65432

# Spawn a UV sphere
echo "sphere" | nc 127.0.0.1 65432
```

---

## 🛠️ Customizing Commands

To map your own functions, open the add-on script and modify the conditional checks inside the `check_incoming_data()` function. You can catch new keywords like this:

```python
if data == "my_custom_action":
    # Insert your Blender Python API calls here
    bpy.ops.render.render(write_still=True)
    conn.sendall(b"Render completed successfully!\n")
```

## ⚠️ Security Warning
By default, the server binds to `127.0.0.1` (**localhost**), meaning it only accepts connections originating from your local machine. Do not change this host to `0.0.0.0` unless you are on a trusted local area network, as it allows any device on the network to send commands to your Blender instance.
