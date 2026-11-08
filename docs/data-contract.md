# 数据包契约（Stock Data Pack）v1.0

风格技能不关心数据从哪来，只消费本格式的 `data_pack`。数据适配器（可插拔）负责把外部来源转成本格式。

## 字段定义

```json
{
  "meta": { "ticker": "002472.SZ", "name": "双环传动", "as_of": "2026-11-07", "currency": "CNY", "market": "A" },
  "price": { "close": 45.20, "market_cap": 38500000000, "shares_outstanding": 851000000 },
  "financials": [
    {
      "year": 2025, "period": "FY",
      "revenue": 9210000000, "net_profit": 1210000000, "eps": 1.42, "dps": 0.50,
      "gross_margin": 0.281, "net_margin": 0.131, "roe": 0.161, "roic": null,
      "total_assets": 20100000000, "total_liab": 10300000000,
      "current_assets": 8900000000, "current_liab": 6700000000,
      "long_debt": 1500000000, "net_cash": 2100000000,
      "operating_cash_flow": 1650000000, "capex": 980000000,
      "rd_expense": 420000000, "shares_outstanding": 851000000,
      "inventory": 3200000000, "receivables": 2100000000
    }
  ],
  "dividends": [ { "year": 2025, "payout_ratio": 0.35, "record_years": 12 } ],
  "quality_flags": {
    "audit_opinion": "标准无保留",
    "major_shareholder_pledge": 0.08,
    "goodwill_ratio": 0.03,
    "regulatory_penalties": [],
    "going_concern": false
  },
  "industry": { "level1": "汽车零部件", "level2": "齿轮", "market_share_note": "乘用车变速器齿轮国内份额领先" },
  "sources": [ { "field": "financials", "from": "2025年报", "verified_by": ["巨潮资讯", "交易所公告"] } ]
}
```

规则：
- `financials` 至少给到 10 年（格雷厄姆/巴菲特风格需要）；不足 10 年时技能必须降级 confidence 并在 `data_gaps` 声明。
- 所有金额为**元**、比率为**小数**（0.15 而非 15%），避免 LLM 单位换算出错。
- 每个关键数值应可回溯到 `sources`；双源核验的标 `verified_by` 两项以上。
- 市值单位陷阱（港币亿/人民币亿）由 `metrics.py verify-market-cap` 类校验兜底：股价×总股本 vs 报告市值，偏差>1% 报警。
- `inventory` / `receivables` 用于营运资本膨胀检验（林奇 ly3/ly6、费雪要点 4）。**缺失时脚本对应字段返回 null，技能必须走 data_gaps，不得跳过该判据假装通过。**
- `computed_metrics.growth` 中 `*_cagr_5y`（费雪 A 维）、`eps_cumulative_growth_pct`（格雷厄姆 g5）、`shares_3y_growth_pct`（RF-07）均为**保守口径**：基期值非正或样本不足时返回 null。null 的含义是"无法计算"，不是"增长为 0"，判定时必须区分。

## 数据源适配器（Phase 2 逐个实现，输出必须符合本契约）

| 适配器 | 适用 | 说明 |
|---|---|---|
| 手工模板 | 任意 | `evals/fixtures/` 的 JSON 即模板，最可靠 |
| finance-data skill（千问） | A股/港股/美股 | 行情+财务指标直接可得 |
| akshare | A股为主 | 免费，脚本抓取后转本格式 |
| tushare | A股 | 需 token |
| yfinance / Financial Datasets | 美股 | 借鉴 ai-hedge-fund / value-investing-mcp 的做法 |

## 定性线索（qualitative_leads）

不属于数据包，由编排层在分发前检索补充：近期公告要点、业绩会纪要、行业地位报道、管理层公开承诺记录等。技能引用时必须标注出处；查不到就写进 `data_gaps`，不许脑补。
