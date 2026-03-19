# 数据准备子智能体

## 1. 本模块是什么

`data_preparation` 是一个子智能体，用于将原始育种 / G2P 相关输入转换为可校验的结构化结果。

它不会对每一个文件都盲目转换。预期行为是：

1. 检查原始输入
2. 将其分类为：基因型 / 环境 / 元数据 / 报告 / 未知
3. 判断它们是否已经可用
4. 将它们路由到正确的处理路径
5. 只有在处理确实有必要时才规划并执行工具
6. 校验输出
7. 组装出一个最终的 `PreparationResult`

该包支持三种运行模式：

- `rule_only`: 仅使用确定性规则
- `hybrid`: 基于规则的流水线，并可选用 LLM 协助
- `llm_enhanced`: 预留用于更深度的模型参与

## 2. 当前状态


对外提供的单入口运行时方法现已可用：

- `DataPreparationSubAgent.run(request)`

该方法会串联完整的受控链路：

- `inspect_files()`
- `build_bundle()`
- `assess_readiness()`
- `route()`
- `build_processing_plan()`
- `execute_processing_plan()`
- `refine_outputs()`
- `validate_route_outputs()`
- `build_route_report()`
- `assemble_result()`

部分内部演示仍保留手动逐阶段的路径（当需要仅用于演示的 `plan_mutator` hooks 时），但正常调用方应使用 `run()`。

## 3. 端到端工作流

工作流是固定且受控的：

```text
检查 -> 构建包 -> 就绪性 -> 路由 -> （按需计划/执行） -> 精炼 -> 校验 -> 组装结果
```

当前的路由映射如下：

| Bundle 状态 | 路由 |
| --- | --- |
| `analysis_ready` | `direct_output` |
| `partially_ready` | `direct_output` |
| `transformable` | `processing` |
| `view_only` | `report_only` |
| `unsupported` | `unsupported` |

只有在 `processing` 这条路由上才会发生处理。

## 4. 目录结构

当前包的布局如下：

```text
data_preparation/
  AGENTS.md

  __init__.py
  agent.py
  config.py
  schemas.py
  state.py
  memory.py
  exceptions.py

  inspector.py
  bundle_builder.py
  readiness_assessor.py
  router.py
  planner.py
  executor.py
  result_assembler.py
  brain.py
  llm_client.py

  adapters/
  capabilities/
  docs/
    project/
      README.md
      readmeCN.md
      SPEC.md
      TASKS.md
      TEST_CONTRACT.md
      EXPECTED_CASES.md
      PROMPTS.md
  prompts/
  sample_inputs/
  examples/
  tests/
  tools/
```

关键子目录：

- `capabilities/`：运行时业务逻辑辅助，包括检查规则、精炼、校验，以及路由报告组装
- `docs/project/`：打包后的项目文档集合，包含规格、任务阶段、提示词说明以及维护说明
- `tools/`：底层可执行处理工具及其注册表
- `prompts/`：运行时模型提示模板，用于规划和工具生成
- `examples/`：可运行的演示
- `tests/`：阶段级与演示级测试

## 5. 核心文件职责

### 编排（Orchestration）

- `agent.py`：主编排器；负责阶段切换和内存更新
- `memory.py`：存储请求、中间工件、元数据以及追踪信息
- `state.py`：工作流状态机枚举
- `config.py`：运行模式、输出目录、LLM 选项，以及策略覆盖
- `schemas.py`：请求、计划、校验与最终结果的类型化合约
- `exceptions.py`：包级错误类型

### 阶段逻辑（Phase Logic）

- `inspector.py`：封装文件检查能力
- `bundle_builder.py`：将检查结果汇总为标准化的包（bundle）
- `readiness_assessor.py`：计算 `analysis_ready / partially_ready / transformable / view_only / unsupported`
- `router.py`：将就绪性结果转换为路由
- `planner.py`：为 `processing` 路由构建确定性的处理任务
- `executor.py`：按顺序执行已注册的工具，并记录部分成功情况
- `result_assembler.py`：把所有中间工件组装为最终的 `PreparationResult`

### 运行时能力（Runtime Capabilities）

- `capabilities/file_inspection.py`：基于规则的文件类型 / 类别 / 可用性检测
- `capabilities/data_refine.py`：结构化输出的可选后处理精炼
- `capabilities/data_checker.py`：基于路由的验证
- `capabilities/report_builder.py`：路由摘要与工件报告组装

### LLM 集成

- `brain.py`：可选的模型辅助规划层
- `llm_client.py`：OpenAI 兼容的 HTTP 客户端
- `prompts/runtime_tool_planning.md`：运行时提示，用于仅建议已注册工具任务
- `prompts/tool_generation.md`：开发时提示，用于生成新的工具实现

### 工具（Tools）

- `tools/base.py`：`BaseTool` 合约
- `tools/registry.py`：工具注册与查找
- `tools/plink_conversion.py`：类 PLINK 的基因型归一化
- `tools/table_normalization.py`：CSV/TSV/表格归一化工具
- `tools/report_generation.py`：样本/时间检查与文本报告
- `tools/source_merge.py`：源清单生成（manifest generation）
- `tools/tool_template.py`：新增工具的模板
- `tools/task_tools.py`：兼容性重导出层

