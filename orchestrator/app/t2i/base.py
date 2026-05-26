"""Base interface for EasyAds text-to-image engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


class BaseT2IEngine(ABC):
    """Common lifecycle and generation interface for T2I engines."""

    name: str

    @abstractmethod
    def load(self) -> None:
        """Load model/client resources."""
        raise NotImplementedError

    @abstractmethod
    def unload(self) -> None:
        """Release model/client resources."""
        raise NotImplementedError

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return whether the engine is ready to generate."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return availability and diagnostic information."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, request: T2IRequest) -> T2IResult:
        """Generate one or more images from a text prompt."""
        raise NotImplementedError