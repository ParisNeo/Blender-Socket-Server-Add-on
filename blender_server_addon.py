bl_info = {
    "name": "Blender JSON Socket Server",
    "author": "AI Assistant & QA Harness",
    "version": (2, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Socket Server",
    "description": "Asynchronous TCP JSON Server for remote tool execution.",
    "category": "Development",
}

import bpy
import socket
import json
import mathutils

_server_socket = None
_is_running = False

# --- Route Table & Action Helpers ---

def _clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    return {"status": "Scene cleared successfully"}

def _get_scene_info():
    scene = bpy.context.scene
    objects = []
    
    for obj in scene.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type.upper(),
            "location": list(obj.location)
        })
        
    camera_name = scene.camera.name if scene.camera else None
    
    return {
        "scene_name": scene.name,
        "object_count": len(scene.objects),
        "camera_name": camera_name,
        "objects": objects,
        "engine": scene.render.engine,
        "blender_version": bpy.app.version_string
    }

def _add_object(params):
    obj_type = params.get("object_type", "CUBE").lower()
    name = params.get("name", obj_type.capitalize())
    location = params.get("location", [0.0, 0.0, 0.0])
    
    if obj_type == "cube":
        bpy.ops.mesh.primitive_cube_add(location=location)
    elif obj_type in ["sphere", "uv_sphere"]:
        bpy.ops.mesh.primitive_uv_sphere_add(location=location)
        obj_type = "sphere"
    elif obj_type == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(location=location)
    elif obj_type == "cone":
        bpy.ops.mesh.primitive_cone_add(location=location)
    else:
        raise ValueError(f"Unsupported object type: {obj_type}")
        
    created_obj = bpy.context.view_layer.objects.active
    created_obj.name = name
    
    return {
        "object_name": created_obj.name,
        "object_type": obj_type.upper(),
        "location": list(created_obj.location),
        "status": "created"
    }

def _remove_object(params):
    name = params.get("name")
    if name in bpy.data.objects:
        obj = bpy.data.objects[name]
        bpy.data.objects.remove(obj, do_unlink=True)
        return {"status": f"Object '{name}' removed"}
    raise KeyError(f"Object '{name}' not found in scene")

def _set_object_location(params):
    name = params.get("name")
    if name in bpy.data.objects:
        obj = bpy.data.objects[name]
        obj.location = (float(params.get("x", 0)), float(params.get("y", 0)), float(params.get("z", 0)))
        return {"object_name": name, "new_location": list(obj.location)}
    raise KeyError(f"Object '{name}' not found")

def _create_material(params):
    name = params.get("name", "NewMaterial")
    base_color = params.get("base_color", [0.8, 0.8, 0.8, 1.0])
    
    if len(base_color) == 3:
        base_color = list(base_color) + [1.0]
        
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled:
        principled.inputs.get("Base Color").default_value = base_color
        if "metallic" in params:
            principled.inputs.get("Metallic").default_value = float(params["metallic"])
        if "roughness" in params:
            principled.inputs.get("Roughness").default_value = float(params["roughness"])
            
    return {
        "material_name": mat.name,
        "base_color": base_color,
        "status": "created"
    }

def _assign_material(params):
    obj_name = params.get("object_name")
    mat_name = params.get("material_name")
    
    if obj_name not in bpy.data.objects:
        raise KeyError(f"Object '{obj_name}' not found")
    if mat_name not in bpy.data.materials:
        raise KeyError(f"Material '{mat_name}' not found")
        
    obj = bpy.data.objects[obj_name]
    mat = bpy.data.materials[mat_name]
    
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials = mat
    return {"status": f"Material '{mat_name}' assigned to '{obj_name}'"}

def _set_camera_view(params):
    cam_name = params.get("name", "Camera")
    if cam_name not in bpy.data.objects:
        if bpy.context.scene.camera:
            cam = bpy.context.scene.camera
            cam_name = cam.name
        else:
            raise KeyError(f"Camera '{cam_name}' not found and no active camera setup.")
    else:
        cam = bpy.data.objects[cam_name]
        
    if "location" in params:
        cam.location = params["location"]
        
    if "target" in params:
        target_loc = mathutils.Vector(params["target"])
        direction = target_loc - cam.location
        if direction.length > 0.0001:
            cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        
    return {
        "camera_name": cam_name,
        "camera_location": list(cam.location),
        "status": "updated"
    }

