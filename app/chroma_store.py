"""
ChromaDB client singleton.
Локальна vector DB для RAG — зберігає книги / знання проіндексовані з files/.
"""
import os
import chromadb

CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "chroma_db",
)

client = chromadb.PersistentClient(path=CHROMA_DIR)

# Колекції відповідно до README модуля D
COLLECTIONS = {
    "marketing_knowledge": "Книги продажів, hooks, CTA, storytelling, маркетинг",
    "child_dev_knowledge": "Книги та матеріали фахівців дитячого розвитку 0–6",
    "editorial_guide": "Tone-of-voice, формати, стилі, правила",
    "safe_claims": "Дозволені твердження",
    "banned_claims": "Заборонені / ризикові твердження",
}


def get_collection(name: str):
    """Повертає (або створює) колекцію ChromaDB за іменем."""
    return client.get_or_create_collection(name=name)
