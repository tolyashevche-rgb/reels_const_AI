import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from app.state import ReelsState, PolicyResult
from app.prompts.policy_expert import POLICY_EXPERT_SYSTEM

llm = ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=1024, temperature=0.2)


def policy_review(state: ReelsState) -> dict:
    """
    Вузол 5: Перевірка безпеки та точності сценарію.
    Блокує публікацію при критичних проблемах (медичні клейми, шкідливі поради).
    Повертає виправлений скрипт якщо є важливі проблеми.
    Використовує: Claude 3.5 Haiku (низька температура = точне слідування правилам)
    """
    script = state.get("script", {})
    if not script:
        return {"errors": ["policy_review: no script to review"]}

    full_script = (
        f"Hook: {script.get('hook', '')}\n"
        f"Body: {script.get('body', '')}\n"
        f"CTA: {script.get('cta', '')}\n"
        f"Text overlays: {', '.join(script.get('text_overlays', []))}"
    )

    user_message = f"""Review this Reels script about child development:

{full_script}

Context:
- Topic: {state.get("normalized_topic", state.get("topic"))}
- Age focus: {state.get("intent", {}).get("age_focus", "0-6")}
- Language: {state.get("language", "uk")}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "approved": true or false,
  "issues": [
    {{"severity": "CRITICAL|IMPORTANT|STYLE", "quote": "exact text from script", "reason": "why it's an issue"}}
  ],
  "revised_script": null or {{
    "hook": "...",
    "body": "...",
    "cta": "...",
    "text_overlays": ["...", "..."],
    "duration_hint_sec": {script.get("duration_hint_sec", 30)}
  }}
}}

If no issues found: approved=true, issues=[], revised_script=null.
If only STYLE issues: approved=true, include issues, revised_script=null.
If IMPORTANT or CRITICAL issues: approved=false, revised_script must fix all issues."""

    try:
        response = llm.invoke([
            SystemMessage(content=POLICY_EXPERT_SYSTEM),
            HumanMessage(content=user_message),
        ])
        content = response.content
        start = content.find("{")
        end = content.rfind("}") + 1
        policy_result: PolicyResult = json.loads(content[start:end])

        result = {"policy_result": policy_result}
        # If reviewer provided a fixed script, replace the current one
        if policy_result.get("revised_script"):
            result["script"] = policy_result["revised_script"]
        return result

    except Exception as e:
        return {
            "errors": [f"policy_review error: {str(e)}"],
            "policy_result": {"approved": False, "issues": [str(e)], "revised_script": None},
        }
