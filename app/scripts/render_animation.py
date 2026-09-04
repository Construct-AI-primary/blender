"""
Render an animation from a .blend file (multiple frames).

Usage: blender <file> --background --python render_animation.py -- \
    --frame_start 1 --frame_end 50 --engine CYCLES --samples 128 \
    --resolution_percentage 100 --output_format PNG --output_dir /path/to/output

Outputs JSON to stdout when complete.
"""
import argparse
import bpy
import json
import os
import sys
import time


def parse_args() -> argparse.Namespace:
    """Parse animation render arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame_start", type=int, default=1)
    parser.add_argument("--frame_end", type=int, default=250)
    parser.add_argument("--engine", default="CYCLES")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--resolution_percentage", type=int, default=100)
    parser.add_argument("--output_format", default="PNG")
    parser.add_argument("--output_dir", default="/tmp/blender_service/anim_output")
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    start_time = time.time()

    try:
        scene = bpy.context.scene

        # Configure engine
        engine_map = {
            "CYCLES": "CYCLES",
            "EEVEE": "BLENDER_EEVEE",
            "BLENDER_EEVEE": "BLENDER_EEVEE",
            "WORKBENCH": "BLENDER_WORKBENCH",
        }
        scene.render.engine = engine_map.get(args.engine, "CYCLES")
        scene.render.resolution_percentage = args.resolution_percentage

        if scene.render.engine == "CYCLES":
            scene.cycles.samples = args.samples

        # Configure output
        format_map = {
            "PNG": "PNG",
            "JPEG": "JPEG",
            "TIFF": "TIFF",
            "OPEN_EXR": "OPEN_EXR",
        }
        scene.render.image_settings.file_format = format_map.get(args.output_format, "PNG")

        # Set output directory
        os.makedirs(args.output_dir, exist_ok=True)
        scene.render.filepath = os.path.join(args.output_dir, "frame_")

        # Set frame range
        scene.frame_start = args.frame_start
        scene.frame_end = args.frame_end

        # Render animation
        bpy.ops.render.render(animation=True, write_still=False)

        # Count rendered frames
        frame_count = args.frame_end - args.frame_start + 1
        elapsed = time.time() - start_time

        result = {
            "success": True,
            "frames_rendered": frame_count,
            "frame_start": args.frame_start,
            "frame_end": args.frame_end,
            "output_dir": args.output_dir,
            "render_time_seconds": round(elapsed, 2),
        }
        print(json.dumps(result))

    except Exception as e:
        elapsed = time.time() - start_time
        error_result = {
            "success": False,
            "error": str(e),
            "render_time_seconds": round(elapsed, 2),
        }
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    main()