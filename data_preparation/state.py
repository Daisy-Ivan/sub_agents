"""Explicit runtime states for the data preparation workflow."""

from __future__ import annotations

from enum import Enum


class PreparationState(str, Enum):
    """State machine for the gated sub-agent workflow."""

    INITIALIZED = "initialized"
    INSPECTING = "inspecting"
    INSPECTED = "inspected"
    BUNDLING = "bundling"
    BUNDLED = "bundled"
    ASSESSING_READINESS = "assessing_readiness"
    READINESS_ASSESSED = "readiness_assessed"
    ROUTING = "routing"
    ROUTED = "routed"
    PROCESSING = "processing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Return whether the current state is terminal."""

        return self in {PreparationState.COMPLETED, PreparationState.FAILED}


ALLOWED_STATE_TRANSITIONS: dict[PreparationState, set[PreparationState]] = {
    PreparationState.INITIALIZED: {
        PreparationState.INSPECTING,
        PreparationState.FAILED,
    },
    PreparationState.INSPECTING: {
        PreparationState.INSPECTED,
        PreparationState.FAILED,
    },
    PreparationState.INSPECTED: {
        PreparationState.BUNDLING,
        PreparationState.FAILED,
    },
    PreparationState.BUNDLING: {
        PreparationState.BUNDLED,
        PreparationState.FAILED,
    },
    PreparationState.BUNDLED: {
        PreparationState.ASSESSING_READINESS,
        PreparationState.FAILED,
    },
    PreparationState.ASSESSING_READINESS: {
        PreparationState.READINESS_ASSESSED,
        PreparationState.FAILED,
    },
    PreparationState.READINESS_ASSESSED: {
        PreparationState.ROUTING,
        PreparationState.FAILED,
    },
    PreparationState.ROUTING: {
        PreparationState.ROUTED,
        PreparationState.FAILED,
    },
    PreparationState.ROUTED: {
        PreparationState.PROCESSING,
        PreparationState.VALIDATING,
        PreparationState.COMPLETED,
        PreparationState.FAILED,
    },
    PreparationState.PROCESSING: {
        PreparationState.VALIDATING,
        PreparationState.FAILED,
    },
    PreparationState.VALIDATING: {
        PreparationState.COMPLETED,
        PreparationState.FAILED,
    },
    PreparationState.COMPLETED: set(),
    PreparationState.FAILED: set(),
}


def is_valid_transition(
    current_state: PreparationState,
    next_state: PreparationState,
) -> bool:
    """Return whether a state transition is allowed."""

    return next_state in ALLOWED_STATE_TRANSITIONS[current_state]
