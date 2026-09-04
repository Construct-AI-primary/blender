"""
Pydantic models for request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional


# ── Scene Rendering ──────────────────────────────────────────────────────────

class RenderSceneResponse(BaseModel):
    """Response after rendering a single frame."""
    success: bool
    message: str
    output_filename: Optional[str] = None
    download_url: Optional[str] = None
    render_time_seconds: Optional[float] = None


# ── Animation Rendering ──────────────────────────────────────────────────────

class AnimationJobRequest(BaseModel):
    """Request to start an animation render job."""
    frame_start: int = Field(default=1, ge=1, description="First frame to render")
    frame_end: int = Field(default=250, ge=1, description="Last frame to render")
    engine: str = Field(default="CYCLES", pattern="^(CYCLES|EEVEE|BLENDER_EEVEE|WORKBENCH)$")
    resolution_percentage: int = Field(default=100, ge=10, le=100)
    output_format: str = Field(default="PNG", pattern="^(PNG|JPEG|TIFF|OPEN_EXR)$")
    samples: int = Field(default=128, ge=1, le=4096)

    class Config:
        json_schema_extra = {
            "example": {
                "frame_start": 1,
                "frame_end": 50,
                "engine": "CYCLES",
                "resolution_percentage": 50,
                "output_format": "PNG",
                "samples": 128
            }
        }


class AnimationJobResponse(BaseModel):
    """Response when an animation job is submitted."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Status of an animation render job."""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: Optional[float] = None  # 0.0 to 1.0
    message: Optional[str] = None
    current_frame: Optional[int] = None
    total_frames: Optional[int] = None
    output_filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None


# ── File Processing ──────────────────────────────────────────────────────────

class ProcessExtractResponse(BaseModel):
    """Response from extracting data from a .blend file."""
    success: bool
    message: str
    data: Optional[dict] = None


class ConvertResponse(BaseModel):
    """Response from converting a .blend file."""
    success: bool
    message: str
    output_filename: Optional[str] = None
    download_url: Optional[str] = None


class ApplyModifierRequest(BaseModel):
    """Request to apply a modifier to a mesh."""
    modifier_type: str = Field(default="SUBSURF", description="Type of modifier to apply")
    settings: dict = Field(default_factory=dict, description="Modifier settings")

    class Config:
        json_schema_extra = {
            "example": {
                "modifier_type": "SUBSURF",
                "settings": {"levels": 2, "render_levels": 3}
            }
        }


class ApplyModifierResponse(BaseModel):
    """Response after applying a modifier."""
    success: bool
    message: str
    output_filename: Optional[str] = None
    download_url: Optional[str] = None


# ── General ──────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    blender_version: Optional[str] = None
    engine: str = "Blender Web Service"