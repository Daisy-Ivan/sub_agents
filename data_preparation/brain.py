"""Optional brain-layer orchestration for hybrid and LLM-enhanced modes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any
from uuid import uuid4

from .config import DataPreparationConfig, RuntimeMode
from .exceptions import BrainError, LLMClientError
from .llm_client import LLMClient
from .prompts import load_prompt_template, render_prompt_template
from .router import RouteName
from .schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    ReadinessDecision,
    SubTask,
)
from .tools.registry import ToolRegistry

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


@dataclass(slots=True)
class BrainCallResult:
    """Normalized result of an optional LLM invocation."""

    prompt_name: str
    attempted_llm: bool
    used_llm: bool
    content: str
    fallback_reason: str | None = None
    raw_content: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the call result."""

        return {
            "prompt_name": self.prompt_name,
            "attempted_llm": self.attempted_llm,
            "used_llm": self.used_llm,
            "content": self.content,
            "fallback_reason": self.fallback_reason,
            "raw_content": self.raw_content,
        }


@dataclass(slots=True)
class PlanSuggestionResult:
    """Structured LLM suggestion for optional plan augmentation."""

    prompt_name: str
    attempted_llm: bool
    used_llm: bool
    rationale: str
    tasks: list[SubTask] = field(default_factory=list)
    fallback_reason: str | None = None
    raw_content: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the plan suggestion."""

        return {
            "prompt_name": self.prompt_name,
            "attempted_llm": self.attempted_llm,
            "used_llm": self.used_llm,
            "rationale": self.rationale,
            "tasks": [_model_to_dict(task) for task in self.tasks],
            "fallback_reason": self.fallback_reason,
            "raw_content": self.raw_content,
            "warnings": list(self.warnings),
        }


class PreparationBrain:
    """Optional reasoning gateway that keeps raw LLM use out of core modules."""

    def __init__(
        self,
        config: DataPreparationConfig | None = None,
        client: LLMClient | None = None,
        runtime_mode: RuntimeMode | None = None,
    ) -> None:
        self.config = config or DataPreparationConfig(
            runtime_mode=runtime_mode or "rule_only"
        )
        if runtime_mode is not None and runtime_mode != self.config.runtime_mode:
            raise BrainError("runtime_mode override must match the config runtime_mode")
        self.runtime_mode = self.config.runtime_mode
        self._client = client or (
            LLMClient.from_options(self.config.llm_options)
            if self.config.brain_enabled
            else None
        )

    def available(self) -> bool:
        """Return whether the optional brain is active."""

        return self.runtime_mode != "rule_only"

    def load_prompt(self, prompt_name: str) -> str:
        """Load a raw prompt template by filename or stem."""

        return load_prompt_template(prompt_name)

    def render_prompt(
        self,
        prompt_name: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a prompt template with lightweight placeholder replacement."""

        return render_prompt_template(prompt_name, variables, **kwargs)

    def invoke_prompt(
        self,
        prompt_name: str,
        *,
        variables: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        fallback_content: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> BrainCallResult:
        """Render a prompt and optionally route it through the configured client."""

        rendered_prompt = self.render_prompt(prompt_name, variables)
        if not self.available():
            return BrainCallResult(
                prompt_name=prompt_name,
                attempted_llm=False,
                used_llm=False,
                content=fallback_content,
                fallback_reason="runtime_mode=rule_only",
            )

        if self._client is None:
            return BrainCallResult(
                prompt_name=prompt_name,
                attempted_llm=False,
                used_llm=False,
                content=fallback_content,
                fallback_reason="no llm client configured",
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": rendered_prompt})

        try:
            response = self._client.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            failure = exc if isinstance(exc, LLMClientError) else LLMClientError(str(exc))
            return BrainCallResult(
                prompt_name=prompt_name,
                attempted_llm=True,
                used_llm=False,
                content=fallback_content,
                fallback_reason=str(failure),
            )

        return BrainCallResult(
            prompt_name=prompt_name,
            attempted_llm=True,
            used_llm=True,
            content=response.content,
            raw_content=response.content,
        )

    def build_tool_generation_prompt(self, **fields: Any) -> str:
        """Render the development-time tool generation template."""

        return self.render_prompt("tool_generation", fields)

    def suggest_processing_tasks(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
        rule_plan: PreparationPlan | None = None,
        registry: ToolRegistry | None = None,
    ) -> PlanSuggestionResult:
        """Ask the optional brain for conservative task suggestions."""

        if route_name != "processing":
            return PlanSuggestionResult(
                prompt_name="runtime_tool_planning",
                attempted_llm=False,
                used_llm=False,
                rationale="Brain planning is only relevant for the processing route.",
                fallback_reason="route_not_processing",
            )

        tool_registry = registry or ToolRegistry.build_default()
        prompt = self.build_runtime_tool_prompt(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            rule_plan=rule_plan,
            registry=tool_registry,
        )
        fallback_payload = json.dumps(
            {
                "rationale": (
                    "LLM assistance unavailable; keep the deterministic rule-based plan."
                ),
                "recommended_tasks": [],
            },
            ensure_ascii=True,
        )
        call_result = self.invoke_prompt(
            "runtime_tool_planning",
            variables={
                "runtime_mode": self.runtime_mode,
                "bundle_status": readiness_decision.bundle_status,
                "route_name": route_name,
                "known_input_refs": self._format_known_input_refs(bundle),
                "available_tools": self._format_available_tools(tool_registry),
                "rule_plan_tasks": self._format_rule_plan(rule_plan),
            },
            system_prompt=(
                "You are a careful planning assistant. Return strict JSON only, and "
                "only suggest already-registered tools."
            ),
            fallback_content=fallback_payload,
            temperature=0.0,
        )

        try:
            parsed = self._parse_json_payload(call_result.content)
        except BrainError as exc:
            return PlanSuggestionResult(
                prompt_name="runtime_tool_planning",
                attempted_llm=call_result.attempted_llm,
                used_llm=False,
                rationale="The deterministic rule-based plan was kept because the LLM response could not be parsed.",
                fallback_reason=str(exc),
                raw_content=call_result.raw_content or call_result.content,
            )

        raw_tasks = parsed.get("recommended_tasks", [])
        rationale_value = parsed.get("rationale")
        rationale = (
            str(rationale_value).strip()
            if rationale_value is not None and str(rationale_value).strip()
            else "No additional LLM task suggestions were provided."
        )

        warnings: list[str] = []
        suggested_tasks: list[SubTask] = []
        existing_signatures = self._task_signatures(rule_plan.tasks if rule_plan else [])
        known_input_refs = self._known_input_refs(bundle)

        if not isinstance(raw_tasks, list):
            warnings.append("recommended_tasks was not a list and was ignored")
            raw_tasks = []

        for index, raw_task in enumerate(raw_tasks, 1):
            try:
                task = self._build_suggested_task(
                    raw_task=raw_task,
                    index=index,
                    known_input_refs=known_input_refs,
                    registry=tool_registry,
                )
            except BrainError as exc:
                warnings.append(str(exc))
                continue

            signature = self._task_signature(task)
            if signature in existing_signatures:
                warnings.append(
                    f"duplicate suggested task ignored: {task.task_type} for {task.input_refs}"
                )
                continue

            existing_signatures.add(signature)
            suggested_tasks.append(task)

        return PlanSuggestionResult(
            prompt_name="runtime_tool_planning",
            attempted_llm=call_result.attempted_llm,
            used_llm=call_result.used_llm,
            rationale=rationale,
            tasks=suggested_tasks,
            fallback_reason=call_result.fallback_reason,
            raw_content=call_result.raw_content or call_result.content,
            warnings=warnings,
        )

    def build_runtime_tool_prompt(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
        rule_plan: PreparationPlan | None = None,
        registry: ToolRegistry | None = None,
    ) -> str:
        """Render the runtime tool-planning prompt used in hybrid modes."""

        tool_registry = registry or ToolRegistry.build_default()
        return self.render_prompt(
            "runtime_tool_planning",
            runtime_mode=self.runtime_mode,
            bundle_status=readiness_decision.bundle_status,
            route_name=route_name,
            known_input_refs=self._format_known_input_refs(bundle),
            available_tools=self._format_available_tools(tool_registry),
            rule_plan_tasks=self._format_rule_plan(rule_plan),
        )

    def _parse_json_payload(self, content: str) -> dict[str, Any]:
        candidate = content.strip()
        if not candidate:
            raise BrainError("LLM returned empty content")

        fenced_match = _JSON_BLOCK_PATTERN.search(candidate)
        if fenced_match:
            candidate = fenced_match.group(1).strip()

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise BrainError("LLM returned non-JSON planning content") from exc

        if not isinstance(parsed, dict):
            raise BrainError("LLM planning payload must be a JSON object")
        return parsed

    def _build_suggested_task(
        self,
        *,
        raw_task: Any,
        index: int,
        known_input_refs: set[str],
        registry: ToolRegistry,
    ) -> SubTask:
        if not isinstance(raw_task, dict):
            raise BrainError(f"suggested task #{index} was not an object")

        task_type = str(raw_task.get("task_type") or "").strip()
        tool_name = str(raw_task.get("tool_name") or task_type).strip()
        description = str(raw_task.get("description") or "").strip()
        input_refs_value = raw_task.get("input_refs", [])

        if not task_type:
            raise BrainError(f"suggested task #{index} is missing task_type")
        if not tool_name:
            raise BrainError(f"suggested task #{index} is missing tool_name")
        if not description:
            raise BrainError(f"suggested task #{index} is missing description")
        if not isinstance(input_refs_value, list) or not input_refs_value:
            raise BrainError(f"suggested task #{index} must include non-empty input_refs")

        input_refs = [str(item) for item in input_refs_value]
        invalid_refs = [item for item in input_refs if item not in known_input_refs]
        if invalid_refs:
            invalid_text = ", ".join(invalid_refs)
            raise BrainError(
                f"suggested task #{index} referenced unknown input refs: {invalid_text}"
            )

        task = SubTask(
            task_id=f"brain-{task_type}-{uuid4().hex[:6]}",
            task_type=task_type,
            description=description,
            input_refs=input_refs,
            tool_name=tool_name,
            status="pending",
        )
        registry.resolve(task)
        return task

    def _format_available_tools(self, registry: ToolRegistry) -> str:
        lines: list[str] = []
        for descriptor in registry.describe_tools():
            task_types = ", ".join(descriptor["supported_task_types"])
            lines.append(
                f"- {descriptor['name']}: task_types=[{task_types}] - {descriptor['summary']}"
            )
        return "\n".join(lines) if lines else "- none"

    def _format_known_input_refs(self, bundle: NormalizedInputBundle) -> str:
        refs = sorted(self._known_input_refs(bundle))
        if not refs:
            return "- none"
        return "\n".join(f"- {ref}" for ref in refs)

    def _format_rule_plan(self, rule_plan: PreparationPlan | None) -> str:
        if rule_plan is None or not rule_plan.tasks:
            return "- no rule-based tasks"
        lines = []
        for task in rule_plan.tasks:
            refs = ", ".join(task.input_refs)
            tool_name = task.tool_name or task.task_type
            lines.append(f"- {task.task_type} via {tool_name}: {refs}")
        return "\n".join(lines)

    def _known_input_refs(self, bundle: NormalizedInputBundle) -> set[str]:
        files: list[FileInspectionResult] = [
            *bundle.genotype_files,
            *bundle.environment_files,
            *bundle.metadata_files,
            *bundle.report_files,
            *bundle.unknown_files,
        ]
        return {str(file.file_path) for file in files}

    def _task_signatures(self, tasks: list[SubTask]) -> set[tuple[str, tuple[str, ...]]]:
        return {self._task_signature(task) for task in tasks}

    def _task_signature(self, task: SubTask) -> tuple[str, tuple[str, ...]]:
        return task.task_type, tuple(task.input_refs)


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return dict(model.model_dump())
    if hasattr(model, "dict"):
        return dict(model.dict())
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)
    raise BrainError(f"cannot serialize model of type {type(model)!r}")


__all__ = [
    "BrainCallResult",
    "PlanSuggestionResult",
    "PreparationBrain",
]
