"""
TwelveLabs client singleton.

Ініціалізує клієнт з API ключа (.env → TWELVELABS_API_KEY).
В mock-режимі (USE_MOCK=1) повертає заглушку.
"""
import os
from typing import Optional

_client = None


def get_twelvelabs_client():
    """Повертає TwelveLabs client singleton (або None в mock-режимі)."""
    global _client

    if os.getenv("USE_MOCK", "0") == "1":
        return None

    if _client is None:
        from twelvelabs import TwelveLabs

        api_key = os.getenv("TWELVELABS_API_KEY", "")
        if not api_key:
            raise RuntimeError("TWELVELABS_API_KEY not set in .env")
        _client = TwelveLabs(api_key=api_key)

    return _client


def list_indexes() -> list[dict]:
    """Повертає список індексів з їх id та назвою."""
    client = get_twelvelabs_client()
    if client is None:
        return []
    result = []
    for idx in client.indexes.list():
        result.append({
            "id": idx.id,
            "name": idx.index_name,
            "video_count": getattr(idx, "video_count", 0),
        })
    return result
