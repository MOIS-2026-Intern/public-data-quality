from __future__ import annotations

import os

from backend.application.agents import (
    CategoricalSemanticValidationAgent,
    FinalFindingVerificationAgent,
    LLMRoutingAgent,
    ReferenceLoaderAgent,
    SchemaParsingAgent,
    SemanticProfilingAgent,
)
from backend.application.services import (
    LLMCategoricalValueValidator,
    LLMColumnResolver,
    LLMFinalFindingVerifier,
    LLMSemanticProfiler,
)
from backend.config.llm import LLM_FAST_MODEL, LLM_STRONG_MODEL
from backend.config.env import ensure_runtime_environment
from backend.infrastructure.io.dataset_gateway import FilesystemDatasetGateway
from backend.infrastructure.llm import ChatLLMClient


def _fast_model_name(
    *,
    llm_fast_model: str | None,
) -> str:
    return llm_fast_model or os.getenv("OPENAI_FAST_MODEL") or os.getenv("OPENAI_MODEL") or LLM_FAST_MODEL


def _strong_model_name(
    *,
    llm_model: str | None,
    llm_strong_model: str | None,
) -> str:
    return llm_strong_model or os.getenv("OPENAI_STRONG_MODEL") or llm_model or LLM_STRONG_MODEL


def build_agents(
    *,
    use_llm_agents: bool = False,
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
) -> dict[str, object]:
    dataset_gateway = FilesystemDatasetGateway()
    column_resolver = None
    semantic_profiler = None
    categorical_validator = None
    final_finding_verifier = None

    if use_llm_agents:
        ensure_runtime_environment()
        fast_model_name = _fast_model_name(llm_fast_model=llm_fast_model)
        strong_model_name = _strong_model_name(llm_model=llm_model, llm_strong_model=llm_strong_model)
        fast_llm = ChatLLMClient(model_name=fast_model_name, api_key=openai_api_key)
        strong_llm = ChatLLMClient(model_name=strong_model_name, api_key=openai_api_key)

        column_resolver = LLMColumnResolver(
            fast_llm=fast_llm,
            strong_llm=strong_llm,
        )
        semantic_profiler = LLMSemanticProfiler(
            fast_llm=fast_llm,
            strong_llm=strong_llm,
        )
        categorical_validator = LLMCategoricalValueValidator(
            fast_llm=fast_llm,
            strong_llm=strong_llm,
        )
        final_finding_verifier = LLMFinalFindingVerifier(
            llm=strong_llm,
        )
    return {
        "dataset_gateway": dataset_gateway,
        "reference_loader": ReferenceLoaderAgent(dataset_gateway=dataset_gateway),
        "schema_parser": SchemaParsingAgent(),
        "rule_router": LLMRoutingAgent(column_resolver=column_resolver),
        "semantic_profiler": SemanticProfilingAgent(semantic_profiler=semantic_profiler),
        "categorical_semantic_validator": CategoricalSemanticValidationAgent(validator=categorical_validator),
        "final_finding_verifier": FinalFindingVerificationAgent(verifier=final_finding_verifier),
    }
