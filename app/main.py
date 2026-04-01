import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from typing import Optional
import os
import threading

from app.models import (
    RenderRequest, EditRequest, TaskStatus,
    TaskCreatedResponse, TaskResponse, ProjectResponse,
    ScriptResponse, PolicyResponse, PolicyIssueResponse,
    ShotResponse,
)
from app.storage import create_project, create_task, get_task, get_project, save_task
from app.graph import content_graph

app = FastAPI(title="Reels Construction AI", version="0.2.0")

# Serve media files (previews, renders)
_media_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(_media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_dir), name="media")


# ─── Health ───

@app.get("/")
def health():
    return {"status": "ok", "service": "reels-construction-ai"}


# ─── Background pipeline runner ───

def _run_pipeline(task_id: str, initial_state: dict) -> None:
    """Запускає LangGraph pipeline у фоновому потоці."""
    from app.storage import get_task, save_task
    task = get_task(task_id)
    if not task:
        return
    try:
        result = content_graph.invoke(initial_state)
        if result.get("errors"):
            task.status = TaskStatus.failed
            task.result = {"errors": result["errors"]}
        else:
            approved = result.get("policy_result", {}).get("approved", False)
            task.status = TaskStatus.done if approved else TaskStatus.review_needed
            task.result = {
                "script": result.get("script"),
                "policy_result": result.get("policy_result"),
                "shot_list": result.get("shot_list"),
                "search_candidates": result.get("search_candidates"),
                "selected_assets": result.get("selected_assets"),
                "voice_track": result.get("voice_track"),
                "voice_duration_sec": result.get("voice_duration_sec"),
                "render_output": result.get("render_output"),
                "preview_url": result.get("preview_url"),
            }
    except Exception as e:
        task.status = TaskStatus.failed
        task.result = {"errors": [str(e)]}
    save_task(task)


# ─── POST /api/v1/render — створити задачу ───

@app.post("/api/v1/render", response_model=TaskCreatedResponse)
def create_render(req: RenderRequest, background_tasks: BackgroundTasks):
    """
    Створює проєкт + задачу, запускає pipeline асинхронно у фоновому потоці.
    Повертає task_id негайно — клієнт поллінгує GET /api/v1/render/{task_id}.
    """
    project = create_project(
        user_id=req.user_id,
        topic=req.topic,
        language=req.language.value,
    )
    task = create_task(project, request_data=req.model_dump())

    # Build initial state for LangGraph
    initial_state = {
        "topic": req.topic,
        "language": req.language.value,
        "duration_sec": req.duration_sec,
        "style": req.style,
        "user_id": req.user_id,
        "project_id": project.project_id,
        "marketing_chunks": [],
        "child_dev_chunks": [],
        "search_candidates": [],
        "selected_assets": [],
        "errors": [],
    }

    # Render config
    if req.render_config:
        rc_dict = {}
        if req.render_config.video:
            rc_dict["video"] = req.render_config.video.model_dump()
        if req.render_config.text:
            rc_dict["text"] = req.render_config.text.model_dump()
        if req.render_config.audio:
            rc_dict["audio"] = req.render_config.audio.model_dump()
        initial_state["render_config"] = rc_dict

    # Intent override
    if any([req.emotion, req.pain_point, req.reel_type, req.age_focus]):
        initial_state["intent"] = {
            "emotion": req.emotion or "curiosity",
            "pain_point": req.pain_point or "",
            "reel_type": req.reel_type or "expert",
            "age_focus": req.age_focus or "0-6",
        }

    task.status = TaskStatus.processing

    # Запускаємо у фоновому потоці — FastAPI BackgroundTasks
    background_tasks.add_task(_run_pipeline, task.task_id, initial_state)

    return TaskCreatedResponse(
        task_id=task.task_id,
        project_id=project.project_id,
        status=task.status,
    )


# ─── GET /api/v1/render/{task_id} — статус задачі ───

@app.get("/api/v1/render/{task_id}", response_model=TaskResponse)
def get_render_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    script_resp = None
    policy_resp = None
    shots_resp = None

    if task.result:
        s = task.result.get("script")
        if s:
            script_resp = ScriptResponse(**s)
        p = task.result.get("policy_result")
        if p:
            issues = [PolicyIssueResponse(**i) for i in p.get("issues", []) if isinstance(i, dict)]
            policy_resp = PolicyResponse(approved=p.get("approved", False), issues=issues)
        sh = task.result.get("shot_list")
        if sh:
            shots_resp = [ShotResponse(**shot) for shot in sh if isinstance(shot, dict)]

    return TaskResponse(
        task_id=task.task_id,
        project_id=task.project_id,
        status=task.status,
        created_at=task.created_at,
        script=script_resp,
        policy=policy_resp,
        shots=shots_resp,
        voice_duration_sec=task.result.get("voice_duration_sec") if task.result else None,
        preview_url=task.result.get("preview_url") if task.result else None,
    )


# ─── POST /api/v1/render/{task_id}/edit — редагувати версію ───

@app.post("/api/v1/render/{task_id}/edit", response_model=TaskResponse)
def edit_render(task_id: str, req: EditRequest):
    """
    Редагує частину сценарію і перезапускає policy_review.
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.result or not task.result.get("script"):
        raise HTTPException(status_code=400, detail="Task has no script to edit")

    script = dict(task.result["script"])

    allowed_fields = {"hook", "body", "cta", "text_overlays"}
    if req.field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Editable fields: {', '.join(sorted(allowed_fields))}")

    script[req.field] = req.value

    # Re-run only policy_review on the edited script
    from app.nodes.policy_review import policy_review as run_policy

    review_state = {
        "topic": task.request_data.get("topic", ""),
        "normalized_topic": task.request_data.get("topic", ""),
        "language": task.request_data.get("language", "uk"),
        "intent": task.request_data.get("intent", {"age_focus": "0-6"}),
        "script": script,
        "errors": [],
    }

    try:
        review_result = run_policy(review_state)
        task.result["script"] = review_result.get("script", script)
        task.result["policy_result"] = review_result.get("policy_result")

        approved = review_result.get("policy_result", {}).get("approved", False)
        task.status = TaskStatus.done if approved else TaskStatus.review_needed
    except Exception as e:
        task.result["script"] = script
        task.status = TaskStatus.failed
        task.result["errors"] = [str(e)]

    save_task(task)
    return get_render_status(task_id)


# ─── GET /api/v1/projects/{project_id} — дані проєкту ───

@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
def get_project_data(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    versions = []
    for t in project.tasks:
        versions.append(get_render_status(t.task_id))

    return ProjectResponse(
        project_id=project.project_id,
        user_id=project.user_id,
        topic=project.topic,
        language=project.language,
        versions=versions,
    )
