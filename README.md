# stockpick-skills — 多风格 AI 选股技能框架

用 **AI Skill（Markdown）承载选股逻辑**的可扩展框架：每种投资风格（巴菲特、费雪、格雷厄姆、林奇……）是一个独立的、可插拔的技能包，由统一的编排流水线并行调用，输出结构一致的筛选结论。

> ⚠️ 本项目仅供学习研究，不构成投资建议。AI 输出存在幻觉风险，所有关键数据必须回溯到原始财报核验。

## 设计哲学（为什么不是代码承载逻辑）

| 传统量化选股 | 本框架 |
|---|---|
| 选股逻辑写死在代码里，改一条标准 = 改代码 + 回归测试 | 逻辑写在 SKILL.md/references 里，改标准 = 改一段 Markdown |
| 只能处理可量化指标 | 能处理"护城河类型""管理层诚信"等定性判断 |
| 参数调整靠重新编译部署 | 阈值外置 YAML，逐风格可调、可版本化 |
| 黑箱打分 | 每条判据输出 pass/fail + 依据 + 数据源，可审计 |

但**计算不交给 LLM**：PE/ROE/CAGR/PEG 等所有数值由 `scripts/metrics.py`（精确 Decimal）计算，AI 只做判断。这是借鉴 ai-berkshire 最重要的工程教训：LLM 心算金融数据不可靠。

## 架构

```
                    ┌─────────────────────────────────────┐
                    │  skills/orchestrator  编排层         │
                    │  股票池 → 数据装配 → 公共红线 →       │
                    │  并行分发风格技能 → 汇总对比矩阵      │
                    └──────────────┬──────────────────────┘
                                   │ 按 docs/style-skill-contract.md 契约分发/收集
          ┌────────────┬───────────┼───────────┬────────────┐
          ▼            ▼           ▼           ▼            ▼
   buffett-value  fisher-growth  graham-    lynch-garp   (新风格…)
     巴菲特质量    费雪成长股     deep-value  林奇GARP     目录即插件
     价值                      格雷厄姆
   SKILL.md +   SKILL.md +    SKILL.md     SKILL.md
   references   references    + 内置判据    + 内置判据
          │            │           │           │
          └────────────┴─────┬─────┴───────────┘
                             ▼
                  数据层：scripts/metrics.py 精确计算指标
                        config/profiles/*.yaml 阈值外置
                        docs/data-contract.md 数据包字段
```

三层解耦：
1. **编排层**（orchestrator）：不知道任何风格的具体逻辑，只负责流水线和汇总。
2. **风格技能层**：每种风格一个目录，实现统一契约。新增风格只需复制骨架 + 写判据，见 `docs/authoring-guide.md`。
3. **数据与计算层**：数据获取适配器（可插拔：finance-data skill / akshare / tushare / 手工录入）+ 指标精确计算。

## 目录结构

```
stockpick-skills/
├── skills/
│   ├── orchestrator/SKILL.md          # 选股流水线编排器
│   ├── shared/common-redflags.md      # 全风格共用一票否决红线
│   ├── buffett-value/                 # 巴菲特质量价值
│   │   ├── SKILL.md
│   │   └── references/ (moats.md, management-valuation.md)
│   ├── fisher-growth/                 # 费雪成长股
│   │   ├── SKILL.md
│   │   └── references/ (15-point-checklist.md, scuttlebutt.md)
│   ├── graham-deep-value/SKILL.md     # 格雷厄姆深度价值/防御型投资者
│   └── lynch-garp/SKILL.md            # 彼得·林奇 GARP
├── scripts/metrics.py                 # Decimal 精确指标计算（唯一"代码"，且不含风格逻辑）
├── config/
│   ├── profiles/*.yaml                # 每风格阈值参数（可调参、可 A/B、可版本化）
│   └── universes/                     # 股票池定义
├── docs/
│   ├── architecture.md                # 架构与演化路线
│   ├── style-skill-contract.md        # 风格技能统一输入输出契约
│   ├── data-contract.md               # 数据包字段规范 + 数据源适配
│   └── authoring-guide.md             # 新增一种风格的操作手册
├── evals/                             # 回归评测：固定输入→核对判据覆盖，改 prompt 不跑 eval 不许合并
│   ├── README.md
│   └── fixtures/example-stock.json
└── .gitignore
```

## 快速开始

1. **单风格单股判定**（把技能目录交给任意支持 Agent Skills 的客户端：Claude Code 放 `.claude/skills/`，Codex 放 `~/.codex/skills/`，千问工作助理等按其技能目录规范）：
   ```
   使用 buffett-value 分析 贵州茅台
   ```
2. **多风格选股**：
   ```
   使用 orchestrator 对 config/universes/sample_hs300.txt 股票池执行全部 4 种风格筛选，输出对比矩阵
   ```
   （示例池仅 8 只；换成自己的池子即可。）
3. **先算指标**（AI 判断前必须跑，禁止心算）：
   ```bash
   python scripts/metrics.py --data path/to/stock_data.json
   ```

## 演化路线（Roadmap）

- **Phase 1（当前）**：技能逻辑 + 手工/半自动数据包，单股与中小股票池筛选。
- **Phase 2**：数据适配器自动化（akshare/tushare/财经数据 API → data-contract 格式），全市场批量流水线。
- **Phase 3**：回测 harness —— 把风格契约输出（pass/fail/score）作为信号，对上前向收益做命中率统计，用数据反向修订 references 判据（"skill 版本演化"从此有据可依）。
- **Phase 4**：风格委员会 —— 多风格并行 + 分歧仲裁（借鉴 ai-hedge-fund 的裁判层与 ai-berkshire 的视角对抗），输出"几派都同意 / 几派打架"的决策矩阵。
- **持续**：每次修改 SKILL.md 或阈值必须跑 `evals/`；参数与判据分仓管理，判据进化不破坏契约。

## 借鉴来源（MIT License 项目，遵守出处）

- xbtlin/ai-berkshire：多 Agent 对抗、Decimal 精确计算、三值输出（通过/不通过/灰色）纪律
- agi-now/buffett-skills：SKILL.md + references 渐进式披露结构、eval 通过率基准方法
- ancs21/ai-sub-invest：按投资哲学切分 skill 的做法（含 phil-fisher）
- virattt/ai-hedge-fund：多风格 Agent + 汇总裁判的分层思想（本框架把其"代码"换成"Skill"）
- andMYhacks/graham：格雷厄姆防御型 7 条硬指标的量化口径

## 免责声明

本框架输出为 AI 基于公开信息生成的研究性意见，可能存在数据错误或推理偏差，不构成任何投资建议。投资有风险，决策需独立尽调（DYOR）。
