from __future__ import annotations

from langgraph.graph import END, START, StateGraph

try:
    from backend.application.dto.pipeline import PipelineState
    from backend.application.services.pipeline import propose_repairs, validate_quality, verify_results
    from backend.application.services.pipeline.profiling import profile_values
    from backend.infrastructure.orchestration.agents import build_agents
except ImportError:  # pragma: no cover
    if __package__:
        raise
    from backend.application.dto.pipeline import PipelineState
    from backend.application.services.pipeline import propose_repairs, validate_quality, verify_results
    from backend.application.services.pipeline.profiling import profile_values
    from backend.infrastructure.orchestration.agents import build_agents


def build_graph(
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
):
    agents = build_agents(
        use_llm_agents=use_llm_agents,
        openai_api_key=openai_api_key,
        llm_model=llm_model,
        llm_fast_model=llm_fast_model,
        llm_strong_model=llm_strong_model,
    )
    graph = StateGraph(PipelineState)
    graph.add_node("load_reference_data", agents["reference_loader"].run)
    graph.add_node("normalize_columns", agents["schema_parser"].run)
    graph.add_node(
        "profile_values",
        lambda state: profile_values(state, dataset_gateway=agents["dataset_gateway"]),
    )
    graph.add_node("route_rules", agents["rule_router"].run)
    graph.add_node("semantic_profile", agents["semantic_profiler"].run)
    graph.add_node("validate", validate_quality)
    graph.add_node("categorical_semantic_validate", agents["categorical_semantic_validator"].run)
    graph.add_node("propose_repairs", propose_repairs)
    graph.add_node("final_finding_verify", agents["final_finding_verifier"].run)
    graph.add_node("verify_results", verify_results)

    graph.add_edge(START, "load_reference_data")
    graph.add_edge("load_reference_data", "normalize_columns")
    graph.add_edge("normalize_columns", "profile_values")
    graph.add_edge("profile_values", "route_rules")
    graph.add_edge("route_rules", "semantic_profile")
    graph.add_edge("semantic_profile", "validate")
    graph.add_edge("validate", "categorical_semantic_validate")
    graph.add_edge("categorical_semantic_validate", "propose_repairs")
    graph.add_edge("propose_repairs", "final_finding_verify")
    graph.add_edge("final_finding_verify", "verify_results")
    graph.add_edge("verify_results", END)
    return graph.compile()
