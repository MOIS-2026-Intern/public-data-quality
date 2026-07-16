from __future__ import annotations

import os
from dataclasses import dataclass

from backend.application.agents import (
    CategoricalSemanticValidationAgent,
    FinalFindingVerificationAgent,
    LLMRoutingAgent,
    ReferenceLoaderAgent,
    SchemaParsingAgent,
    SemanticProfilingAgent,
)
from backend.application.dto import PipelineExecutionRequest
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


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class PipelineAgents:
    dataset_gateway: FilesystemDatasetGateway
    reference_loader: ReferenceLoaderAgent
    schema_parser: SchemaParsingAgent
    rule_router: LLMRoutingAgent
    semantic_profiler: SemanticProfilingAgent
    categorical_semantic_validator: CategoricalSemanticValidationAgent
    final_finding_verifier: FinalFindingVerificationAgent


def _fast_model_name(
    *,
    request: PipelineExecutionRequest,
) -> str:
    return (
        request.llm_fast_model
        or request.llm_model
        or _first_env("BIZROUTER_FAST_MODEL", "OPENAI_FAST_MODEL", "BIZROUTER_MODEL", "OPENAI_MODEL")
        or LLM_FAST_MODEL
    )


def _strong_model_name(
    *,
    request: PipelineExecutionRequest,
) -> str:
    return (
        request.llm_strong_model
        or _first_env("BIZROUTER_STRONG_MODEL", "OPENAI_STRONG_MODEL")
        or request.llm_model
        or _first_env("BIZROUTER_MODEL", "OPENAI_MODEL")
        or LLM_STRONG_MODEL
    )


def build_agents(request: PipelineExecutionRequest) -> PipelineAgents:
    dataset_gateway = FilesystemDatasetGateway()
    column_resolver = None
    semantic_profiler = None
    categorical_validator = None
    final_finding_verifier = None

    if request.use_llm_agents:
        ensure_runtime_environment()
        fast_llm = ChatLLMClient(
            model_name=_fast_model_name(request=request),
            api_key=request.openai_api_key,
        )
        strong_llm = ChatLLMClient(
            model_name=_strong_model_name(request=request),
            api_key=request.openai_api_key,
        )

        if fast_llm.enabled:
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

    return PipelineAgents(
        dataset_gateway=dataset_gateway,
        reference_loader=ReferenceLoaderAgent(dataset_gateway=dataset_gateway),
        schema_parser=SchemaParsingAgent(),
        rule_router=LLMRoutingAgent(column_resolver=column_resolver),
        semantic_profiler=SemanticProfilingAgent(semantic_profiler=semantic_profiler),
        categorical_semantic_validator=CategoricalSemanticValidationAgent(validator=categorical_validator),
        final_finding_verifier=FinalFindingVerificationAgent(verifier=final_finding_verifier),
    )
