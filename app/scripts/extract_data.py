"""
Extract structured data from a .blend file.

Usage: blender <file> --background --python extract_data.py -- \
    --extract_type summary|meshes|materials|textures|animations|scenes|all

Outputs JSON with extracted data to stdout.
"""
import argparse
import bpy
import json
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract_type", default="summary")
    return parser.parse_known_args()[0]


def get_summary() -> dict:
    """Get a summary of the .blend file contents."""
    summary = {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "textures": len(bpy.data.textures),
        "actions": len(bpy.data.actions),
        "worlds": len(bpy.data.worlds),
        "collections": len(bpy.data.collections),
        "scenes": len(bpy.data.scenes),
        "scene_names": [s.name for s in bpy.data.scenes],
        "file_path": bpy.data.filepath or "Untitled",
    }
    return summary


def get_meshes() -> list:
    """Get mesh data summary."""
    meshes = []
    for mesh in bpy.data.meshes:
        meshes.append({
            "name": mesh.name,
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "polygons": len(mesh.polygons),
            "uv_layers": len(mesh.uv_layers),
            "materials": [m.name if m else None for m in mesh.materials],
        })
    return meshes


def get_materials() -> list:
    """Get material data."""
    materials = []
    for mat in bpy.data.materials:
        nodes = []
        if mat.node_tree:
            nodes = [n.name for n in mat.node_tree.nodes]
        materials.append({
            "name": mat.name,
            "use_nodes": mat.use_nodes,
            "nodes": nodes,
        })
    return materials


def get_textures() -> list:
    """Get texture data."""
    textures = []
    for tex in bpy.data.textures:
        textures.append({
            "name": tex.name,
            "type": tex.type,
        })
    for img in bpy.data.images:
        textures.append({
            "name": img.name,
            "type": "IMAGE",
            "size": f"{img.size[0]}x{img.size[1]}" if img.size[0] > 0 else "unknown",
            "filepath": img.filepath,
        })
    return textures


def get_animations() -> list:
    """Get animation/action data."""
    animations = []
    for action in bpy.data.actions:
        fcurves_count = len(action.fcurves) if action.fcurves else 0
        animations.append({
            "name": action.name,
            "frame_range": list(action.frame_range) if hasattr(action, "frame_range") else None,
            "fcurves": fcurves_count,
            "groups": [g.name for g in action.groups],
        })
    return animations


def get_scenes_detail() -> list:
    """Get detailed scene info."""
    scenes = []
    for scene in bpy.data.scenes:
        scenes.append({
            "name": scene.name,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
            "engine": scene.render.engine,
            "resolution": f"{scene.render.resolution_x}x{scene.render.resolution_y}",
            "resolution_percentage": scene.render.resolution_percentage,
            "world": scene.world.name if scene.world else None,
            "objects": [o.name for o in scene.objects],
        })
    return scenes


def main():
    args = parse_args()

    try:
        data = {}

        if args.extract_type in ("summary", "all"):
            data["summary"] = get_summary()
        if args.extract_type in ("meshes", "all"):
            data["meshes"] = get_meshes()
        if args.extract_type in ("materials", "all"):
            data["materials"] = get_materials()
        if args.extract_type in ("textures", "all"):
            data["textures"] = get_textures()
        if args.extract_type in ("animations", "all"):
            data["animations"] = get_animations()
        if args.extract_type in ("scenes", "all"):
            data["scenes"] = get_scenes_detail()

        result = {"success": True, "data": data}
        print(json.dumps(result, default=str))

    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()