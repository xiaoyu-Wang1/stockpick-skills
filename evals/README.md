# evals/ — 技能回归评测

## 为什么需要它

选股逻辑写成 Markdown 之后，**没有单元测试就等于没有质量保障**。改一句话、调一个阈值，都可能让某个判据悄悄失效（例如护城河从"必答方向"退化成"顺带提一句"），而这种退化在人读报告时很难发现。

本目录的机制：**固定输入 + 判据覆盖清单**。每次修改 SKILL.md / references / profiles 必须跑一遍并记录结果，不通过不合并。

## 目录

```
evals/
├── README.md
├── fixtures/
│   └── example-stock.json          # 一个完整、可复算的数据包（含刻意设置的判据陷阱）
└── rubric/                          # 每个 fixture 对应的期望清单（人工维护）
    └── example-stock.buffett.json  # 可选：把期望硬指标结论固化，便于比对
```

## 怎么跑

1. 准备环境：让客户端能发现技能（Claude Code 复制到 `.claude/skills/`，Codex 复制到 `~/.codex/skills/`，千问工作助理按其技能目录）。
2. 计算指标：
   ```bash
   python scripts/metrics.py --data evals/fixtures/example-stock.json --years 10
   ```
3. 逐风格执行：把**数据包 JSON + 第 2 步产出的指标 JSON 一起**喂给技能（编排层上下文格式见 `docs/style-skill-contract.md` 第 1 节），要求按契约输出 JSON。**不要让技能自己去"分析那个 json 文件"**——它会绕过精确计算，正好踩中 E3 的失败形态。示例指令：
   ```
   使用 buffett-value 评估：ticker=000000.SZ，computed_metrics=<第2步输出>，
   data_pack=evals/fixtures/example-stock.json 内容，profile=config/profiles/buffett-value.yaml
   使用 fisher-growth 评估：同上
   使用 graham-deep-value 评估：同上
   使用 lynch-garp 评估：同上
   ```
4. 按下方 checklist 人工/半自动核对。

## 每次改动必查的 8 项（PASS/FAIL 记录）

| # | 检查项 | 失败长什么样 |
|---|---|---|
| E1 | 输出是合法 JSON 且契约字段齐全 | 缺 `confidence_grade`；把 `hard_screen` 写成散文 |
| E2 | `verdict` 是三值之一，没有和稀泥 | 出现"需权衡""建议关注"当结论 |
| E3 | 所有数值等于 `computed_metrics`，AI 未重算 | 报告里 PE 与脚本输出不一致 |
| E4 | 硬指标逐条有 `pass` + `actual` + `evidence` | 只给总分不给逐条 |
| E5 | 命中红线时 `veto_hits` 非空且 `verdict=fail` | 发现造假记录却仍给 70 分 |
| E6 | 数据缺失进入 `data_gaps` 且降级 confidence | 用记忆填补 10 年前的 ROE |
| E7 | fixture 中刻意设置的陷阱被抓到（见下） | 陷阱被忽略 = 判据失效 |
| E8 | 同输入重复跑，结论方向稳定（格式可微调） | 一次 pass 一次 fail 且理由不同 |

### fixture 内置陷阱（务必被检出）
`evals/fixtures/example-stock.json` 故意包含：
- **一年净利为负**（考验 g3 盈利稳定 / 巴菲特派 roe_10y 逐年校验）
- **应收账款增速远超营收**（考验费雪要点 4 / 林奇 ly6 红旗）
- **PE × PB 明显高于格雷厄姆上限**（考验 g6/g7 必须 fail，且不得因"好公司"放宽）
- **无 20 年连续分红记录**（考验 g4 的降级判定与 `data_gaps` 声明）
- **市值与股价×股本故意留出可校验的一致性**（考验 `market_cap_check`）

## 记分与记录格式

每次运行在 `evals/results/`（gitignore，本地留存）追加一条：
```json
{ "date": "2026-11-07", "skill": "buffett-value", "version": "1.0.0",
  "commit_or_file_hash": "…", "checks": {"E1":"pass","E3":"fail", "…":""},
  "notes": "E3: 报告自行重算了ROE为16.1%与脚本16.1%一致但PB口径不同" }
```
**通过率下降的改动不许合并**，除非有记录说明为何某项检查标准本身变了。

## 进阶（Phase 3）

把 `verdict` 与 `score` 作为信号接入前向收益统计（如 12 个月超额收益），用命中率反向校准判据与阈值。此时 `profile_overrides` 就是天然的 A/B 实验开关。
