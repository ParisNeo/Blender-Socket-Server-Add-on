def _get_scene_info():
    scene = bpy.context.scene
    objects = []
    
    for obj in scene.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type.upper(),  # Force la casse attendue par le client (ex: 'SPHERE')
            "location": list(obj.location)  # Inclus la position manquante
        })
        
    # Identification de la caméra active
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
    elif obj_type == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(location=location)
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
        "object_type": obj_type.upper(),  # Retourne en MAJUSCULES pour correspondre au contrat
        "location": list(created_obj.location),
        "status": "created"
    }

def _create_material(params):
    name = params.get("name", "NewMaterial")
    base_color = params.get("base_color", [0.8, 0.8, 0.8, 1.0])
    
    # Gestion du format RGB vers RGBA si nécessaire
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

def _set_camera_view(params):
    cam_name = params.get("name", "Camera")
    if cam_name not in bpy.data.objects:
        # Si la caméra nommée n'existe pas, on tente de prendre la caméra active du projet
        if bpy.context.scene.camera:
            cam = bpy.context.scene.camera
            cam_name = cam.name
        else:
            raise KeyError(f"Camera '{cam_name}' not found and no active camera setup.")
    else:
        cam = bpy.data.objects[cam_name]
        
    if "location" in params:
        cam.location = params["location"]
        
    # Si une cible (target) est définie, on oriente automatiquement la caméra vers elle
    if "target" in params:
        import mathutils
        target_loc = mathutils.Vector(params["target"])
        direction = target_loc - cam.location
        # Oriente l'axe -Z vers la cible, avec le haut dirigé vers Y
        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
        
    return {
        "camera_name": cam_name,
        "camera_location": list(cam.location),
        "status": "updated"
    }

def _render_scene(params):
    scene = bpy.context.scene
    
    # 1. Correction de la clé d'entrée : Lecture de 'output_path' conformément au client
    output_path = params.get("output_path", params.get("filepath", "/tmp/render.png"))
    
    # Évite les chemins relatifs indémerdables dans le bac à sable, force l'écriture
    scene.render.filepath = bpy.path.abspath(output_path)
    
    # 2. Application dynamique des paramètres d'image transmis
    if "width" in params:
        scene.render.resolution_x = int(params["width"])
    if "height" in params:
        scene.render.resolution_x = int(params["height"])
        
    # 3. Changement du moteur de rendu à la volée si demandé
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

    # Exécution du moteur de rendu natif
    bpy.ops.render.render(write_still=True)
    
    return {
        "status": "Render completed",
        "output_path": scene.render.filepath
    }
