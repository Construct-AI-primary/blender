"""
Convert a .blend file to another 3D format.

Usage: blender <file> --background --python convert_format.py -- \
    --target_format gltf|glb|obj|fbx|stl|usd|ply|x3d|abc

Outputs JSON to stdout.
"""
import argparse
import bpy
import json
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target_format", default="gltf")
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    target = args.target_format.lower()

    try:
        input_path = bpy.data.filepath
        if not input_path:
            raise ValueError("No .blend file loaded. Provide a .blend file as the first argument.")

        # Generate output path
        output_dir = os.environ.get("BLENDER_OUTPUT_DIR", "/tmp/blender_service")
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        # Select all objects
        bpy.ops.object.select_all(action="SELECT")

        if target in ("gltf", "glb"):
            # glTF 2.0 export
            ext = ".glb" if target == "glb" else ".gltf"
            output_path = os.path.join(output_dir, f"{base_name}{ext}")
            bpy.ops.export_scene.gltf(
                filepath=output_path,
                export_format="GLB" if target == "glb" else "GLTF_SEPARATE",
                use_selection=False,
                export_texcoords=True,
                export_normals=True,
                export_materials="EXPORT",
            )

        elif target == "obj":
            output_path = os.path.join(output_dir, f"{base_name}.obj")
            bpy.ops.wm.obj_export(
                filepath=output_path,
                export_selected_objects=False,
                apply_modifiers=True,
                export_uv=True,
                export_normals=True,
                export_materials=True,
            )

        elif target == "fbx":
            output_path = os.path.join(output_dir, f"{base_name}.fbx")
            bpy.ops.export_scene.fbx(
                filepath=output_path,
                use_selection=False,
                apply_scale_options="FBX_SCALE_UNITS",
                bake_anim=True,
            )

        elif target == "stl":
            output_path = os.path.join(output_dir, f"{base_name}.stl")
            bpy.ops.export_mesh.stl(
                filepath=output_path,
                use_selection=False,
                ascii=False,
            )

        elif target == "usd":
            output_path = os.path.join(output_dir, f"{base_name}.usd")
            bpy.ops.export_scene.usd(
                filepath=output_path,
                use_selection=False,
            )

        elif target == "ply":
            output_path = os.path.join(output_dir, f"{base_name}.ply")
            bpy.ops.export_mesh.ply(
                filepath=output_path,
                use_selection=False,
                apply_modifiers=True,
                export_uv=True,
                export_normals=True,
                export_colors="SRGB",
            )

        elif target == "x3d":
            output_path = os.path.join(output_dir, f"{base_name}.x3d")
            bpy.ops.export_scene.x3d(
                filepath=output_path,
                use_selection=False,
            )

        elif target == "abc":
            output_path = os.path.join(output_dir, f"{base_name}.abc")
            bpy.ops.export_alembic.main(
                filepath=output_path,
                frame_start=bpy.context.scene.frame_start,
                frame_end=bpy.context.scene.frame_end,
            )

        else:
            raise ValueError(f"Unsupported format: {target}. Supported: gltf, glb, obj, fbx, stl, usd, ply, x3d, abc")

        result = {
            "success": True,
            "output_path": output_path,
            "format": target,
        }
        print(json.dumps(result))

    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()