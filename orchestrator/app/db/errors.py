"""Database layer errors."""

from __future__ import annotations


class DatabaseConfigurationError(RuntimeError):
    """Raised when DB backend configuration is invalid."""


class DatabaseDependencyError(RuntimeError):
    """Raised when an optional database dependency is unavailable."""
