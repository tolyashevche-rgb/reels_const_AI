from langgraph.graph import StateGraph, END

from app.state import ReelsState
from app.nodes.script_writer import script_writer
from app.nodes.policy_review import policy_review


def build_content_graph():
    """
    MVP 1 — Content Engine
    Тема → script_writer → policy_review → результат

    Наступні вузли (MVP 2+):
      shot_planner → twelvelabs_search → asset_selector
      → voiceover_generate → render_compose → preview_publish
    """
    graph = StateGraph(ReelsState)

    graph.add_node("script_writer", script_writer)
    graph.add_node("policy_review", policy_review)

    graph.set_entry_point("script_writer")
    graph.add_edge("script_writer", "policy_review")
    graph.add_edge("policy_review", END)

    return graph.compile()


# Singleton — імпортується в main.py і тестах
content_graph = build_content_graph()
