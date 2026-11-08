# 风格技能契约（Style Skill Contract）v1.0

所有风格技能（`skills/<style-name>/`）必须实现本契约。契约稳定的接口 + 可自由演化的内部逻辑，是本框架工程化的核心：**编排层只依赖本契约，风格技能怎么改都不影响主干。**

## 1. 输入

风格技能接收一个"标的评估上下文"，由编排层装配：

```json
{
  "ticker": "600519.SH",
  "name": "贵州茅台",
  "as_of": "2026-11-07",
  "data_pack": { "...": "见 docs/data-contract.md，含行情/多年财务/分红/股本" },
  "computed_metrics": { "...": "scripts/metrics.py 的输出，禁止 AI 自行心算数值" },
  "qualitative_leads": ["行业地位线索", "管理层公开表态线索", "…" ],
  "profile_overrides": { "可选：覆盖本风格 config/profiles/<style>.yaml 的阈值" }
}
```

## 2. 输出（必须是合法 JSON，字段不可缺省）

```json
{
  "style": "buffett-value",
  "contract_version": "1.0",
  "skill_version": "1.0.0",
  "ticker": "600519.SH",
  "as_of": "2026-11-07",

  "verdict": "pass | fail | gray",
  "score": 78.5,

  "hard_screen": [
    {
      "id": "roe_10y",
      "name": "近10年ROE≥15%",
      "threshold": ">=15% (10年逐年)",
      "actual": "2016-2025: 31.9%…30.2%，全部达标",
      "pass": true,
      "evidence": "metrics.py输出 + 年报交叉核验(2源)",
      "confidence": "A"
    }
  ],

  "qualitative": [
    { "dimension": "moat", "score": 5, "max": 5, "rationale": "品牌+定价权+稀缺产能，且趋势变宽" }
  ],

  "veto_hits": [],
  "key_assumptions": ["酱酒价格管制不恶化", "直销占比提升不引发渠道崩塌"],
  "top_risks": ["…最多3条…"],
  "monitoring": ["季度合同负债同比", "批价走势"],

  "data_gaps": ["分红率2015年前数据缺失，用招股书补"],
  "confidence_grade": "A | B | C",
  "one_line": "一句话结论（供汇总矩阵展示）"
}
```

## 3. 语义约定（全部风格统一）

| 字段 | 规则 |
|---|---|
| `verdict` | **三值制，禁止和稀泥**。`pass`=该风格标准下值得进入下一轮深度研究；`fail`=明确不符合，写清哪条硬指标挂了；`gray`=关键维度存疑或数据不足。编排层禁止要求技能给出二值结论。 |
| `score` | 0–100。构成 = 硬指标得分（权重见 profile）+ 定性维度得分。同风格跨标的可比（因为判据同一份文件），**跨风格不可比**（汇总矩阵不排序混合分数）。 |
| `veto_hits` | 命中即 `verdict=fail`，不管其他分数多高。红线定义在 `skills/shared/common-redflags.md`（全风格通用）+ 风格自有否决项。 |
| `confidence_grade` | A=关键数据双源核验；B=单源或有推算；C=信息严重不足，此时通常应输出 `gray`。**资料多≠确定性高**，评级是对信息质量的独立判断。 |
| `hard_screen[].actual` | 数值必须来自 `computed_metrics`，不得是心算；文字判据必须附可回溯出处。 |
| 缺失数据 | 如实写入 `data_gaps`，禁止编造数值。缺关键硬指标 → 该项 `pass:false, confidence:C`，整体倾向 `gray`。 |

## 4. 版本号纪律

- `SKILL.md` frontmatter 含 `version`（判据变更升 minor，错字/表述修订升 patch）。
- 阈值改动只改 `config/profiles/*.yaml`，与判据解耦。
- 每次升版必须跑 `evals/` 并记录结果，否则不合并（见 evals/README.md）。
