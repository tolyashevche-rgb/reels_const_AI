from app.state import ReelsState


def retrieve_knowledge(state: ReelsState) -> dict:
    """
    Вузли 3a + 3b: Витягує релевантні chunks з ChromaDB.
    Запити: marketing_knowledge + child_dev_knowledge.
    Якщо ChromaDB порожня — повертає пусті списки (pipeline продовжується).
    """
    topic = state.get("normalized_topic", state.get("topic", ""))
    intent = state.get("intent", {})
    age = intent.get("age_focus", "0-6")
    emotion = intent.get("emotion", "")

    query_text = f"{topic} {age} {emotion}".strip()

    marketing_chunks: list[str] = []
    child_dev_chunks: list[str] = []

    try:
        from app.chroma_store import get_collection

        # 3a: marketing knowledge
        marketing_col = get_collection("marketing_knowledge")
        if marketing_col.count() > 0:
            results = marketing_col.query(query_texts=[query_text], n_results=5)
            marketing_chunks = results["documents"][0] if results["documents"] else []

        # 3b: child development knowledge
        child_dev_col = get_collection("child_dev_knowledge")
        if child_dev_col.count() > 0:
            results = child_dev_col.query(query_texts=[query_text], n_results=5)
            child_dev_chunks = results["documents"][0] if results["documents"] else []

    except Exception as e:
        return {
            "marketing_chunks": marketing_chunks,
            "child_dev_chunks": child_dev_chunks,
            "errors": [f"retrieve_knowledge error: {str(e)}"],
        }

    return {
        "marketing_chunks": marketing_chunks,
        "child_dev_chunks": child_dev_chunks,
    }
