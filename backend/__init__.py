"""Public-data quality pipeline built with LangGraph."""

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def build_graph(*args, **kwargs):
    from .graph import build_graph as _build_graph

    return _build_graph(*args, **kwargs)


def create_app(*args, **kwargs):
    from .web import create_app as _create_app

    return _create_app(*args, **kwargs)

__all__ = ["build_graph", "create_app"]
