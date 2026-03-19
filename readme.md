## sub_agents 目录说明

本目录用于**集中存放育种智能体（Breeding Agent）体系中的所有子智能体（sub agent）**。每个子智能体应当是一个**相对独立、可插拔**的模块：有清晰的输入/输出契约、可测试、可逐步演进，并能被上层智能体按需编排调用。

## 当前包含的子智能体

- **`data_preparation/`**：数据准备子智能体  
  将原始育种 / G2P 相关输入检查、归类与就绪性评估后，按路由输出（必要时才进行处理），并组装为统一的结构化结果。

## 如何新增一个 sub agent（约定）

新增子智能体时，请在 `sub_agents/` 下创建一个同名目录，例如 `trait_modeling/`、`field_trial_planning/` 等，并遵循以下最小约定，便于维护与自动化集成：

- **对外入口清晰**：提供单一对外入口（如 `run(request)` 或等价 API），隐藏内部流水线细节。
- **文档齐全**：
  - `README.md`（英文可选）
  - `readmeCN.md`（中文说明，推荐）
  - `AGENTS.md`（该子智能体的开发/修改约束、架构要求、运行规则等）
- **边界清楚**：尽量只在自身目录内修改；如必须跨目录改动（例如包初始化/导入），应保持最小改动面。
- **可测试与可复现**：提供最小可运行示例与测试用例（建议 `examples/`、`tests/`）。

## 推荐目录结构（模板）

```text
sub_agents/
  <sub_agent_name>/
    AGENTS.md
    README.md
    readmeCN.md

    __init__.py
    agent.py            # 对外入口与编排
    schemas.py          # 主要输入/输出的类型与契约
    config.py           # 运行配置（含模式/开关）
    state.py            # 状态/追踪（如需要）
    exceptions.py

    capabilities/       # 规则、校验、报告组装等运行时能力模块
    tools/              # 可执行工具与注册（如需要）
    prompts/            # 模型提示模板（如需要）
    docs/               # 项目文档集合（如需要）
    examples/           # 可运行演示
    tests/              # 单测/集成测试
```

## 扩展说明

后续新的 sub agent 会持续添加到该目录。请在新增时同步更新本文件的“当前包含的子智能体”列表，确保目录总览始终准确。
