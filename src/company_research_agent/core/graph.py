"""Builds the LangGraph research workflow from its nodes and routing functions."""

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from company_research_agent.core.nodes import (
    ResearchNodes,
    SearchTool,
    route_after_review,
    route_to_researchers,
)
from company_research_agent.core.state import QuestionTask, ResearchState

type ResearchGraph = CompiledStateGraph[ResearchState, None, ResearchState, ResearchState]


def build_graph(
    llm: BaseChatModel,
    search: SearchTool,
    checkpointer: BaseCheckpointSaver[str],
    max_revisions: int,
) -> ResearchGraph:
    nodes = ResearchNodes(llm, search, max_revisions)
    builder = StateGraph(ResearchState)
    builder.add_node("planner", nodes.planner)
    builder.add_node("human_approval", nodes.human_approval)
    builder.add_node("researcher", nodes.researcher, input_schema=QuestionTask)
    builder.add_node("writer", nodes.writer)
    builder.add_node("reviewer", nodes.reviewer)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "human_approval")
    builder.add_conditional_edges("human_approval", route_to_researchers, ["researcher"])
    builder.add_edge("researcher", "writer")
    builder.add_edge("writer", "reviewer")
    builder.add_conditional_edges("reviewer", route_after_review, ["writer", "__end__"])
    return builder.compile(checkpointer=checkpointer)
