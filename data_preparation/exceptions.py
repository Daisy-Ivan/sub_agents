"""Custom exceptions for the data preparation sub-agent."""

from __future__ import annotations


class DataPreparationError(Exception):
    """Base exception for the data preparation package."""


class DataPreparationConfigurationError(DataPreparationError):
    """Raised when runtime configuration is invalid."""


class DataPreparationSchemaError(DataPreparationError):
    """Raised when a typed schema receives invalid data."""


class DataPreparationStateError(DataPreparationError):
    """Raised when the workflow enters an invalid runtime state."""


class InspectionError(DataPreparationError):
    """Raised when file inspection fails unexpectedly."""


class BundleBuildError(DataPreparationError):
    """Raised when inspection results cannot form a normalized bundle."""


class ReadinessAssessmentError(DataPreparationError):
    """Raised when readiness cannot be assessed safely."""


class RoutingError(DataPreparationError):
    """Raised when routing cannot select a valid path."""


class PlanningError(DataPreparationError):
    """Raised when plan construction fails."""


class PromptTemplateError(DataPreparationError):
    """Raised when a prompt template is missing or cannot be rendered."""


class LLMClientError(DataPreparationError):
    """Raised when the optional LLM client cannot complete a request."""


class BrainError(DataPreparationError):
    """Raised when the optional brain layer returns unusable suggestions."""


class ExecutionError(DataPreparationError):
    """Raised when task execution fails."""


class PreparationValidationError(DataPreparationError):
    """Raised when output validation fails critically."""
