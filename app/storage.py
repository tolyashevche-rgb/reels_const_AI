"""
In-memory project/task storage for MVP.
Replace with PostgreSQL in production.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models import TaskStatus


class TaskRecord:
    __slots__ = (
        "task_id", "project_id", "user_id", "status",
        "created_at", "request_data", "result",
    )

    def __init__(self, project_id: str, user_id: str, request_data: dict):
        self.task_id: str = uuid.uuid4().hex[:12]
        self.project_id: str = project_id
        self.user_id: str = user_id
        self.status: TaskStatus = TaskStatus.queued
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.request_data: dict = request_data
        self.result: Optional[dict] = None


class ProjectRecord:
    __slots__ = ("project_id", "user_id", "topic", "language", "tasks")

    def __init__(self, user_id: str, topic: str, language: str):
        self.project_id: str = uuid.uuid4().hex[:12]
        self.user_id: str = user_id
        self.topic: str = topic
        self.language: str = language
        self.tasks: list[TaskRecord] = []


# In-memory stores — replace with DB later
_projects: dict[str, ProjectRecord] = {}
_tasks: dict[str, TaskRecord] = {}


def create_project(user_id: str, topic: str, language: str) -> ProjectRecord:
    proj = ProjectRecord(user_id=user_id, topic=topic, language=language)
    _projects[proj.project_id] = proj
    return proj


def create_task(project: ProjectRecord, request_data: dict) -> TaskRecord:
    task = TaskRecord(
        project_id=project.project_id,
        user_id=project.user_id,
        request_data=request_data,
    )
    project.tasks.append(task)
    _tasks[task.task_id] = task
    return task


def get_task(task_id: str) -> Optional[TaskRecord]:
    return _tasks.get(task_id)


def get_project(project_id: str) -> Optional[ProjectRecord]:
    return _projects.get(project_id)
