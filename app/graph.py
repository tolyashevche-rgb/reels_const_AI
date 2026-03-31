from langgraph.graph import StateGraph, END

from app.state import ReelsState
from app.nodes.input_normalizer import input_normalizer
from app.nodes.audience_intent_analysis import audience_intent_analysis
from app.nodes.retrieve_knowledge import retrieve_knowledge
from app.nodes.script_writer import script_writer
from app.nodes.policy_review import policy_review
from app.nodes.shot_planner import shot_planner


def build_content_graph():
    """
    MVP 1 — Content Engine
    input_normalizer → audience_intent_analysis → retrieve_knowledge
    → script_writer → policy_review → shot_planner → END
    """
    graph = StateGraph(ReelsState)

    graph.add_node("input_normalizer", input_normalizer)
    graph.add_node("audience_intent_analysis", audience_intent_analysis)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("script_writer", script_writer)
    graph.add_node("policy_review", policy_review)
    graph.add_node("shot_planner", shot_planner)

    graph.set_entry_point("input_normalizer")
    graph.add_edge("input_normalizer", "audience_intent_analysis")
    graph.add_edge("audience_intent_analysis", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "script_writer")
    graph.add_edge("script_writer", "policy_review")
    graph.add_edge("policy_review", "shot_planner")
    graph.add_edge("shot_planner", END)

    return graph.compile()


# Singleton — імпортується в main.py і тестах
content_graph = build_content_graph()
