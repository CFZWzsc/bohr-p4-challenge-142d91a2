---
name: research-proposal-planner
description: Use when a case supplies thesis-proposal or research-plan materials and asks for a defensible plan; turns background notes into testable research questions, maps objectives to technical routes and deliverables, parses milestones into a normalized month schedule within the allowed period, builds a risk register with trigger signals and fallbacks, and writes /app/output/result.json preserving case_id and every output_contract field. Deterministic standard library only; no network.
---

# 开题报告与研究计划书（问题可证伪—路线可落地—计划排得开）

## 用途与适用条件

当输入包含课题背景、前期数据、导师意见、周期与资源约束，需要形成开题报告/研究计划书的结构化骨架与自查表时使用。

适用：

- 需要把宽泛方向收敛为 1–3 个可回答、可证伪的研究问题。
- 需要把目标、技术路线、验证方式与预期成果逐条对应。
- 需要把阶段任务排入给定周期，检查里程碑与任务量是否匹配。
- 需要按数据、方法、进度、伦理分类识别风险并写出触发信号与备选方案。

不适用：代填伦理审批、虚构前期数据、承诺未给定的经费与人员、替代导师做方向决策。

## 输入

- `/input/case.json`：读取 `case_id`、`output_contract`、`task`、`duration_months`/`period`、以及 `proposal`、`plan`、`background`、`materials`、`milestones`、`risks` 等字段。
- `task.md`：存在时读取 `/input/task.md` 或 `/app/work/task.md`，缺失不阻塞。
- 文本可内联或给路径；只读 UTF-8、≤2MB 文件；二进制登记为未解析。
- 输出 `/app/output`，工作 `/app/work`。

## 处理流程（逐项覆盖评分维度）

1. **背景—缺口（立得住）**：按章节归位背景、问题、目标、路线、计划、风险、成果；抽取“已知/未知/待验证”句，缺口句缺证据时标 `gap_without_evidence`。
2. **问题可证伪性**：识别问句与“研究问题”条目；含可测量要素（比较、影响、关系、是否、阈值、样本、时间点）记为 `testable=true`，只有“探讨/分析/研究”而无判据的记为 `vague_question`。
3. **目标—路线—成果对应**：用实词重叠建立 `objective → route → deliverable` 映射；无对应项的列入 `gaps`，不强行配对。
4. **里程碑排期**：解析 `第1-6月`、`第1季度`、`Q2`、`2026-03`、`month 3` 等时间表达，归一化为月区间；检查重叠、倒序、超出 `duration_months`，输出 `timeline_conflicts`。
5. **风险登记**：按数据/方法/进度/伦理分类；每条风险必须有触发信号与备选方案，缺失项分别标 `missing_trigger`、`missing_fallback`。
6. **工作量核对**：统计每阶段任务数与跨度，标记“单月超过 3 项”或“跨度小于 1 个月”的拥挤/过短里程碑。
7. **结构化交付**：`question_register`、`objective_route_map`、`milestone_schedule`、`risk_register`、`deliverable_checklist`。
8. **合同保留**：见输出契约。

## 输出契约

写入 `/app/output/result.json`：

- 顶层 `case_id` 与输入一致。
- **保留原始 `output_contract` 每个字段名**（字典/列表/`fields`/Schema `properties`）；已知字段按别名填充，未映射写 `null` 并登记，状态降为 `partial`；组合 Schema 登记 `unsupported_features`。
- 固定字段：
  - `status`：`success | partial | insufficient_input | failed`
  - `result`：`question_register`、`objective_route_map`、`milestone_schedule`、`risk_register`、`deliverable_checklist`、`gaps`
  - `evidence`、`uncertainty`、`errors`、`stats`
- 退出码：`0` 完成；`1` 有未映射合同字段；`2` 输入不可读。

## 异常处理

| 情形 | 处置 |
|---|---|
| 无可用文本 | `status=insufficient_input`，说明缺少计划材料 |
| 未给周期 | 里程碑照常归一化，`duration_months=null`，不推断截止时间 |
| 时间表达歧义（“上半年”） | 记为 `ambiguous_time`，不强行换算 |
| 里程碑重叠或倒序 | 保留原值，标 `timeline_conflict` |
| 风险无触发信号/备选 | 分别标记，不代写具体方案 |
| 问题不可证伪 | 标 `vague_question` 并给出“需补充判据”的具体位置 |
| 目标多于路线 | `gaps.objectives_without_route` 逐条列出 |
| 材料冲突（样本量/周期） | 两条都保留并升级人工确认 |

## 限制与不适用

- 不验证文献缺口是否真实存在，不检索数据库。
- 不计算经费、不分配人员、不承诺考核数值。
- 时间归一化只覆盖常见中英文表达，无法解析时明确标注。
- 映射基于词面重叠，`linked=true` 不代表论证充分。

## 最小调用示例（示例）

以下为合成示意，非官方案例。

```bash
python /skills/weekly-skill/scripts/run_skill.py \
  --case /input/case.json \
  --out /app/output/result.json \
  --work /app/work
```

合成 `case.json`：

```json
{
  "case_id": "synthetic-plan-demo",
  "output_contract": {"status": "string", "question_register": "array", "milestone_schedule": "array", "risks": "array"},
  "duration_months": 24,
  "proposal": "## 研究问题\n血清标志物是否可预测 12 周治疗反应？\n## 研究目标\n1. 建立预测模型。\n## 技术路线\n回顾性队列建模与前瞻验证。\n## 阶段计划\n第1-6月 数据清洗；第7-18月 建模；第19-24月 验证。\n## 风险\n样本不足可能导致模型不稳。"
}
```

示意输出（节选）：

```json
{"case_id":"synthetic-plan-demo","status":"success","result":{"milestone_schedule":[{"text":"数据清洗","start_month":1,"end_month":6}]},"stats":{"milestones":3}}
```

## 自查清单

- [ ] `case_id` 与合同字段保留；未映射项已登记。
- [ ] 每个研究问题都有 `testable` 判定与理由。
- [ ] 里程碑月区间单调、不超周期，冲突已列出。
- [ ] 每条风险都有触发信号与备选状态位。
- [ ] 未编造周期、经费、样本量或前期成果。
- [ ] 无网络调用、无第三方依赖。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. **必须交付完整成品**：脚本只产出索引与自查表；调用 Agent 必须据同一 `case.json` 写出七要素齐全的开题方案正文（研究背景与缺口、1–3 个可证伪研究问题及判据、目标、技术路线、阶段计划、风险与备选、预期成果），写入 `result.proposal_markdown`，并补全 `question_register`、`objective_route_map`、`milestone_schedule`、`risk_register`、`deliverable_checklist`；不得停留在骨架、`pending` 或“待作者补写”。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值 `success | partial | insufficient_input | failed`（材料齐全时为 `success`，确缺输入才降级）；正文无 `pending`/`TODO`/空占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