## 6. 数据在包内如何流动

当前主要对外公开调用链是：

```text
PreparationRequest -> run() -> PreparationResult
```

在内部，`run()` 展开为：

```text
PreparationRequest
  -> inspect_files()
  -> build_bundle()
  -> assess_readiness()
  -> route()
  -> build_processing_plan()     # 仅对 processing 路由有意义
  -> execute_processing_plan()   # 仅对 processing 路由有意义
  -> refine_outputs()
  -> validate_route_outputs()
  -> build_route_report()
  -> assemble_result()
```

执行侧是确定性的：

```text
planner.py -> SubTask(task_type, tool_name)
executor.py -> tools/registry.py
registry.py -> concrete BaseTool subclass
tool.run(task, context) -> ToolResult
```

这对维护非常重要：

- 把文件扔进 `tools/` 并不够
- 该工具必须被注册
- planner 必须知道何时发出与之匹配的任务

## 7. 演示（Demos）

### 7.1 简单演示

通过对外公开的 `run()` 入口，运行一个单一“处理型”示例：

```bash
cd /home/dataset-assist-0/swb/swb_bak
python agents/core/sub_agents/data_preparation/examples/demo_run.py
```

### 7.2 完整场景演示

运行一个覆盖多场景的综合演示；这是最好的回归冒烟测试：

```bash
cd /home/dataset-assist-0/swb/swb_bak
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py
```

支持的选项：

```bash
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --json
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --scenario processing_transformable_success
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --scenario report_only_assets --scenario unsupported_missing_and_binary
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --output-root /tmp/data_prep_demo
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --list-scenarios
```

`full_scenario_demo.py` 默认覆盖的场景：

- `analysis_ready_direct_output`
- `partially_ready_with_report`
- `content_based_detection_unknown_suffix`
- `processing_transformable_success`
- `processing_partial_success`
- `processing_validation_failed`
- `report_only_assets`
- `unsupported_missing_and_binary`

给维护者的备注：

- 完整演示是回归测试平台，而不仅仅是“快乐路径脚本”
- 部分场景会刻意使用仅用于演示的 `plan_mutator` hooks，以保证 `success`、`partial_success`、`validation_failed` 分支稳定且便于测试

### 7.3 可选 LLM 演示

完整场景演示也可以包含混合（hybrid）规划路径：

```bash
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --include-llm
```

还有一个专门的模型调试演示：

```bash
python agents/core/sub_agents/data_preparation/examples/llm_debug_demo.py
```

该调试演示会按下面两件事执行：

- 直接使用本地的 OpenAI 兼容端点进行一次 smoke test（带测试提示）
- 在 `hybrid` 模式下运行 `DataPreparationSubAgent.run()`，并打印：选择的路由、计划、brain 使用标志、校验汇总，以及最终状态

## 8. 本地模型配置

当前本地模型集成假设使用的是一个 OpenAI 兼容端点。默认调试目标为：

- `base_url`: `http://127.0.0.1:8000/v1`
- `model`: `Qwen/Qwen3.5-35B-A3B-FP8`

典型配置示例：

```python
from agents.core.sub_agents.data_preparation import DataPreparationConfig

config = DataPreparationConfig(
    runtime_mode="hybrid",
    llm_options={
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "Qwen/Qwen3.5-35B-A3B-FP8",
        "timeout_seconds": 30,
    },
)
```

模型使用范围会被刻意限制：

- 规则仍然负责生成基础计划
- brain 可以建议额外任务
- 运行时工具执行仍然通过 planner + registry 完成
- 模型不会直接从 `tools/` 执行任意代码

## 9. 编程式用法（Programmatic Usage）

当前推荐的编程式入口已经是 `run()`：

```python
from agents.core.sub_agents.data_preparation import (
    DataPreparationSubAgent,
    PreparationRequest,
    RawInputFile,
)

request = PreparationRequest(
    input_files=[
        RawInputFile(file_path="path/to/genotypes.vcf"),
        RawInputFile(file_path="path/to/weather.csv"),
    ],
    task_goal="Prepare trial inputs",
)

agent = DataPreparationSubAgent()
result = agent.run(request)
```

如果你需要调试某一个具体阶段，单独的 phase 方法仍然保留并可直接调用。

## 10. 测试（Tests）

运行完整的数据准备测试套件：

```bash
cd /home/dataset-assist-0/swb/swb_bak
python -m unittest discover -s agents/core/sub_agents/data_preparation/tests -t . -v
```

仅运行综合演示的冒烟测试：

```bash
python -m unittest agents.core.sub_agents.data_preparation.tests.test_full_scenario_demo -v
```

有用的额外校验：

```bash
python -m compileall agents/core/sub_agents/data_preparation
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py
```

### 10.1 快速验收

如果你只是想快速确认当前工作区里的代码还能正常工作，建议按下面顺序执行：

