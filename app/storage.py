"""
SQLite persistent storage for projects and tasks.
Drop-in replacement for the in-memory MVP storage.
DB file: data/reels.db
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models import TaskStatus

DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)
DB_PATH = os.path.join(DB_DIR, "reels.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            topic      TEXT NOT NULL,
            language   TEXT NOT NULL DEFAULT 'uk',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id      TEXT PRIMARY KEY,
            project_id   TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'queued',
            created_at   TEXT NOT NULL,
            request_data TEXT NOT NULL DEFAULT '{}',
            result       TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_user    ON tasks(user_id);
    """)


# Init on import
_conn = _get_conn()
_init_db(_conn)


# ─── Lightweight record wrappers (API-compatible with old in-memory storage) ───

class TaskRecord:
    __slots__ = (
        "task_id", "project_id", "user_id", "status",
        "created_at", "request_data", "result",
    )

    def __init__(self, project_id: str, user_id: str, request_data: dict,
                 task_id: str | None = None, status: str = "queued",
                 created_at: str | None = None, result: dict | None = None):
        self.task_id = task_id or uuid.uuid4().hex[:12]
        self.project_id = project_id
        self.user_id = user_id
        self.status = TaskStatus(status)
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.request_data = request_data
        self.result = result


class ProjectRecord:
    __slots__ = ("project_id", "user_id", "topic", "language", "tasks", "created_at")

    def __init__(self, user_id: str, topic: str, language: str,
                 project_id: str | None = None, created_at: str | None = None):
        self.project_id = project_id or uuid.uuid4().hex[:12]
        self.user_id = user_id
        self.topic = topic
        self.language = language
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.tasks: list[TaskRecord] = []


# ─── CRUD operations ───

def create_project(user_id: str, topic: str, language: str) -> ProjectRecord:
    proj = ProjectRecord(user_id=user_id, topic=topic, language=language)
    _conn.execute(
        "INSERT INTO projects (project_id, user_id, topic, language, created_at) VALUES (?, ?, ?, ?, ?)",
        (proj.project_id, proj.user_id, proj.topic, proj.language, proj.created_at),
    )
    _conn.commit()
    return proj


def create_task(project: ProjectRecord, request_data: dict) -> TaskRecord:
    task = TaskRecord(
        project_id=project.project_id,
        user_id=project.user_id,
        request_data=request_data,
    )
    _conn.execute(
        "INSERT INTO tasks (task_id, project_id, user_id, status, created_at, request_data) VALUES (?, ?, ?, ?, ?, ?)",
        (task.task_id, task.project_id, task.user_id, task.status.value, task.created_at,
         json.dumps(request_data, ensure_ascii=False)),
    )
    _conn.commit()
    project.tasks.append(task)
    return task


def save_task(task: TaskRecord) -> None:
    """Persist task status/result changes to DB."""
    _conn.execute(
        "UPDATE tasks SET status = ?, result = ? WHERE task_id = ?",
        (task.status.value if isinstance(task.status, TaskStatus) else task.status,
         json.dumps(task.result, ensure_ascii=False) if task.result else None,
         task.task_id),
    )
    _conn.commit()


def get_task(task_id: str) -> Optional[TaskRecord]:
    row = _conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        return None
    return TaskRecord(
        task_id=row["task_id"],
        project_id=row["project_id"],
        user_id=row["user_id"],
        status=row["status"],
        created_at=row["created_at"],
        request_data=json.loads(row["request_data"]) if row["request_data"] else {},
        result=json.loads(row["result"]) if row["result"] else None,
    )


def get_project(project_id: str) -> Optional[ProjectRecord]:
    row = _conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return None
    proj = ProjectRecord(
        project_id=row["project_id"],
        user_id=row["user_id"],
        topic=row["topic"],
        language=row["language"],
        created_at=row["created_at"],
    )
    task_rows = _conn.execute(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at", (project_id,)
    ).fetchall()
    for tr in task_rows:
        proj.tasks.append(TaskRecord(
            task_id=tr["task_id"],
            project_id=tr["project_id"],
            user_id=tr["user_id"],
            status=tr["status"],
            created_at=tr["created_at"],
            request_data=json.loads(tr["request_data"]) if tr["request_data"] else {},
            result=json.loads(tr["result"]) if tr["result"] else None,
        ))
    return proj
