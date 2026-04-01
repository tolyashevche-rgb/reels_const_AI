"""
Вузол 8: Asset Selector — розподіляє кліпи з пулу по shots.

Отримує пул кліпів від вузла 7 (1 запит на рілз).
Розподіляє по round-robin: shot 1 → кліп 0, shot 2 → кліп 1, ...
Кожен кліп використовується максимум 1 раз (без повторів).
Якщо пул менший за кількість shots — решта shots стануть placeholder.

Bез LLM — 0 додаткових API запитів.
"""
from app.state import ReelsState


def asset_selector(state: ReelsState) -> dict:
    """
    Вузол 8: Round-robin розподіл кліпів з пулу по shots.
    """
    search_candidates = state.get("search_candidates", [])
    shot_list = state.get("shot_list", [])

    if not search_candidates or not shot_list:
        return {"selected_assets": []}

    # Витягуємо пул кліпів (вузол 7 кладе однаковий пул у кожен shot)
    # Беремо з першого shot що має кандидатів
    pool = []
    for sc in search_candidates:
        candidates = sc.get("candidates", [])
        if candidates:
            pool = candidates
            break

    if not pool:
        return {"selected_assets": []}

    # Round-robin: shot i → pool[i % len(pool)]
    # Але прагнемо уникати повторів — беремо послідовно, потім по колу
    selected_assets = []
    used_indices = set()

    for i, shot in enumerate(shot_list):
        order = shot.get("order", i + 1)
        duration_needed = shot.get("duration_sec", 3)

        # Шукаємо наступний невикористаний кліп достатньої тривалості
        chosen = None
        for j, clip in enumerate(pool):
            if j in used_indices:
                continue
            clip_duration = (clip.get("end") or 0) - (clip.get("start") or 0)
            if clip_duration >= duration_needed * 0.5:  # мінімум половина
                chosen = (j, clip)
                break

        # Якщо всі використані — беремо по колу будь-який достатній
        if chosen is None:
            for j, clip in enumerate(pool):
                clip_duration = (clip.get("end") or 0) - (clip.get("start") or 0)
                if clip_duration >= duration_needed * 0.5:
                    chosen = (j, clip)
                    break

        if chosen is not None:
            j, clip = chosen
            used_indices.add(j)
            selected_assets.append({
                "shot_order": order,
                "selected": {
                    "video_id": clip["video_id"],
                    "index_id": clip["index_id"],
                    "start": clip["start"],
                    "end": clip["end"],
                },
            })
        else:
            # Кліпів не вистачає — placeholder
            selected_assets.append({"shot_order": order, "selected": None})

    real = sum(1 for a in selected_assets if a.get("selected"))
    print(f"[asset_selector] {real}/{len(shot_list)} shots отримали кліп з пулу ({len(pool)} кліпів)")

    return {"selected_assets": selected_assets}
