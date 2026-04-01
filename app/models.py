"""
Pydantic models for API request/response validation.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


# --- Enums ---

class TaskStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    review_needed = "review_needed"
    done = "done"
    failed = "failed"


class Language(str, Enum):
    uk = "uk"
    en = "en"
    ru = "ru"


# --- Request models ---

# Render config models (must be before RenderRequest)

class VideoConfigRequest(BaseModel):
    format: str = Field(default="reels", description="Preset: reels | square | landscape | story | custom")
    width: int = Field(default=1080, ge=320, le=3840, description="Width (only for format=custom)")
    height: int = Field(default=1920, ge=320, le=3840, description="Height (only for format=custom)")
    fps: int = Field(default=30, ge=15, le=60)
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Playback speed")
    crf: int = Field(default=23, ge=0, le=51, description="Quality (lower=better, 18-28 typical)")
    transition: str = Field(default="fade", description="xfade transition type")
    transition_duration: float = Field(default=0.3, ge=0.0, le=2.0, description="Transition duration (sec)")


class TextConfigRequest(BaseModel):
    font: str = Field(default="", description="Path to .ttf font (empty=auto)")
    font_size: int = Field(default=52, ge=16, le=120)
    font_size_desc: int = Field(default=28, ge=12, le=80)
    font_color: str = Field(default="white")
    font_color_opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    border_width: int = Field(default=3, ge=0, le=10)
    border_color: str = Field(default="black")
    border_opacity: float = Field(default=0.6, ge=0.0, le=1.0)
    position_y: float = Field(default=0.75, ge=0.0, le=1.0, description="Main text Y position (0=top, 1=bottom)")
    position_y_desc: float = Field(default=0.15, ge=0.0, le=1.0, description="Description Y position")


class AudioConfigRequest(BaseModel):
    voice_volume: float = Field(default=1.0, ge=0.0, le=2.0)
    ambient_enabled: bool = Field(default=True)
    ambient_volume: float = Field(default=0.15, ge=0.0, le=1.0)
    ambient_type: str = Field(default="sine", description="sine | lullaby | deep | bright")
    audio_bitrate: str = Field(default="192k")


class RenderConfigRequest(BaseModel):
    video: Optional[VideoConfigRequest] = None
    text: Optional[TextConfigRequest] = None
    audio: Optional[AudioConfigRequest] = None


class RenderRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300)
    language: Language = Field(default=Language.uk)
    duration_sec: int = Field(default=30, ge=15, le=60)
    style: str = Field(default="warm_expert")
    user_id: str = Field(default="anonymous")
    # Optional intent override (for testing / advanced users)
    emotion: Optional[str] = Field(default=None)
    pain_point: Optional[str] = Field(default=None)
    reel_type: Optional[str] = Field(default=None)
    age_focus: Optional[str] = Field(default=None)
    # Render configuration
    render_config: Optional[RenderConfigRequest] = Field(default=None, description="Video/text/audio render settings")


class EditRequest(BaseModel):
    field: str = Field(..., description="Which part to edit: hook | body | cta | text_overlays | emotion | style")
    value: str | list = Field(..., description="New value for the field")


# --- Response models ---

class PolicyIssueResponse(BaseModel):
    severity: str
    quote: str
    reason: str


class ScriptResponse(BaseModel):
    hook: str
    body: str
    cta: str
    text_overlays: List[str]
    duration_hint_sec: int


class PolicyResponse(BaseModel):
    approved: bool
    issues: List[PolicyIssueResponse] = []


class ShotResponse(BaseModel):
    order: int
    description: str
    duration_sec: float
    text_overlay: str = ""
    audio_cue: str = ""


class TaskResponse(BaseModel):
    task_id: str
    project_id: str
    status: TaskStatus
    created_at: str
    script: Optional[ScriptResponse] = None
    policy: Optional[PolicyResponse] = None
    shots: Optional[List[ShotResponse]] = None
    voice_duration_sec: Optional[float] = None
    preview_url: Optional[str] = None


class TaskCreatedResponse(BaseModel):
    task_id: str
    project_id: str
    status: TaskStatus


class ProjectResponse(BaseModel):
    project_id: str
    user_id: str
    topic: str
    language: str
    versions: List[TaskResponse] = []