```bash
cd /home/dataset-assist-0/swb/swb_bak
python -m unittest discover -s agents/core/sub_agents/data_preparation/tests -t . -v
python agents/core/sub_agents/data_preparation/examples/demo_run.py
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --json
python agents/core/sub_agents/data_preparation/examples/llm_debug_demo.py
```

你应该看到的现象：

- unittest 套件完整通过；最近一次本地验收是 `57` 个测试通过
- `demo_run.py` 能正常结束，并打印 `memory_state: completed`；当前这组 toy 数据会落到 `final_status: validation_failed`，这是预期现象，不是脚本崩溃
- `full_scenario_demo.py --json` 会返回一组混合结果，覆盖 `success`、`partial_success`、`validation_failed`、`report_only`、`unsupported`，且不应出现 crash
- `llm_debug_demo.py` 会打印本地模型名 `Qwen/Qwen3.5-35B-A3B-FP8`，并显示 `brain_attempted_llm: True`、`brain_used_llm: True`，最终 hybrid run 会结束在 `hybrid_memory_state: completed`

## 11. 维护指南（Maintenance Guide）

### 11.1 如果你需要添加一个新的检测规则

主要文件：

- `capabilities/file_inspection.py`
- `inspector.py`
- `tests/test_phase3_inspector.py` 下的测试

建议流程：

1. 在 `file_inspection.py` 中添加或调整启发式（heuristic）
2. 保持输出字段以 `modality`、`detected_category`、`detected_format`、`usability` 为维度
3. 添加一个代表性的测试用例
4. 验证下游的就绪性 / 路由行为仍符合预期

### 11.2 如果你需要改变就绪性或路由

主要文件：

- `readiness_assessor.py`
- `router.py`
- 测试：`test_phase5_readiness.py`、`test_phase6_router.py`

当策略变化时使用，例如：

- 某种文件类型应该变为 `transformable`，而不是 `analysis_ready`
- 一个之前直接输出（direct-output）的 bundle 现在应该走 processing

### 11.3 如果你需要添加一个新的工具

主要文件：

- `tools/tool_template.py`
- `tools/<your_tool>.py`
- `tools/registry.py`
- `planner.py`
- tests

必须的步骤：

1. 复制 `tools/tool_template.py`
2. 实现一个新的 `BaseTool` 子类
3. 在 `tools/registry.py` 中注册它
4. 让 `planner.py` 在发出匹配的 `task_type` / `tool_name` 时考虑到它
5. 为该工具以及端到端执行新增测试

不要假设模型会自动发现该工具。运行时路径是基于“注册”的，而不是基于“扫描目录”。

### 11.4 如果你需要修改校验逻辑（Validation）

主要文件：

- `capabilities/data_checker.py`
- `capabilities/report_builder.py`
- `result_assembler.py`

更新发生在这里：

- 必需的列（required columns）
- 时序/空间对齐检查（temporal/spatial alignment checks）
- 样本一致性行为（sample consistency behavior）
- 汇总 / 警告合并（summary / warning merging）

### 11.5 如果你需要修改模型行为（Model Behavior）

主要文件：

- `brain.py`
- `llm_client.py`
- `prompts/runtime_tool_planning.md`
- `prompts/tool_generation.md`
- 测试：`test_phase11_brain_llm.py`

推荐规则：

- 让基于规则的规划作为安全兜底（safe fallback）
- 仅允许模型建议映射到已注册工具的任务
- 永远不要让运行时执行绕过 `registry.py`

### 11.6 如果你需要新增演示（Demo）或回归用例（Regression Case）

主要文件：

- `examples/full_scenario_demo.py`
- `tests/test_full_scenario_demo.py`

这是添加新代表性场景的最佳位置：因为它也同时承担 smoke 回归测试平台的作用。

## 12. 提示文件（Prompt Files）

当前的提示文件：

- `prompts/runtime_tool_planning.md`：运行时规划提示，用于建议“已注册”的工具
- `prompts/tool_generation.md`：开发时提示，用于生成新的工具代码

当模型需要帮助规划时使用运行时提示。

当模型需要帮助创建新的工具模块，以及对应的 registry / planner / test 变更时，使用工具生成提示。

## 13. 已知限制（Known Limitations）

- `llm_enhanced` 在结构上已支持，但不像 `rule_only` 与 `hybrid` 那样被深入测试/覆盖
- 一些工具实现仍然是轻量的 Python 变换，而不是对领域原生命令行工具的封装
- 一些 demo 场景会故意保留仅用于演示的 `plan_mutator` hooks，以便稳定覆盖 `partial_success` 和 `validation_failed` 分支

## 14. 推荐的下一步改进（Recommended Next Improvements）

- 在不需要 `plan_mutator` 的场景下，继续把 demo 内的手动编排迁移到 `run()`
- 按需要添加更多领域原生的基因型/环境工具
- 在样本输入夹具上扩展更多不依赖合成测试内容（synthetic test content）的覆盖
- 添加 CI hooks：自动运行 `test_full_scenario_demo.py` 以及完整 unittest 测试套件
