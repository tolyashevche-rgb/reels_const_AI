import operator
from typing import TypedDict, Optional, List, Annotated


class IntentDict(TypedDict):
    emotion: str        # joy, fear, curiosity, pride, guilt
    pain_point: str     # що турбує батьків
    reel_type: str      # expert | promo | trust | story
    age_focus: str      # "0-1" | "1-3" | "3-6" | "0-6"


class ScriptDict(TypedDict):
    hook: str                    # перші 2-3 сек (мовлення)
    body: str                    # основний контент (мовлення)
    cta: str                     # заклик до дії (мовлення)
    text_overlays: List[str]     # текст поверх відео (6-8 слів кожен)
    duration_hint_sec: int       # цільова тривалість


class PolicyIssue(TypedDict):
    severity: str       # CRITICAL | IMPORTANT | STYLE
    quote: str          # цитата зі сценарію
    reason: str         # чому це проблема


class PolicyResult(TypedDict):
    approved: bool
    issues: List[PolicyIssue]                  # список знайдених проблем
    revised_script: Optional[ScriptDict]       # виправлений скрипт або null


class ShotDict(TypedDict):
    order: int              # порядковий номер кадру
    description: str        # опис візуального контенту (для пошуку відео)
    duration_sec: float     # тривалість кадру в секундах
    text_overlay: str       # текст поверх відео
    audio_cue: str          # частина сценарію для voice-over


class ReelsState(TypedDict):
    # --- Вхід від користувача ---
    topic: str
    language: str           # "uk" | "en" | "ru"
    duration_sec: int       # 15 | 30 | 60
    style: str              # "warm_expert" | "energetic" | "calm_story"
    user_id: str
    project_id: str

    # --- Виходи вузлів ---
    normalized_topic: str
    intent: IntentDict
    marketing_chunks: List[str]     # RAG chunks з маркетингової бази
    child_dev_chunks: List[str]     # RAG chunks з бази дитячого розвитку
    script: ScriptDict
    policy_result: PolicyResult
    shot_list: List[ShotDict]

    # --- Системне ---
    errors: Annotated[List[str], operator.add]
