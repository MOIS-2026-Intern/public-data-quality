from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedDataset:
    display_name: str
    path: Path
    source_type: str
    response_type: str | None = None
