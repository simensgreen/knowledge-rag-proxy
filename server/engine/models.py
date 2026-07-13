"""Engine domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MarkdownResult:
    filename: str
    format: str
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)