def _render_scene(params):
    scene = bpy.context.scene
    
    output_path = params.get("output_path", params.get("filepath", "/tmp/render.png"))
    scene.render.filepath = bpy.path.abspath(output_path)
    
    if "width" in params:
        scene.render.resolution_x = int(params["width"])
    if "height" in params:
        scene.render.resolution_y = int(params["height"])
        
    if "engine" in params:
        engine_map = {
            "BLENDER_WORKBENCH": "BLENDER_WORKBENCH",
            "CYCLES": "CYCLES",
            "BLENDER_EEVEE": "BLENDER_EEVEE",
            "BLENDER_EEVEE_NEXT": "BLENDER_EEVEE_NEXT"
        }
        requested_engine = params["engine"].upper()
        if requested_engine in engine_map:
            scene.render.engine = engine_map[requested_engine]

    bpy.ops.render.render(write_still=True)
    
    return {
        "status": "Render completed",
        "output_path": scene.render.filepath
    }

# --- API Router Layout ---
_ACTIONS = {
    "ping": lambda p: {"blender_version": bpy.app.version_string, "status": "alive"},
    "clear_scene": lambda p: _clear_scene(),
    "get_scene_info": lambda p: _get_scene_info(),
    "add_object": lambda p: _add_object(p),
    "remove_object": lambda p: _remove_object(p),
    "set_object_location": lambda p: _set_object_location(p),
    "create_material": lambda p: _create_material(p),
    "assign_material": lambda p: _assign_material(p),
    "set_camera_view": lambda p: _set_camera_view(p),
    "render_scene": lambda p: _render_scene(p),
}

# --- Asynchronous Networking Loop ---

def check_incoming_data():
    global _server_socket, _is_running
    if not _is_running or _server_socket is None:
        return None  # Arrête proprement le timer si le serveur est désactivé
        
    try:
        while True:
            try:
                # Interception immédiate du non-bloquant s'il n'y a pas de client
                conn, addr = _server_socket.accept()
            except BlockingIOError:
                break  # Sortie propre de la boucle : aucun client en attente pour cette itération
                
            try:
                conn.settimeout(2.0)
                data = b""
                # Accumulation sécurisée des données jusqu'au saut de ligne
                while not data.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    
                if not data:
                    conn.close()
                    continue
                    
                try:
                    msg = json.loads(data.decode("utf-8").strip())
                    action = msg.get("action")
                    params = msg.get("params", {})
                    
                    if action in _ACTIONS:
                        result = _ACTIONS[action](params)
                        resp = {"success": True, "result": result}
                    else:
                        resp = {"success": False, "error": f"Unknown action: {action}"}
                        
                except Exception as e:
                    resp = {"success": False, "error": f"{type(e).__name__}: {e}"}
                    
                # Renvoi de la réponse JSON au client
                conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
                
            except Exception as e:
                print(f"[Server] Client Connection Error: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                    
    except Exception as e:
        print(f"[Server] Global Loop Error: {e}")
        
    return 0.1  # Rappelle la fonction dans 100ms


# --- User Interface & Lifetime Registration ---

class WM_OT_StartJsonServer(bpy.types.Operator):
    bl_idname = "wm.start_json_server"
    bl_label = "Start API Server"
    
    def execute(self, context):
        global _server_socket, _is_running
        if _is_running:
            self.report({'INFO'}, "Server is already running.")
            return {'CANCELLED'}
            
        host, port = '127.0.0.1', 65432
        try:
            _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _server_socket.bind((host, port))
            _server_socket.listen()
            _server_socket.setblocking(False)
            
            _is_running = True
            bpy.app.timers.register(check_incoming_data)
            self.report({'INFO'}, f"JSON Server live on {host}:{port}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Initialization Failed: {e}")
            return {'CANCELLED'}

class WM_OT_StopJsonServer(bpy.types.Operator):
    bl_idname = "wm.stop_json_server"
    bl_label = "Stop API Server"
    
    def execute(self, context):
        global _server_socket, _is_running
        if not _is_running:
            return {'CANCELLED'}
            
        _is_running = False
        if _server_socket:
            _server_socket.close()
            _server_socket = None
        self.report({'INFO'}, "API Server Stopped.")
        return {'FINISHED'}

class VIEW3D_PT_JsonServerPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Socket Server'
    bl_label = "Rigid API Control v2.3"

    def draw(self, context):
        layout = self.layout
        global _is_running
        col = layout.column(align=True)
        if not _is_running:
            col.operator("wm.start_json_server", icon='PLAY')
        else:
            col.operator("wm.stop_json_server", icon='PAUSE')
            col.label(text="Listening for JSON requests...", icon='RADIO')

classes = (WM_OT_StartJsonServer, WM_OT_StopJsonServer, VIEW3D_PT_JsonServerPanel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    global _is_running, _server_socket
    _is_running = False
    if _server_socket:
        _server_socket.close()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
