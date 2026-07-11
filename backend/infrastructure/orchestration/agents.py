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
from backend.config.constants import LLM_FAST_MODEL, LLM_STRONG_MODEL
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
    openai_api_key: str | None = None,
    llm_model: str | None = None,
    llm_fast_model: str | None = None,
    llm_strong_model: str | None = None,
) -> dict[str, object]:
    dataset_gateway = FilesystemDatasetGateway()
    fast_model_name = _fast_model_name(llm_fast_model=llm_fast_model)
    strong_model_name = _strong_model_name(llm_model=llm_model, llm_strong_model=llm_strong_model)

    column_resolver = LLMColumnResolver(
        fast_llm=ChatLLMClient(model_name=fast_model_name, api_key=openai_api_key),
        strong_llm=ChatLLMClient(model_name=strong_model_name, api_key=openai_api_key),
    )
    semantic_profiler = LLMSemanticProfiler(
        fast_llm=ChatLLMClient(model_name=fast_model_name, api_key=openai_api_key),
        strong_llm=ChatLLMClient(model_name=strong_model_name, api_key=openai_api_key),
    )
    categorical_validator = LLMCategoricalValueValidator(
        fast_llm=ChatLLMClient(model_name=fast_model_name, api_key=openai_api_key),
        strong_llm=ChatLLMClient(model_name=strong_model_name, api_key=openai_api_key),
    )
    final_finding_verifier = LLMFinalFindingVerifier(
        llm=ChatLLMClient(model_name=strong_model_name, api_key=openai_api_key),
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
