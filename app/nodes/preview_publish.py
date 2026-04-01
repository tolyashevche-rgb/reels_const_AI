"""
Вузол 11: Публікація preview — копіює фінальний render у preview директорію.
Повертає preview_url (локальний шлях або URL для API).
"""
import os
import shutil
import uuid

from app.state import ReelsState

PREVIEW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media", "previews",
)


def preview_publish(state: ReelsState) -> dict:
    """
    Вузол 11: Копіює render у preview та повертає URL.
    """
    render_output = state.get("render_output", "")
    if not render_output or not os.path.exists(render_output):
        return {"errors": ["preview_publish: no render_output file"]}

    os.makedirs(PREVIEW_DIR, exist_ok=True)

    project_id = state.get("project_id", uuid.uuid4().hex[:8])
    ext = os.path.splitext(render_output)[1] or ".mp4"
    preview_name = f"{project_id}_preview{ext}"
    preview_path = os.path.join(PREVIEW_DIR, preview_name)

    shutil.copy2(render_output, preview_path)

    # В production тут буде upload на CDN / S3 / Static URL
    # Зараз — локальний файл, який може бути відданий через FastAPI StaticFiles
    preview_url = f"/media/previews/{preview_name}"

    return {"preview_url": preview_url}
