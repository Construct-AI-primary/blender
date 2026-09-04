"""
FastAPI application for Blender Web Service.

Provides endpoints for:
  - Scene rendering (render a single frame from a .blend file)
  - Animation rendering (render multiple frames as a background job)
  - File processing (extract data, convert formats, apply modifiers)

All Blender operations are performed via subprocess calls to the Blender
binary, running internal scripts with `blender --background --python`.
"""
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.blender_runner import (
    cleanup_temp,
    get_temp_path,
    run_blender_script,
    save_upload,
    TEMP_DIR,
)
from app.models import (
    AnimationJobRequest,
    AnimationJobResponse,
    ApplyModifierRequest,
    ApplyModifierResponse,
    ConvertResponse,
    HealthResponse,
    JobStatusResponse,
    ProcessExtractResponse,
    RenderSceneResponse,
)

# ── App Setup ────────────────────────────────────────────────────────────────

MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "500"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

app = FastAPI(
    title="Blender Web Service",
    description=(
        "Render 3D scenes, process .blend files, and render animations "
        "using Blender's full rendering engine on Render.com."
    ),
    version="1.0.0",
)

# ── In-Memory Job Store ──────────────────────────────────────────────────────
# NOTE: Jobs are lost on restart. For production, replace with Redis or a DB.
jobs: dict[str, dict] = {}
# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint — Render uses this to verify the service is alive."""
    blender_version = None
    try:
        import subprocess
        result = subprocess.run(
            [os.environ.get("BLENDER_EXECUTABLE", "blender"), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        blender_version = result.stdout.strip().split("\n")[0] if result.stdout else None
    except Exception:
        blender_version = "unknown"

    return HealthResponse(status="healthy", blender_version=blender_version)


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — API information."""
    return {
        "service": "Blender Web Service",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "health": "GET /health",
            "render_scene": "POST /render/scene",
            "render_animation": "POST /render/animation",
            "job_status": "GET /render/jobs/{job_id}",
            "job_download": "GET /render/jobs/{job_id}/download",
            "extract": "POST /process/extract",
            "convert": "POST /process/convert",
            "apply_modifier": "POST /process/apply-modifier",
        },
    }
# ── Scene Rendering ──────────────────────────────────────────────────────────

@app.post(
    "/render/scene",
    response_model=RenderSceneResponse,
    tags=["Rendering"],
    summary="Render a single frame from a .blend file",
)
async def render_scene(
    file: UploadFile = File(..., description="The .blend file to render"),
    engine: str = Form(default="CYCLES", description="Render engine: CYCLES, EEVEE, BLENDER_EEVEE, WORKBENCH"),
    samples: int = Form(default=128, description="Render samples (Cycles only)"),
    resolution_percentage: int = Form(default=100, description="Resolution percentage (10-100)"),
    frame: int = Form(default=1, description="Frame number to render"),
    output_format: str = Form(default="PNG", description="Output format: PNG, JPEG, TIFF, OPEN_EXR"),
):
    """
    Upload a .blend file and render a single frame.

    Returns the rendered image as a downloadable file.
    """
    if not file.filename or not file.filename.endswith(".blend"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .blend file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB}MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    input_path = save_upload(content)
    output_path = get_temp_path(f".{output_format.lower()}")

    try:
        result = run_blender_script(
            "render_frame.py",
            input_path=str(input_path),
            output_path=str(output_path),
            extra_args=[
                "--engine", engine,
                "--samples", str(samples),
                "--resolution_percentage", str(resolution_percentage),
                "--frame", str(frame),
                "--output_format", output_format,
            ],
            timeout=600,
        )

        if result.get("success") and output_path.exists():
            return RenderSceneResponse(
                success=True,
                message=f"Frame {frame} rendered successfully",
                output_filename=output_path.name,
                download_url=f"/download/{output_path.name}",
                render_time_seconds=result.get("render_time_seconds"),
            )
        else:
            error_msg = result.get("error", "Unknown render error")
            raise HTTPException(status_code=500, detail=error_msg)

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_temp(input_path)
# ── Animation Rendering ──────────────────────────────────────────────────────

@app.post(
    "/render/animation",
    response_model=AnimationJobResponse,
    tags=["Rendering"],
    summary="Start rendering an animation as a background job",
)
async def render_animation(
    file: UploadFile = File(..., description="The .blend file to render"),
    job_settings: str = Form(
        default=json.dumps(AnimationJobRequest.Config.json_schema_extra["example"]),
        description="JSON string of AnimationJobRequest settings",
    ),
):
    """Start an animation render job and return a job ID for tracking."""
    if not file.filename or not file.filename.endswith(".blend"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .blend file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB}MB",
        )

    try:
        settings = json.loads(job_settings)
        request = AnimationJobRequest(**settings)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(status_code=400, detail=f"Invalid job settings: {e}")

    input_path = save_upload(content)

    job_id = uuid.uuid4().hex[:12]
    output_dir = get_temp_path("").parent / f"anim_{job_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0.0,
        "current_frame": 0,
        "total_frames": (request.frame_end - request.frame_start + 1),
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "settings": request.model_dump(),
        "created_at": datetime.utcnow().isoformat(),
        "error": None,
    }

    try:
        _run_animation_job(job_id)
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

    return AnimationJobResponse(
        job_id=job_id,
        status=jobs[job_id]["status"],
        message=f"Animation job {job_id} submitted",
    )


def _run_animation_job(job_id: str):
    """Execute the animation render job (synchronous execution)."""
    job = jobs[job_id]
    settings = job["settings"]

    extra_args = [
        "--frame_start", str(settings["frame_start"]),
        "--frame_end", str(settings["frame_end"]),
        "--engine", settings["engine"],
        "--samples", str(settings["samples"]),
        "--resolution_percentage", str(settings["resolution_percentage"]),
        "--output_format", settings["output_format"],
        "--output_dir", job["output_dir"],
    ]

    job["status"] = "running"

    try:
        result = run_blender_script(
            "render_animation.py",
            input_path=job["input_path"],
            extra_args=extra_args,
            timeout=3600,
        )

        if result.get("success"):
            zip_path = shutil.make_archive(
                str(get_temp_path("").parent / f"anim_{job_id}"),
                "zip",
                job["output_dir"],
            )
            job["output_filename"] = os.path.basename(zip_path)
            job["download_url"] = f"/download/{os.path.basename(zip_path)}"
            job["status"] = "completed"
            job["progress"] = 1.0
        else:
            job["status"] = "failed"
            job["error"] = result.get("error", "Unknown error")

    except RuntimeError as e:
        job["status"] = "failed"
        job["error"] = str(e)
    finally:
        cleanup_temp(Path(job["input_path"]))


@app.get(
    "/render/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Rendering"],
    summary="Check the status of an animation render job",
)
async def get_job_status(job_id: str):
    """Get the current status of an animation render job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job["id"],
        status=job["status"],
        progress=job.get("progress"),
        message=f"Job is {job['status']}",
        current_frame=job.get("current_frame"),
        total_frames=job.get("total_frames"),
        output_filename=job.get("output_filename"),
        download_url=job.get("download_url"),
        error=job.get("error"),
    )
# ── File Processing: Extract & Convert ───────────────────────────────────────

@app.post(
    "/process/extract",
    response_model=ProcessExtractResponse,
    tags=["Processing"],
    summary="Extract data from a .blend file",
)
async def extract_data(
    file: UploadFile = File(..., description="The .blend file to extract data from"),
    extract_type: str = Form(
        default="summary",
        description="What to extract: summary, meshes, materials, textures, animations, scenes, all",
    ),
):
    """Extract structured data (meshes, materials, animations, etc.) from a .blend file."""
    if not file.filename or not file.filename.endswith(".blend"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .blend file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB}MB")

    input_path = save_upload(content)

    try:
        result = run_blender_script(
            "extract_data.py",
            input_path=str(input_path),
            extra_args=["--extract_type", extract_type],
            timeout=120,
        )
        if result.get("success"):
            return ProcessExtractResponse(
                success=True, message="Data extracted successfully",
                data=result.get("data", {}),
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Extraction failed"))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_temp(input_path)


@app.post(
    "/process/convert",
    response_model=ConvertResponse,
    tags=["Processing"],
    summary="Convert a .blend file to another format",
)
async def convert_file(
    file: UploadFile = File(..., description="The .blend file to convert"),
    target_format: str = Form(
        default="gltf",
        description="Target format: gltf, glb, obj, fbx, stl, usd, ply, x3d, abc",
    ),
):
    """Convert a .blend file to glTF, OBJ, FBX, STL, USD, PLY, X3D, or Alembic."""
    if not file.filename or not file.filename.endswith(".blend"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .blend file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB}MB")

    input_path = save_upload(content)
    output_path = get_temp_path(f".{target_format}")

    try:
        result = run_blender_script(
            "convert_format.py",
            input_path=str(input_path),
            output_path=str(output_path),
            extra_args=["--target_format", target_format],
            timeout=300,
        )
        if result.get("success") and output_path.exists():
            return ConvertResponse(
                success=True, message=f"Converted to {target_format} successfully",
                output_filename=output_path.name,
                download_url=f"/download/{output_path.name}",
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Conversion failed"))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_temp(input_path)
# ── File Processing: Apply Modifier ──────────────────────────────────────────

@app.post(
    "/process/apply-modifier",
    response_model=ApplyModifierResponse,
    tags=["Processing"],
    summary="Apply a modifier to a mesh in a .blend file",
)
async def apply_modifier(
    file: UploadFile = File(..., description="The .blend file containing the mesh"),
    modifier_type: str = Form(
        default="SUBSURF",
        description="Modifier type: SUBSURF, MIRROR, SOLIDIFY, BEVEL, ARRAY, DECIMATE, REMESH, etc.",
    ),
    modifier_settings: str = Form(
        default='{"levels": 2, "render_levels": 2}',
        description="JSON string of modifier settings",
    ),
    mesh_name: str = Form(
        default="",
        description="Name of the mesh (empty = first mesh found)",
    ),
):
    """Apply a modifier (e.g., Subdivision Surface, Mirror, Bevel) and return the modified .blend."""
    if not file.filename or not file.filename.endswith(".blend"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .blend file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum is {MAX_UPLOAD_SIZE_MB}MB")

    try:
        settings = json.loads(modifier_settings)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid modifier_settings JSON")

    input_path = save_upload(content)
    output_path = get_temp_path("_modified.blend")

    try:
        result = run_blender_script(
            "apply_modifier.py",
            input_path=str(input_path),
            output_path=str(output_path),
            extra_args=[
                "--modifier_type", modifier_type,
                "--settings", json.dumps(settings),
                "--mesh_name", mesh_name,
            ],
            timeout=300,
        )
        if result.get("success") and output_path.exists():
            return ApplyModifierResponse(
                success=True, message=f"Modifier '{modifier_type}' applied successfully",
                output_filename=output_path.name,
                download_url=f"/download/{output_path.name}",
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Modifier application failed"))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_temp(input_path)
# ── File Download ─────────────────────────────────────────────────────────────

@app.get("/download/{filename}", tags=["System"], include_in_schema=False)
async def download_file(filename: str):
    """Download a rendered or processed file."""
    file_path = TEMP_DIR / filename
    if not file_path.exists():
        alt_path = TEMP_DIR.parent / filename
        if alt_path.exists():
            file_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"File {filename} not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


# ── Cleanup Old Files (on startup) ───────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Clean up any leftover temp files from previous runs."""
    if TEMP_DIR.exists():
        for f in TEMP_DIR.iterdir():
            if f.is_file():
                cleanup_temp(f)
    print(f"Blender Web Service started. Temp dir: {TEMP_DIR}")


# ── Error Handlers ───────────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )