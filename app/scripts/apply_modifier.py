"""
Apply a modifier to a mesh and save the modified .blend file.

Usage: blender <file> --background --python apply_modifier.py -- \
    --modifier_type SUBSURF --settings '{"levels": 2}' --mesh_name ""

Outputs JSON to stdout.
"""
import argparse
import bpy
import json
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modifier_type", default="SUBSURF")
    parser.add_argument("--settings", default="{}")
    parser.add_argument("--mesh_name", default="")
    return parser.parse_known_args()[0]


def main():
    args = parse_args()

    try:
        settings = json.loads(args.settings)

        # Find the target mesh object
        target_object = None
        if args.mesh_name:
            obj = bpy.data.objects.get(args.mesh_name)
            if obj and obj.type == "MESH":
                target_object = obj
            else:
                raise ValueError(f"Mesh object '{args.mesh_name}' not found")
        else:
            # Find the first mesh object
            for obj in bpy.data.objects:
                if obj.type == "MESH":
                    target_object = obj
                    break
            if not target_object:
                raise ValueError("No mesh objects found in the file")

        # Select and make active
        bpy.context.view_layer.objects.active = target_object
        bpy.ops.object.select_all(action="DESELECT")
        target_object.select_set(True)

        # Add the modifier
        modifier = target_object.modifiers.new(
            name=f"auto_{args.modifier_type}",
            type=args.modifier_type,
        )

        # Apply settings to the modifier
        for key, value in settings.items():
            if hasattr(modifier, key):
                setattr(modifier, key, value)

        # Apply the modifier
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        # Save to output path
        output_dir = os.environ.get("BLENDER_OUTPUT_DIR", "/tmp/blender_service")
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(bpy.data.filepath or "output"))[0]
        output_path = os.path.join(output_dir, f"{base_name}_modified.blend")

        bpy.ops.wm.save_as_mainfile(filepath=output_path)

        result = {
            "success": True,
            "output_path": output_path,
            "modifier_type": args.modifier_type,
            "mesh_name": target_object.name,
        }
        print(json.dumps(result))

    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()