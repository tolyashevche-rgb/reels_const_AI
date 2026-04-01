"""
Вузол 7: TwelveLabs Search — 1 запит на весь рілз.

Замість окремого пошуку для кожного shot — один запит по темі + скрипту.
Повертає пул кліпів достатній для покриття всієї тривалості рілзу.
Asset Selector (вузол 8) розподіляє їх по shots без LLM.

Витрати API: 1 запит на рілз (незалежно від кількості shots).
"""
import math
from app.state import ReelsState
from app.twelvelabs_client import get_twelvelabs_client

# Модальність пошуку
SEARCH_OPTIONS = ["visual"]

# Пріоритетний індекс (найбільша бібліотека)
PRIMARY_INDEX = "69baaa2f698c5b93064f2e9e"


def _build_query(state: ReelsState) -> str:
    """
    Формує один пошуковий запит з теми + hook скрипту.
    Англійською — TwelveLabs краще шукає по EN.
    """
    topic = state.get("normalized_topic", state.get("topic", ""))
    script = state.get("script") or {}
    hook = script.get("hook", "")
    intent = state.get("intent") or {}
    age = intent.get("age_focus", "0-6")

    # Короткий опис для semantic пошуку
    parts = [f"child development age {age}"]
    if topic:
        parts.append(topic[:80])
    if hook:
        parts.append(hook[:80])
    return ", ".join(parts)


def twelvelabs_search(state: ReelsState) -> dict:
    """
    Вузол 7: 1 запит до TwelveLabs на весь рілз.
    Повертає пул кліпів у форматі search_candidates сумісному з asset_selector.
    """
    shot_list = state.get("shot_list", [])
    duration_sec = state.get("duration_sec", 30)

    if not shot_list:
        return {"errors": ["twelvelabs_search: no shot_list"]}

    # Скільки кліпів потрібно: shots_count + запас
    clips_needed = len(shot_list) + 2

    client = get_twelvelabs_client()

    # ── Mock mode ──
    if client is None:
        return {
            "search_candidates": [
                {"shot_order": s.get("order", i + 1), "candidates": []}
                for i, s in enumerate(shot_list)
            ]
        }

    # ── Визначаємо індекс ──
    index_id = PRIMARY_INDEX

    # ── 1 запит ──
    query = _build_query(state)
    print(f"[twelvelabs] 1 запит: index={index_id}, clips_needed={clips_needed}")
    print(f"[twelvelabs] query: {query[:120]}")

    try:
        results = client.search.query(
            index_id=index_id,
            query_text=query,
            search_options=SEARCH_OPTIONS,
            group_by="clip",
            threshold="low",
            page_limit=clips_needed,
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "too_many_requests" in err_str:
            print("[twelvelabs] ⚠ Rate limit (429) — ліміт запитів вичерпано!")
        else:
            print(f"[twelvelabs] Search error: {err_str[:200]}")
        return {
            "search_candidates": [
                {"shot_order": s.get("order", i + 1), "candidates": []}
                for i, s in enumerate(shot_list)
            ],
            "errors": [f"twelvelabs_search: {err_str[:200]}"],
        }

    # ── Збираємо пул кліпів ──
    pool = []
    for item in results:
        pool.append({
            "video_id": item.video_id,
            "index_id": index_id,
            "score": item.score,
            "start": item.start,
            "end": item.end,
            "confidence": item.confidence,
            "thumbnail_url": item.thumbnail_url,
        })
        if len(pool) >= clips_needed:
            break

    print(f"[twelvelabs] Знайдено {len(pool)} кліпів в пулі")

    # ── Прив'язуємо пул до кожного shot як candidates ──
    # Asset selector (вузол 8) розподілить їх по round-robin
    search_candidates = [
        {
            "shot_order": shot.get("order", i + 1),
            "candidates": pool,   # всі shots бачать весь пул
        }
        for i, shot in enumerate(shot_list)
    ]

    return {"search_candidates": search_candidates}
