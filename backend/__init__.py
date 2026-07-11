"""Public-data quality pipeline built with LangGraph."""


def build_graph(*args, **kwargs):
    from .config.env import ensure_runtime_environment
    from .infrastructure.orchestration.graph import build_graph as _build_graph

    ensure_runtime_environment()
    return _build_graph(*args, **kwargs)


def create_app(*args, **kwargs):
    from .config.env import ensure_runtime_environment
    from .adapters.web.app import create_app as _create_app

    ensure_runtime_environment()
    return _create_app(*args, **kwargs)

__all__ = ["build_graph", "create_app"]
