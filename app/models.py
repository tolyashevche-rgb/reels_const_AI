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


class TaskResponse(BaseModel):
    task_id: str
    project_id: str
    status: TaskStatus
    created_at: str
    script: Optional[ScriptResponse] = None
    policy: Optional[PolicyResponse] = None


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
