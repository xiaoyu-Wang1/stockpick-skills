# 新增一种选股风格（10 分钟上手）

目标：`skills/<你的风格>/` 出现后，编排层无需任何改动就能调用它。

## Step 1 · 复制骨架

```bash
mkdir -p skills/my-style/references
cp skills/buffett-value/SKILL.md skills/my-style/SKILL.md   # 参考结构，内容重写
cp config/profiles/buffett-value.yaml config/profiles/my-style.yaml
```

## Step 2 · 写 SKILL.md

frontmatter 必填（客户端靠它发现和触发）：
```yaml
---
name: my-style                 # 与目录名一致，小写连字符
description: 一句话说清：做什么 + 用户会怎么说。这是触发准确率的关键。
version: 1.0.0
---
```

正文骨架（缺一不可）：

1. **风格本质**：本派在买什么？与现有四派的**分歧点**是什么？
   （这段是给 AI 的"判据精神"，没有它，AI 会把新风格写成巴菲特的复读。要求：能用一句话说出"同样的茅台，本派会在哪一条上和巴菲特派打起来"。）
2. **执行前必读**：`skills/shared/common-redflags.md` + references + `config/profiles/my-style.yaml` + 数值纪律声明。
3. **判据表**：
   - 硬指标（数值类）：每条必须有 `id`、阈值、判据来源（指向 `computed_metrics` 的具体字段）、缺数据时的降级策略。
   - 定性维度（判断类）：每项必须有 1–5 分的**评分锚点**（"5 分长什么样"必须写出来），以及必答的反问句。
   - 否决项：本派特有的 veto。
4. **打分与三值规则**：明确写"什么组合算 pass / fail / gray"，并把最常见的两个误判写成反例。
5. **输出示例**：给一条 `one_line` 范例，格式与实际风格一致。

## Step 3 · references 怎么写

- 只在判据复杂到"塞进 SKILL.md 会让主文件超过 ~200 行"时才拆。
- 每个 reference 开头一句"本文件何时加载"。渐进披露的前提是**加载条件明确**。
- 判据要写成"可核查动作"而非理念摘抄。对比：
  - ❌ "管理层应当诚实守信"
  - ✅ "找 3 年前的公开承诺逐条对账；逆境期公告是否主动量化说明；命中即记 veto"

## Step 4 · profile

阈值全部外置。规则：
- SKILL.md 里引用阈值时用"见 profile"，硬编码数字只允许出现在"默认值说明"里。
- 权重合计 = 100（编排层会校验）。
- 每个数值一行注释：这是什么口径、为什么是这个数。

## Step 5 · 自检（合并前必须过）

```
□ 契约 JSON 输出与 style-skill-contract.md 字段完全一致
□ verdict 严格三值，无"建议关注/需权衡"句式
□ 所有数值判据指向 computed_metrics 字段名，而非自算
□ 缺数据分支有明确定义（进 data_gaps，不编造）
□ 与现有四派至少有一处显式分歧，写在"风格本质"里
□ 跑 evals/fixtures/example-stock.json，8 项 checklist 全过
□ 跑一个"该被本派选中"的标的和一个"该被本派否决"的标的，结果符合预期
□ version 从 1.0.0 起；后续判据改动升 minor 并留 eval 记录
```

## 注册到编排层？

不用。orchestrator 从 `skills/` 目录枚举契约合规的技能，profile 存在即生效。你唯一要做的是在调用时说清启用哪些风格。

## 常见错误

1. **写成研报模板**：SKILL.md 不是"报告应该包含哪些章节"，是"按什么标准取舍公司"。输出结构已由契约规定，正文只写判据。
2. **判据互相矛盾**：例如硬指标要求 PE<10 又定性"容忍高估值成长"——AI 会随机服从一条。冲突必须显式分优先级。
3. **忘记灰色分支**：真实数据永远缺几项。没定义缺数据行为的风格，上线后必产生幻觉数字。
