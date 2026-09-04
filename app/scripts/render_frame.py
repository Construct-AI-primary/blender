"""
Render a single frame from a .blend file.

Usage: blender <file> --background --python render_frame.py -- \
    --engine CYCLES --samples 128 --resolution_percentage 100 \
    --frame 1 --output_format PNG

Outputs JSON to stdout.
"""
import argparse
import bpy
import json
import os
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse arguments (everything after '--' in the blender command)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="CYCLES")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--resolution_percentage", type=int, default=100)
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--output_format", default="PNG")
    # Output path is passed as environment variable or inferred
    # We'll read it from a known location
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    start_time = time.time()

    try:
        # ── Configure Scene ──────────────────────────────────────────────
        scene = bpy.context.scene

        # Set render engine
        engine_map = {
            "CYCLES": "CYCLES",
            "EEVEE": "BLENDER_EEVEE",
            "BLENDER_EEVEE": "BLENDER_EEVEE",
            "WORKBENCH": "BLENDER_WORKBENCH",
        }
        scene.render.engine = engine_map.get(args.engine, "CYCLES")

        # Resolution
        scene.render.resolution_percentage = args.resolution_percentage

        # Frame
        scene.frame_set(args.frame)

        # Samples (Cycles only)
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = args.samples

        # Output format
        format_map = {
            "PNG": "PNG",
            "JPEG": "JPEG",
            "TIFF": "TIFF",
            "OPEN_EXR": "OPEN_EXR",
        }
        scene.render.image_settings.file_format = format_map.get(args.output_format, "PNG")

        # ── Output path ──────────────────────────────────────────────────
        # The output path is passed via a known env var or we auto-detect
        output_path = os.environ.get("BLENDER_OUTPUT_PATH", "")
        if not output_path:
            # Use a temp file with auto-naming
            ext_map = {"PNG": ".png", "JPEG": ".jpg", "TIFF": ".tif", "OPEN_EXR": ".exr"}
            output_path = f"/tmp/blender_service/output{ext_map.get(args.output_format, '.png')}"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        scene.render.filepath = output_path

        # ── Render ───────────────────────────────────────────────────────
        bpy.ops.render.render(write_still=True)

        # ── Success Output ───────────────────────────────────────────────
        elapsed = time.time() - start_time
        result = {
            "success": True,
            "output_path": output_path,
            "render_time_seconds": round(elapsed, 2),
            "engine": args.engine,
            "frame": args.frame,
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