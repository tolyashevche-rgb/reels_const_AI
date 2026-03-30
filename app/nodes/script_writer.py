import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from app.state import ReelsState, ScriptDict
from app.prompts.marketing_expert import MARKETING_EXPERT_SYSTEM, REELS_FORMAT_GUIDE
from app.prompts.child_dev_expert import CHILD_DEV_EXPERT_SYSTEM

llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=2048, temperature=0.7)


def script_writer(state: ReelsState) -> dict:
    """
    Вузол 4: Генерує hook + body + CTA + text_overlays.
    Поєднує маркетингову експертизу, формат рілзів та знання про дитячий розвиток.
    Використовує: Claude 3.5 Haiku
    """
    duration = state.get("duration_sec", 30)
    body_end = max(duration - 5, 10)

    format_guide = REELS_FORMAT_GUIDE.format(
        duration_sec=duration,
        body_end=body_end,
        language=state.get("language", "uk"),
        style=state.get("style", "warm_expert"),
    )

    marketing_context = "\n\n---\n\n".join(state.get("marketing_chunks", []))
    child_dev_context = "\n\n---\n\n".join(state.get("child_dev_chunks", []))
    intent = state.get("intent", {})

    system_prompt = f"""{MARKETING_EXPERT_SYSTEM}

{CHILD_DEV_EXPERT_SYSTEM}

{format_guide}

You are the intersection of both roles: a marketing expert who only writes content that is scientifically accurate about child development, and a child development expert who knows how to make content stop the scroll."""

    knowledge_section = ""
    if marketing_context:
        knowledge_section += f"\n\n=== MARKETING KNOWLEDGE ===\n{marketing_context}"
    if child_dev_context:
        knowledge_section += f"\n\n=== CHILD DEVELOPMENT KNOWLEDGE ===\n{child_dev_context}"

    lang = state.get("language", "uk")
    lang_map = {"uk": "Ukrainian", "en": "English", "ru": "Russian"}
    lang_name = lang_map.get(lang, "Ukrainian")

    user_message = f"""Write a Reels script for the following brief:

IMPORTANT: Write ALL script text (hook, body, cta, text_overlays) in {lang_name}.

Topic: {state.get("normalized_topic", state.get("topic"))}
Emotion/pain to address: {intent.get("emotion", "curiosity")} / {intent.get("pain_point", "")}
Reel type: {intent.get("reel_type", "expert")}
Child age focus: {intent.get("age_focus", "0-6")}
{knowledge_section}

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{{
  "hook": "first 2-3 seconds spoken text",
  "body": "main content spoken text",
  "cta": "call to action spoken text",
  "text_overlays": ["overlay text 1", "overlay text 2", "overlay text 3"],
  "duration_hint_sec": {duration}
}}"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        content = response.content
        # Extract JSON even if model wraps it in markdown
        start = content.find("{")
        end = content.rfind("}") + 1
        script: ScriptDict = json.loads(content[start:end])
        return {"script": script}
    except Exception as e:
        return {"errors": [f"script_writer error: {str(e)}"]}
