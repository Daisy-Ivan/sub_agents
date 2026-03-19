# Tool Generation Prompt

Use this template when you want a model to generate a new low-level tool
for `agents/core/sub_agents/data_preparation/`.

This prompt is for development-time code generation. It is not yet
auto-loaded by runtime code.

## Suggested Inputs

Fill in these fields before sending the prompt to a model:

- `task_type`: the planner-facing task type to support
- `tool_name`: the executor-facing tool name to register
- `module_name`: the new Python module name under `tools/`
- `class_name`: the concrete tool class name
- `goal`: what this tool should accomplish
- `input_contract`: expected task inputs and file types
- `output_contract`: expected output files and metadata
- `failure_conditions`: when the tool should raise an error
- `reference_tool`: the closest existing tool to imitate, if any

## Prompt Template

```text
You are implementing a new low-level execution tool inside:
agents/core/sub_agents/data_preparation/

Read and follow these files first:
1. AGENTS.md
2. tools/tool_template.py
3. tools/base.py
4. tools/registry.py
5. planner.py
6. the most relevant existing tool module
7. the most relevant executor/planner tests

Task:
- Add support for `task_type = "<task_type>"`
- Register a concrete tool named `"<tool_name>"`
- Create the module `tools/<module_name>.py`
- Implement class `<class_name>`

Goal:
<goal>

Input contract:
<input_contract>

Output contract:
<output_contract>

Failure conditions:
<failure_conditions>

Closest reference tool:
<reference_tool>

Requirements:
- Follow the existing deterministic architecture:
  planner -> subtask(task_type/tool_name) -> registry -> executor -> tool
- Do not rely on model-side auto-discovery of tools.
- Start from `tools/tool_template.py`, but replace placeholder logic with
  real logic.
- Subclass `BaseTool`.
- Set `name` and `supported_task_types`.
- Implement `run(task, context) -> ToolResult`.
- Validate `task.input_refs` and raise `ExecutionError` on invalid or
  missing required inputs.
- Write generated files into `context.output_dir`.
- Return structured `ToolResult` metadata that is useful for downstream
  reporting.
- Prefer Python stdlib and the project's existing helpers unless a new
  dependency is clearly necessary.
- Keep the tool self-contained and testable.
- Do not hardcode absolute paths.
- Preserve partial-success behavior at the executor level.

Required code changes:
1. Add `tools/<module_name>.py`.
2. Import and register `<class_name>` in `tools/registry.py`.
3. Update `planner.py` so relevant cases emit matching `task_type` and/or
   `tool_name`.
4. Add focused tests for:
   - the tool module itself when reasonable
   - registry resolution
   - executor path coverage
5. Update docs only if the new tool changes supported behavior in a
   user-visible way.

Implementation notes:
- If the tool normalizes tables, keep header handling explicit.
- If the tool writes reports, make the output human-readable.
- If the tool merges sources, keep provenance in metadata when possible.
- If external CLIs are needed in the future, wrap them behind the tool
  boundary instead of leaking command logic into planner/executor.

Output format:
1. Short summary of what was added
2. Files changed
3. Key assumptions
4. Validation commands run
```

## Notes

- This template is meant to help a model generate code, not to make the
  runtime automatically discover tools.
- A tool is only callable after it is registered in
  `tools/registry.py` and emitted by `planner.py`.
