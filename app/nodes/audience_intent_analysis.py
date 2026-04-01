import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.state import ReelsState, IntentDict
from app.llm import get_llm, invoke_with_retry

llm = get_llm("haiku", max_tokens=512, temperature=0.2)

INTENT_ANALYST_PROMPT = """You are an audience intent analyst for a Reels content platform about child development (0-6 years).

Given a topic, analyze:
1. **emotion** — the primary emotion to trigger in the viewer: joy, fear, curiosity, pride, guilt, surprise, relief
2. **pain_point** — what worries parents about this topic (one sentence)
3. **reel_type** — the best format:
   - "expert" — educational, authoritative advice
   - "promo" — promotional, product/service focused
   - "trust" — building trust and credibility
   - "story" — personal story or case study
4. **age_focus** — which age range: "0-1", "1-3", "3-6", or "0-6" if general

Return ONLY valid JSON (no markdown, no explanation):
{
  "emotion": "...",
  "pain_point": "...",
  "reel_type": "...",
  "age_focus": "..."
}"""


def audience_intent_analysis(state: ReelsState) -> dict:
    """
    Вузол 2: Аналіз аудиторії — емоція, біль, тип рілза, вік.
    Якщо intent вже задано через API override — пропускає аналіз.
    Використовує: Claude Haiku 4.5
    """
    existing = state.get("intent")
    if existing and existing.get("emotion") and existing.get("pain_point"):
        return {}

    topic = state.get("normalized_topic", state.get("topic", ""))

    user_message = f"""Analyze the audience intent for this Reels topic:

Topic: {topic}
Language: {state.get("language", "uk")}

Return ONLY valid JSON."""

    try:
        response = invoke_with_retry(llm, [
            SystemMessage(content=INTENT_ANALYST_PROMPT),
            HumanMessage(content=user_message),
        ])
        content = response.content
        start = content.find("{")
        end = content.rfind("}") + 1
        intent: IntentDict = json.loads(content[start:end])
        return {"intent": intent}
    except Exception as e:
        return {
            "intent": {
                "emotion": "curiosity",
                "pain_point": "",
                "reel_type": "expert",
                "age_focus": "0-6",
            },
            "errors": [f"audience_intent_analysis error: {str(e)}"],
        }
