"""Routing-layer scaffold."""

from __future__ import annotations

from typing import Literal

from .config import DataPreparationConfig
from .exceptions import RoutingError
from .schemas import NormalizedInputBundle, ReadinessDecision

RouteName = Literal["direct_output", "processing", "report_only", "unsupported"]


class PreparationRouter:
    """Select an explicit route from readiness outputs."""

    def __init__(self, config: DataPreparationConfig | None = None) -> None:
        self.config = config or DataPreparationConfig()

    def choose_route(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
    ) -> RouteName:
        """Choose a route from bundle readiness."""

        try:
            NormalizedInputBundle.model_validate(bundle)
            normalized_decision = ReadinessDecision.model_validate(readiness_decision)
        except Exception as exc:
            raise RoutingError(f"invalid routing inputs: {exc}") from exc

        status = normalized_decision.bundle_status
        if status == "analysis_ready":
            return "direct_output"
        if status == "partially_ready":
            return self._route_partially_ready()
        if status == "transformable":
            return "processing"
        if status == "view_only":
            return "report_only"
        if status == "unsupported":
            return "unsupported"

        raise RoutingError(f"unsupported readiness status: {status}")

    def _route_partially_ready(self) -> RouteName:
        override = self.config.policy_overrides.get("partially_ready_route")
        if override == "processing":
            return "processing"
        return "direct_output"
