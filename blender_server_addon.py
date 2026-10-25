bl_info = {
    "name": "Blender Socket Server",
    "author": "AI Assistant",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Server Tab",
    "description": "Lance un serveur socket non-bloquant pour contrôler Blender",
    "category": "Development",
}

import bpy
import socket

# Variables globales pour suivre l'état du serveur
_server_socket = None
_is_running = False

def check_incoming_data():
    global _server_socket, _is_running
    
    if not _is_running or _server_socket is None:
        return None # Arrête définitivement le timer de Blender
        
    try:
        # Tente d'accepter une connexion sans bloquer l'UI
        conn, addr = _server_socket.accept()
        data = conn.recv(1024).decode('utf-8').strip()
        
        if data:
            print(f"[Server] Reçu : {data}")
            # Exemple de commandes basiques
            if data == "cube":
                bpy.ops.mesh.primitive_cube_add()
                conn.sendall(b"Cube cree avec succes!\n")
            elif data == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add()
                conn.sendall(b"Sphere cree avec succes!\n")
            else:
                conn.sendall(b"Commande inconnue\n")
                
        conn.close()
    except BlockingIOError:
        pass # Pas de connexion entrante à cet instant
    except Exception as e:
        print(f"[Server] Erreur de lecture : {e}")
        
    return 0.1 # S'exécute à nouveau dans 0.1 seconde

class WM_OT_StartServer(bpy.types.Operator):
    """Démarrer le serveur Socket"""
    bl_idname = "wm.start_socket_server"
    bl_label = "Démarrer le Serveur"
    
    def execute(self, context):
        global _server_socket, _is_running
        
        if _is_running:
            self.report({'INFO'}, "Le serveur tourne déjà.")
            return {'CANCELLED'}
            
        host = '127.0.0.1'
        port = 65432
        
        try:
            _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Permet de réutiliser le port immédiatement après la fermeture
            _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _server_socket.bind((host, port))
            _server_socket.listen()
            _server_socket.setblocking(False)
            
            _is_running = True
            # Enregistre la fonction dans la boucle de Blender
            bpy.app.timers.register(check_incoming_data)
            
            self.report({'INFO'}, f"Serveur lancé sur {host}:{port}")
            print(f"[Server] Lancé sur {host}:{port}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Impossible de lancer le serveur : {e}")
            return {'CANCELLED'}

class WM_OT_StopServer(bpy.types.Operator):
    """Arrêter le serveur Socket"""
    bl_idname = "wm.stop_socket_server"
    bl_label = "Arrêter le Serveur"
    
    def execute(self, context):
        global _server_socket, _is_running
        
        if not _is_running:
            self.report({'INFO'}, "Le serveur est déjà arrêté.")
            return {'CANCELLED'}
            
        _is_running = False
        
        if _server_socket:
            _server_socket.close()
            _server_socket = None
            
        self.report({'INFO'}, "Serveur arrêté.")
        print("[Server] Arrêté.")
        return {'FINISHED'}

class VIEW3D_PT_SocketServerPanel(bpy.types.Panel):
    """Crée un onglet dans le panneau latéral (N) de la vue 3D"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Socket Server'
    bl_label = "Contrôle du Serveur"

    def draw(self, context):
        layout = self.layout
        global _is_running
        
        col = layout.column(align=True)
        if not _is_running:
            col.operator("wm.start_socket_server", icon='PLAY')
        else:
            col.operator("wm.stop_socket_server", icon='PAUSE')
            col.label(text="Serveur actif sur le port 65432", icon='RADIO')

classes = (
    WM_OT_StartServer,
    WM_OT_StopServer,
    VIEW3D_PT_SocketServerPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    global _is_running, _server_socket
    # Sécurité si on désactive l'add-on à la volée
    _is_running = False
    if _server_socket:
        _server_socket.close()
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
