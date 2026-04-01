import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.state import ReelsState
from app.llm import get_llm, invoke_with_retry

llm = get_llm("haiku", max_tokens=1024, temperature=0.3)

SHOT_PLANNER_PROMPT = """You are a shot planner for short-form video (Reels / TikTok / Shorts) about child development (0-6 years).

Given a script (hook + body + CTA + text overlays), create a detailed shot list:
1. **order** — sequential number starting from 1
2. **description** — what should be shown visually (specific, searchable for stock/archive video). Write descriptions in English regardless of script language.
3. **duration_sec** — how long this shot lasts (sum must equal total duration)
4. **text_overlay** — text to display over this shot. CRITICAL: use text_overlays from the script as-is, in the EXACT same language as the script. If more shots than overlays — distribute overlays to the most important shots, leave others empty ("").
5. **audio_cue** — which part of the spoken script plays during this shot

Rules:
- Each shot 2-5 seconds (never longer than 6s for Reels)
- Hook shot grabs attention immediately (close-up, dynamic, emotional)
- Shots should be visually distinct to maintain engagement
- Include B-roll descriptions easy to find in a stock library
- Total duration of all shots must match the script's duration_hint_sec
- NEVER translate text_overlay — keep it exactly in the script's language

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {"order": 1, "description": "...", "duration_sec": 3, "text_overlay": "...", "audio_cue": "..."},
  ...
]"""


def shot_planner(state: ReelsState) -> dict:
    """
    Вузол 6: Створює shot list з таймінгами на основі сценарію.
    Планує візуальний ряд для кожного блоку скрипта.
    Використовує: Claude Haiku 4.5
    """
    script = state.get("script", {})
    if not script:
        return {"errors": ["shot_planner: no script to plan shots for"]}

    duration = script.get("duration_hint_sec", state.get("duration_sec", 30))
    overlays = script.get("text_overlays", [])
    lang = state.get("language", "uk")
    lang_map = {"uk": "Ukrainian", "en": "English", "ru": "Russian"}
    lang_name = lang_map.get(lang, "Ukrainian")

    user_message = f"""Create a shot list for this Reels script.

Total duration: {duration} seconds
Script language: {lang_name} — ALL text_overlay fields MUST be in {lang_name}. Do not translate.

Script:
- Hook: {script.get("hook", "")}
- Body: {script.get("body", "")}
- CTA: {script.get("cta", "")}
- Text overlays (use these as-is): {json.dumps(overlays, ensure_ascii=False)}

Topic: {state.get("normalized_topic", state.get("topic", ""))}
Age focus: {state.get("intent", {}).get("age_focus", "0-6")}

Return ONLY a valid JSON array."""

    try:
        response = invoke_with_retry(llm, [
            SystemMessage(content=SHOT_PLANNER_PROMPT),
            HumanMessage(content=user_message),
        ])
        content = response.content
        start = content.find("[")
        end = content.rfind("]") + 1
        shot_list = json.loads(content[start:end])
        return {"shot_list": shot_list}
    except Exception as e:
        return {"errors": [f"shot_planner error: {str(e)}"]}
