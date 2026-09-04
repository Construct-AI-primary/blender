"""
Utility to run Blender scripts via subprocess.

Our FastAPI app cannot import bpy directly (bpy is tied to Blender's built-in
Python interpreter). Instead, we write Python scripts and execute them with:

    blender --background --python <script> -- <args>

The script communicates results back by printing JSON to stdout.
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────────────

BLENDER_EXECUTABLE = os.environ.get("BLENDER_EXECUTABLE", "/usr/local/bin/blender")
TEMP_DIR = Path(os.environ.get("TEMP_DIR", "/tmp/blender_service"))
SCRIPTS_DIR = Path(__file__).parent / "scripts"

# Ensure temp directory exists
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ── Core Runner ─────────────────────────────────────────────────────────────

def run_blender_script(
    script_name: str,
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    timeout: int = 600,  # 10 minutes default timeout
) -> dict:
    """
    Run a Blender Python script via subprocess.

    Args:
        script_name: Name of script in app/scripts/ (e.g., "render_frame.py")
        input_path: Path to input .blend file (can be None)
        output_path: Path where output should be written
        extra_args: Additional arguments to pass to the script
        timeout: Maximum execution time in seconds

    Returns:
        Parsed JSON output from the script (must print JSON to stdout)

    Raises:
        RuntimeError: If Blender execution fails or returns invalid output.
    """
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Blender script not found: {script_path}")

    # Build the command
    cmd = [
        BLENDER_EXECUTABLE,
        "--background",           # Run without GUI
        "--no-window-focus",      # Don't steal focus
        "--python", str(script_path),
        "--",                     # Separator: everything after is script args
    ]

    if input_path:
        cmd.insert(2, input_path)  # Positional: blender <file> --background ...

    if extra_args:
        cmd.extend(extra_args)

    # Set environment variables for the Blender scripts
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if output_path:
        env["BLENDER_OUTPUT_PATH"] = output_path
        env["BLENDER_OUTPUT_DIR"] = str(Path(output_path).parent)

    # Run Blender
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(TEMP_DIR),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Blender script '{script_name}' timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError(
            f"Blender executable not found at '{BLENDER_EXECUTABLE}'. "
            "Make sure Blender is installed in the Docker image."
        )

    # Check return code
    if result.returncode != 0:
        stderr = result.stderr.strip() or "No error output"
        print(f"Blender stderr:\n{stderr[:2000]}", file=sys.stderr)
        raise RuntimeError(
            f"Blender exited with code {result.returncode}: {stderr[:500]}"
        )

    # Parse JSON from the last line of stdout
    stdout_lines = result.stdout.strip().split("\n")
    json_lines = [line for line in stdout_lines if line.strip().startswith("{")]

    if not json_lines:
        stderr = result.stderr.strip() or "No error output"
        print(f"Blender stdout:\n{result.stdout[:2000]}", file=sys.stderr)
        print(f"Blender stderr:\n{stderr[:2000]}", file=sys.stderr)
        raise RuntimeError("Blender script produced no JSON output")

    try:
        output = json.loads(json_lines[-1])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Blender output JSON: {e}")

    return output


# ── Temp File Helpers ────────────────────────────────────────────────────────

def get_temp_path(suffix: str = "") -> Path:
    """Get a unique temporary file path."""
    return TEMP_DIR / f"{uuid.uuid4().hex}{suffix}"


def save_upload(upload_content: bytes, suffix: str = ".blend") -> Path:
    """Save uploaded file content to a temporary path."""
    path = get_temp_path(suffix)
    path.write_bytes(upload_content)
    return path


def cleanup_temp(path: Path) -> None:
    """Remove a temporary file if it exists."""
    if path.exists():
        path.unlink(missing_ok=True)