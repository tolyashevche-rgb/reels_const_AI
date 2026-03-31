import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.state import ReelsState
from app.llm import get_llm

llm = get_llm("haiku", max_tokens=512, temperature=0.1)

NORMALIZER_PROMPT = """You are a text normalizer for a Reels content pipeline about child development (0-6 years).

Your task:
1. Clean and normalize the user's topic:
   - Fix typos, expand abbreviations
   - Ensure the topic is clear and specific
   - If the topic is too vague, make it more specific while preserving the original meaning
   - Keep the topic in the target language
2. Output a clean, actionable topic sentence

Return ONLY valid JSON (no markdown, no explanation):
{
  "normalized_topic": "clean topic text"
}"""


def input_normalizer(state: ReelsState) -> dict:
    """
    Вузол 1: Нормалізація теми, мови, стилю.
    Очищає вхідний текст для подальших вузлів.
    Використовує: Claude Haiku 4.5
    """
    topic = state.get("topic", "")
    language = state.get("language", "uk")
    lang_map = {"uk": "Ukrainian", "en": "English", "ru": "Russian"}
    lang_name = lang_map.get(language, "Ukrainian")

    user_message = f"""Normalize this topic for a Reels video about child development.

Target language: {lang_name}
Raw topic: {topic}

Return ONLY valid JSON."""

    try:
        response = llm.invoke([
            SystemMessage(content=NORMALIZER_PROMPT),
            HumanMessage(content=user_message),
        ])
        content = response.content
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])
        return {"normalized_topic": data["normalized_topic"]}
    except Exception as e:
        return {
            "normalized_topic": topic,
            "errors": [f"input_normalizer error: {str(e)}"],
        }
