import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from typing import Optional

from app.models import (
    RenderRequest, EditRequest, TaskStatus,
    TaskCreatedResponse, TaskResponse, ProjectResponse,
    ScriptResponse, PolicyResponse, PolicyIssueResponse,
)
from app.storage import create_project, create_task, get_task, get_project
from app.graph import content_graph

app = FastAPI(title="Reels Construction AI", version="0.1.0")


# ─── Health ───

@app.get("/")
def health():
    return {"status": "ok", "service": "reels-construction-ai"}


# ─── POST /api/v1/render — створити задачу ───

@app.post("/api/v1/render", response_model=TaskCreatedResponse)
def create_render(req: RenderRequest):
    """
    Створює проєкт + задачу, запускає LangGraph pipeline синхронно (MVP).
    У production замінити на Celery async task.
    """
    project = create_project(
        user_id=req.user_id,
        topic=req.topic,
        language=req.language.value,
    )
    task = create_task(project, request_data=req.model_dump())

    # --- Build initial state for LangGraph ---
    task.status = TaskStatus.processing
    initial_state = {
        "topic": req.topic,
        "normalized_topic": req.topic,
        "language": req.language.value,
        "duration_sec": req.duration_sec,
        "style": req.style,
        "user_id": req.user_id,
        "project_id": project.project_id,
        "intent": {
            "emotion": req.emotion or "curiosity",
            "pain_point": req.pain_point or "",
            "reel_type": req.reel_type or "expert",
            "age_focus": req.age_focus or "0-6",
        },
        "marketing_chunks": [],
        "child_dev_chunks": [],
        "errors": [],
    }

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
            }
    except Exception as e:
        task.status = TaskStatus.failed
        task.result = {"errors": [str(e)]}

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

    if task.result:
        s = task.result.get("script")
        if s:
            script_resp = ScriptResponse(**s)
        p = task.result.get("policy_result")
        if p:
            issues = [PolicyIssueResponse(**i) for i in p.get("issues", []) if isinstance(i, dict)]
            policy_resp = PolicyResponse(approved=p.get("approved", False), issues=issues)

    return TaskResponse(
        task_id=task.task_id,
        project_id=task.project_id,
        status=task.status,
        created_at=task.created_at,
        script=script_resp,
        policy=policy_resp,
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
