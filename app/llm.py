"""
LLM factory — повертає реальний ChatAnthropic або MockLLM залежно від USE_MOCK env.

    USE_MOCK=1  →  fake відповіді (безкоштовно, для тестування)
    USE_MOCK=0  →  реальний Anthropic API

Використання в nodes:
    from app.llm import get_llm
    llm = get_llm("haiku")    # або "sonnet"
"""
import os
import json
import time


def _is_mock() -> bool:
    return os.getenv("USE_MOCK", "0") == "1"


# ─── Mock LLM ───

class _MockMessage:
    def __init__(self, content: str):
        self.content = content


class MockLLM:
    """Повертає заздалегідь визначені JSON-відповіді для кожного вузла."""

    _RESPONSES = {
        "input_normalizer": json.dumps({
            "normalized_topic": "Як розвивати мовлення дитини від 1 до 3 років через щоденні ігри",
        }),
        "audience_intent_analysis": json.dumps({
            "emotion": "curiosity",
            "pain_point": "Батьки хвилюються, що дитина мало говорить для свого віку",
            "reel_type": "expert",
            "age_focus": "1-3",
        }),
        "script_writer": json.dumps({
            "hook": "Ваша дитина мало говорить? Ось що насправді допомагає!",
            "body": "Дослідження показують: діти 1-3 років найкраще розвивають мовлення через гру. "
                    "Три прості прийоми щодня: перший — називайте все, що бачите на прогулянці. "
                    "Другий — читайте одну книжку перед сном і ставте питання по картинках. "
                    "Третій — грайте в 'телефон' — дитина повторює слова і вчиться діалогу. "
                    "Кожна дитина розвивається у своєму темпі, але ці активності підтримують мовленнєвий розвиток.",
            "cta": "Збережіть це відео і спробуйте сьогодні! Напишіть в коментарях, скільки слів говорить ваш малюк 👇",
            "text_overlays": [
                "Дитина мало говорить? 🤔",
                "3 прийоми щодня ✨",
                "Називайте все навколо 🌳",
                "Читайте + питання 📚",
                "Гра у 'телефон' 📞",
                "Збережіть собі! 💾",
            ],
            "duration_hint_sec": 30,
        }),
        "policy_review": json.dumps({
            "approved": True,
            "issues": [
                {
                    "severity": "STYLE",
                    "quote": "Ось що насправді допомагає!",
                    "reason": "Трохи категоричне формулювання, краще 'що може допомогти'",
                }
            ],
            "revised_script": None,
        }),
        "shot_planner": json.dumps([
            {"order": 1, "description": "Close-up of toddler (1-2 years) trying to speak, mouth moving, cute expression", "duration_sec": 3, "text_overlay": "Дитина мало говорить? 🤔", "audio_cue": "Ваша дитина мало говорить? Ось що насправді допомагає!"},
            {"order": 2, "description": "Parent and child walking outdoors, parent pointing at trees and objects", "duration_sec": 5, "text_overlay": "3 прийоми щодня ✨", "audio_cue": "Дослідження показують: діти 1-3 років найкраще розвивають мовлення через гру."},
            {"order": 3, "description": "Close-up of parent naming objects on a walk — flowers, dog, car", "duration_sec": 5, "text_overlay": "Називайте все навколо 🌳", "audio_cue": "Перший — називайте все, що бачите на прогулянці."},
            {"order": 4, "description": "Cozy bedtime scene, parent reading picture book to toddler", "duration_sec": 5, "text_overlay": "Читайте + питання 📚", "audio_cue": "Другий — читайте одну книжку перед сном і ставте питання по картинках."},
            {"order": 5, "description": "Toddler holding toy phone, 'talking' and laughing with parent", "duration_sec": 5, "text_overlay": "Гра у 'телефон' 📞", "audio_cue": "Третій — грайте в 'телефон' — дитина повторює слова і вчиться діалогу."},
            {"order": 6, "description": "Happy toddler speaking first words, parent's proud reaction", "duration_sec": 4, "text_overlay": "", "audio_cue": "Кожна дитина розвивається у своєму темпі, але ці активності підтримують мовленнєвий розвиток."},
            {"order": 7, "description": "Animated save/bookmark icon, warm gradient background", "duration_sec": 3, "text_overlay": "Збережіть собі! 💾", "audio_cue": "Збережіть це відео і спробуйте сьогодні!"},
        ]),
    }

    def __init__(self, **kwargs):
        self._node_hint = None

    def invoke(self, messages, **kwargs):
        # Визначаємо вузол по контексту повідомлення
        text = " ".join(m.content for m in messages if hasattr(m, "content"))
        node = self._guess_node(text)
        response = self._RESPONSES.get(node, '{"error": "unknown mock node"}')
        return _MockMessage(response)

    def _guess_node(self, text: str) -> str:
        text_lower = text.lower()
        if "normalize" in text_lower or "normalizer" in text_lower:
            return "input_normalizer"
        if "audience intent" in text_lower or "intent analyst" in text_lower:
            return "audience_intent_analysis"
        if "shot planner" in text_lower or "shot list" in text_lower:
            return "shot_planner"
        if "policy" in text_lower or "safety reviewer" in text_lower:
            return "policy_review"
        if "reels script" in text_lower or "hook" in text_lower:
            return "script_writer"
        return "script_writer"


# ─── Retry helper ───

def invoke_with_retry(llm, messages, max_attempts: int = 3, base_delay: float = 5.0, fallback_tier: str | None = None):
    """
    Викликає llm.invoke з exponential backoff при помилці 529 (overloaded).
    Якщо fallback_tier вказано — після всіх спроб пробує з дешевшою моделлю.
    Повертає response або кидає останній виняток.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return llm.invoke(messages)
        except Exception as e:
            err_str = str(e)
            # Retry тільки при overloaded (529) або rate-limit (429)
            if "529" in err_str or "overloaded" in err_str.lower() or "429" in err_str:
                delay = base_delay * (2 ** attempt)  # 5, 10, 20s
                print(f"[llm] API overloaded, retry {attempt+1}/{max_attempts} після {delay:.0f}s...")
                time.sleep(delay)
                last_exc = e
            else:
                raise

    # Fallback на іншу модель (якщо вказано)
    if fallback_tier and not _is_mock():
        print(f"[llm] Fallback на {fallback_tier} після {max_attempts} невдалих спроб")
        fallback_llm = get_llm(fallback_tier)
        return fallback_llm.invoke(messages)

    raise last_exc


# ─── Factory ───

def get_llm(tier: str = "haiku", **overrides):
    """
    Повертає LLM клієнт.

    tier: "haiku" або "sonnet"
    overrides: max_tokens, temperature — перевизначають дефолти
    """
    if _is_mock():
        return MockLLM(**overrides)

    from langchain_anthropic import ChatAnthropic

    defaults = {
        "haiku": {"model": "claude-haiku-4-5-20251001", "max_tokens": 512, "temperature": 0.2},
        "sonnet": {"model": "claude-sonnet-4-6", "max_tokens": 2048, "temperature": 0.7},
        "opus": {"model": "claude-opus-4-5", "max_tokens": 1500, "temperature": 0.7},
    }
    params = {**defaults.get(tier, defaults["haiku"]), **overrides}

    # Force direct Anthropic API — bypass VS Code proxy that returns SSE streams
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        params["anthropic_api_key"] = api_key
        params["anthropic_api_url"] = "https://api.anthropic.com"

    return ChatAnthropic(**params)
