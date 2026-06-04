"""Modal execution errors."""

from __future__ import annotations


class ModalExecutionError(RuntimeError):
    pass


class ModalExecutionUnavailableError(ModalExecutionError):
    pass


class ModalJobSubmitError(ModalExecutionError):
    pass


class ModalJobPollError(ModalExecutionError):
    pass


class ModalResultError(ModalExecutionError):
    pass
