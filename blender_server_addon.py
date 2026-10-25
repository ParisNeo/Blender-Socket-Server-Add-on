bl_info = {
    "name": "Blender JSON Socket Server",
    "author": "AI Assistant & QA Harness",
    "version": (2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Socket Server",
    "description": "Serveur TCP JSON asynchrone et sécurisé pour l'exécution d'outils distants.",
    "category": "Development",
}

import bpy
import socket
import json

_server_socket = None
_is_running = False

# --- Fonctions d'aide (Helpers) associées à vos 9 outils ---

def _clear_scene():
    # Supprime tous les objets de type Mesh, Light et Camera de la scène active
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    return {"status": "Scene cleared successfully"}

def _get_scene_info():
    # Renvoie la liste des objets et la configuration de rendu actuelle
    objects = [{"name": obj.name, "type": obj.type} for obj in bpy.context.scene.objects]
    return {
        "blender_version": bpy.app.version_string,
        "active_object": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
        "objects": objects,
        "engine": bpy.context.scene.render.engine
    }

def _add_object(params):
    obj_type = params.get("object_type", "cube").lower()
    name = params.get("name", obj_type.capitalize())
    
    if obj_type == "cube":
        bpy.ops.mesh.primitive_cube_add()
    elif obj_type == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add()
    elif obj_type == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add()
    elif obj_type == "cone":
        bpy.ops.mesh.primitive_cone_add()
    else:
        raise ValueError(f"Unsupported object type: {obj_type}")
        
    created_obj = bpy.context.view_layer.objects.active
    created_obj.name = name
    return {"object_name": created_obj.name, "object_type": obj_type, "status": "created"}

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
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    # Configuration rapide de la couleur de base BSDF
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled:
        color = params.get("color", [0.8, 0.8, 0.8, 1.0]) # RGBA
        principled.inputs[0].default_value = color
    return {"material_name": mat.name, "status": "created"}

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
        obj.data.materials[0] = mat
    return {"status": f"Material '{mat_name}' assigned to '{obj_name}'"}

def _set_camera_view(params):
    # Configure la position et la rotation de la caméra principale
    cam_name = params.get("name", "Camera")
    if cam_name in bpy.data.objects:
        cam = bpy.data.objects[cam_name]
        if "location" in params:
            cam.location = params["location"]
        if "rotation" in params:
            cam.rotation_euler = params["rotation"]
        return {"camera_name": cam_name, "status": "updated"}
    raise KeyError(f"Camera '{cam_name}' not found")

def _render_scene(params):
    # Lance un rendu en arrière-plan et sauvegarde l'image cible
    filepath = params.get("filepath", "//render.png")
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    return {"status": "Render completed", "filepath": bpy.path.abspath(filepath)}

# --- Table de routage des actions ---
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

# --- Boucle Réseau Non-Bloquante ---

def check_incoming_data():
    global _server_socket, _is_running
    if not _is_running or _server_socket is None:
        return None # Tue le timer proprement
        
    try:
        while True:
            try:
                conn, addr = _server_socket.accept()
            except BlockingIOError:
                break # Plus aucune connexion en attente pour cette itération du timer
                
            try:
                conn.settimeout(2.0)
                data = b""
                # Accumulation des données jusqu'au marqueur de fin de ligne (\n)
                while not data.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                    
                if not data:
                    continue
                    
                try:
                    # Traitement de la requête JSON
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
                    
                # Renvoi de la réponse encodée en JSON, terminée par un \n
                conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
                
            except Exception as e:
                print(f"[Server] Client Connection Error: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    except Exception as e:
        print(f"[Server] Loop Error: {e}")
        
    return 0.1 # Relance l'évaluation dans 100ms

# --- Interface Utilisateur & Enregistrement Blender ---

class WM_OT_StartJsonServer(bpy.types.Operator):
    bl_idname = "wm.start_json_server"
    bl_label = "Démarrer le Serveur API"
    
    def execute(self, context):
        global _server_socket, _is_running
        if _is_running:
            self.report({'INFO'}, "Le serveur tourne déjà.")
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
            self.report({'INFO'}, f"Serveur JSON actif sur {host}:{port}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Échec de l'initialisation : {e}")
            return {'CANCELLED'}

class WM_OT_StopJsonServer(bpy.types.Operator):
    bl_idname = "wm.stop_json_server"
    bl_label = "Arrêter le Serveur API"
    
    def execute(self, context):
        global _server_socket, _is_running
        if not _is_running:
            return {'CANCELLED'}
            
        _is_running = False
        if _server_socket:
            _server_socket.close()
            _server_socket = None
        self.report({'INFO'}, "Serveur API arrêté.")
        return {'FINISHED'}

class VIEW3D_PT_JsonServerPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Socket Server'
    bl_label = "Contrôle API Rigide"

    def draw(self, context):
        layout = self.layout
        global _is_running
        col = layout.column(align=True)
        if not _is_running:
            col.operator("wm.start_json_server", icon='PLAY')
        else:
            col.operator("wm.stop_json_server", icon='PAUSE')
            col.label(text="En attente de requêtes JSON...", icon='RADIO')

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
