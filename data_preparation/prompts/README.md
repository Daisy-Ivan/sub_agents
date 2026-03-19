# Prompts Directory

This directory stores prompt templates that can later be loaded by
`brain.py` and `llm_client.py`.

Current templates:
- `tool_generation.md`: development-time prompt for generating a new
  execution tool module, wiring it into the registry/planner path, and
  adding tests.
- `runtime_tool_planning.md`: runtime prompt for hybrid / llm-enhanced
  planning, where the model may suggest already-registered tools but may
  not invent new ones.

Current status:
- These prompts are available for developers and Codex now.
- Runtime prompt loading is now wired through `prompts/__init__.py`.
- The runtime brain can render these templates by filename or stem.
- `rule_only` mode still bypasses prompt invocation entirely.
