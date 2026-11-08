#!/usr/bin/env python3
"""metrics.py — 选股指标精确计算器（框架内唯一"代码"，不含任何风格判据逻辑）

设计原则（借鉴 ai-berkshire 的工程教训）：
  LLM 心算金融数据不可靠（小数点、港币亿/人民币亿单位混淆会造成数量级错误）。
  因此所有数值指标一律由本脚本用 decimal.Decimal 精确计算，AI 只做定性判断。

用法：
  python scripts/metrics.py --data path/to/stock_data.json
  python scripts/metrics.py --data path/to/stock_data.json --years 10
  python scripts/metrics.py --verify-cap --price 510 --shares 9.11e9 --reported 4.65e12

输出：stdout 为 JSON（computed_metrics），可直接注入风格技能的输入上下文。
依赖：仅标准库。
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28

ZERO = Decimal("0")
EPS = Decimal("0.0000001")


# ---------- 基础工具 ----------

def D(value) -> Decimal | None:
    """安全转 Decimal。接受 int/str/float(None 透传)，float 先转字符串避免二进制误差。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(str(value))


def out(d: Decimal | None, places: str = "0.0001") -> float | None:
    if d is None:
        return None
    return float(d.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def pct(d: Decimal | None) -> float | None:
    if d is None:
        return None
    return float((d * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def safe_div(num: Decimal | None, den: Decimal | None) -> Decimal | None:
    if num is None or den is None or abs(den) <= EPS:
        return None
    return num / den


# ---------- 单年指标 ----------

def year_metrics(row: dict) -> dict:
    net_profit = D(row.get("net_profit"))
    equity = D(row.get("total_assets")) - D(row.get("total_liab")) \
        if (D(row.get("total_assets")) is not None and D(row.get("total_liab")) is not None) else None
    # 若数据源直接给了股东权益，优先使用
    if row.get("total_equity") is not None:
        equity = D(row.get("total_equity"))

    revenue = D(row.get("revenue"))
    ocf = D(row.get("operating_cash_flow"))
    capex = D(row.get("capex"))
    total_assets = D(row.get("total_assets"))
    long_debt = D(row.get("long_debt"))

    roe = safe_div(net_profit, equity)
    # ROIC 近似：NOPAT / (净资产 + 长期有息负债)，缺所得税数据用净利润替代
    nopat = net_profit
    invested_cap = (equity + long_debt) if (equity is not None and long_debt is not None) else None
    roic = safe_div(nopat, invested_cap)

    fcf = (ocf - capex) if (ocf is not None and capex is not None) else None

    return {
        "year": row.get("year"),
        "period": row.get("period", "FY"),
        "revenue": out(revenue, "0.01"),
        "net_profit": out(net_profit, "0.01"),
        "eps": out(D(row.get("eps"))),
        "gross_margin_pct": pct(D(row.get("gross_margin"))),
        "net_margin_pct": pct(D(row.get("net_margin"))),
        "roe_pct": pct(roe),
        "roic_pct": pct(roic),
        "ocf": out(ocf, "0.01"),
        "fcf": out(fcf, "0.01"),
        "fcf_to_net_profit": out(safe_div(fcf, net_profit)) if (net_profit is not None and net_profit > ZERO) else None,
        "ocf_to_net_profit": out(safe_div(ocf, net_profit)) if (net_profit is not None and net_profit > ZERO) else None,
        "debt_to_assets_pct": pct(safe_div(D(row.get("total_liab")), total_assets)),
        "current_ratio": out(safe_div(D(row.get("current_assets")), D(row.get("current_liab")))),
        "rd_ratio_pct": pct(safe_div(D(row.get("rd_expense")), revenue)),
        "payout_ratio_pct": pct(safe_div(D(row.get("dps")), D(row.get("eps")))),
        "inventory": out(D(row.get("inventory")), "0.01"),
        "receivables": out(D(row.get("receivables")), "0.01"),
    }


# ---------- 跨期指标 ----------

def cagr(begin: Decimal | None, end: Decimal | None, years: int) -> Decimal | None:
    if begin is None or end is None or years <= 0:
        return None
    if begin <= ZERO or end <= ZERO:
        return None
    return (end / begin) ** (Decimal(1) / Decimal(years)) - Decimal(1)


def series(rows: list[dict], field: str) -> list[Decimal | None]:
    return [D(r.get(field)) for r in rows]


def min_of(vals: list[Decimal | None]) -> Decimal | None:
    clean = [v for v in vals if v is not None]
    return min(clean) if clean else None


def count_below(vals: list[Decimal | None], thr: Decimal) -> int | None:
    clean = [v for v in vals if v is not None]
    if not clean:
        return None
    return sum(1 for v in clean if v < thr)


# ---------- 主计算 ----------

def compute(data: dict, years: int) -> dict:
    meta = data.get("meta", {})
    price = data.get("price", {})
    raw_rows = data.get("financials", []) or []
    rows = sorted(raw_rows, key=lambda r: (r.get("year") or 0), reverse=True)[:years]
    rows_asc = list(reversed(rows))

    per_year = []
    for r in rows_asc:
        m = year_metrics(r)
        per_year.append(m)

    # 重新按年计算序列指标（使用原始字段优先）
    rev = series(rows_asc, "revenue")
    npf = series(rows_asc, "net_profit")
    eps = series(rows_asc, "eps")
    sh = series(rows_asc, "shares_outstanding")
    inv = series(rows_asc, "inventory")
    rec = series(rows_asc, "receivables")

    # 比率序列：源字段优先；缺失时回退 year_metrics 推算值（% 转回小数）
    def direct_or(src_field: str, metric_key: str) -> list[Decimal | None]:
        vals: list[Decimal | None] = []
        for r, m in zip(rows_asc, per_year):
            v = D(r.get(src_field))
            if v is None and m.get(metric_key) is not None:
                v = D(m[metric_key]) / Decimal(100)
            vals.append(v)
        return vals

    roe_direct = direct_or("roe", "roe_pct")
    roic_direct = direct_or("roic", "roic_pct")
    gm_direct = direct_or("gross_margin", "gross_margin_pct")

    span = len(rows_asc) - 1 if len(rows_asc) > 1 else 0

    latest = rows_asc[-1] if rows_asc else {}
    latest_price = D(price.get("close"))
    latest_eps = D(latest.get("eps"))
    latest_div = D(latest.get("dps"))

    pe = safe_div(latest_price, latest_eps)
    bvps = None
    equity_latest = D(latest.get("total_equity"))
    if equity_latest is None:
        ta, tl = D(latest.get("total_assets")), D(latest.get("total_liab"))
        equity_latest = (ta - tl) if (ta is not None and tl is not None) else None
    if equity_latest is not None and D(latest.get("shares_outstanding")) is not None:
        bvps = safe_div(equity_latest, D(latest.get("shares_outstanding")))
    pb = safe_div(latest_price, bvps)

    # 盈利增速（用于 PEG）：取净利与营收 CAGR 的较低者，保守口径
    profit_cagr = cagr(npf[0], npf[-1], span)
    revenue_cagr = cagr(rev[0], rev[-1], span)
    growth_for_peg = min([g for g in (profit_cagr, revenue_cagr) if g is not None], default=None)
    peg = safe_div(pe, (growth_for_peg * Decimal(100))) if growth_for_peg is not None else None

    # 5 年窗口 CAGR（fisher-growth 判据口径）：基期<=0 时返回 None，禁止编造增速
    def cagr_last_n(vals: list[Decimal | None], n: int):
        seq = [(i, v) for i, v in enumerate(vals) if v is not None]
        if len(seq) < 2:
            return None
        end_i, end_v = seq[-1]
        idx = [i for i, v in seq if i <= end_i - n]
        if not idx:
            return None
        begin_i, begin_v = seq[max(idx, key=lambda i: i)]
        yrs = end_i - begin_i
        if yrs <= 0:
            return None
        return cagr(begin_v, end_v, yrs)

    rev_cagr_5y = cagr_last_n(rev, 5)
    np_cagr_5y = cagr_last_n(npf, 5)

    # 逐年负增长计数（fisher A 维 / graham g3 / buffett 校验用）
    def count_negative(deltas: list[Decimal | None]) -> int | None:
        clean = [v for v in deltas if v is not None]
        return sum(1 for v in clean if v < ZERO) if clean else None

    def yoy(vals: list[Decimal | None]) -> list[Decimal | None]:
        return [safe_div(b - a, abs(a)) if (a is not None and b is not None and abs(a) > EPS)
                else None for a, b in zip(vals, vals[1:])]

    rev_neg_years = count_negative(yoy(rev))
    np_neg_years = count_negative(yoy(npf))
    eps_min = min_of(eps)

    # 股本 3 年增长率（RF-07 / buffett equity_3y_growth_max / fisher 要点13）
    shares_3y_growth = None
    sh_clean = [(i, v) for i, v in enumerate(sh) if v is not None]
    if len(sh_clean) >= 2:
        end_i, end_v = sh_clean[-1]
        base = [(i, v) for i, v in sh_clean if i <= end_i - 3]
        if base:
            bi, bv = max(base, key=lambda x: x[0])
            shares_3y_growth = safe_div(end_v - bv, bv) if bi < end_i else None

    # EPS 累计增长（graham g5：10 年 ≥ 1/3）。基期 EPS<=0 时 None 并说明
    eps_growth_cum = safe_div(eps[-1] - eps[0], abs(eps[0])) if (
        eps and eps[-1] is not None and eps[0] is not None and abs(eps[0]) > EPS
        and eps[0] > ZERO) else None

    # 营运资本膨胀检验（lynch ly3/ly6 / fisher 要点4）：增速超过营收即红旗
    def growth_of_last(vals: list[Decimal | None]):
        clean = [(i, v) for i, v in enumerate(vals) if v is not None]
        if len(clean) < 2:
            return None
        (i0, v0), (i1, v1) = clean[-2], clean[-1]
        yrs = i1 - i0
        if yrs <= 0 or v0 is None or abs(v0) <= EPS or v0 <= ZERO or v1 <= ZERO:
            return None
        return (v1 / v0) ** (Decimal(1) / Decimal(yrs)) - Decimal(1)

    inv_cagr_last = growth_of_last(inv)
    rec_cagr_last = growth_of_last(rec)
    rev_cagr_last = growth_of_last(rev)

    dividend_yield = safe_div(latest_div, latest_price)

    # 格雷厄姆复合指标：PE × PB ≤ 22.5（等价于 15 × 1.5）
    pe_pb = (pe * pb) if (pe is not None and pb is not None) else None

    # 现金流质量：近 N 年 FCF/净利 的中位倾向（逐年比值均值）
    fcf_np = [D(m.get("fcf_to_net_profit")) for m in per_year]
    fcf_np = [v for v in fcf_np if v is not None]
    fcf_np_avg = (sum(fcf_np) / Decimal(len(fcf_np))) if fcf_np else None

    # 所有者收益近似（巴菲特口径）：经营现金流 - 维持性资本开支（用全部 capex 保守替代）
    owner_earnings = None
    if latest:
        ocf_l, capex_l = D(latest.get("operating_cash_flow")), D(latest.get("capex"))
        owner_earnings = (ocf_l - capex_l) if (ocf_l is not None and capex_l is not None) else None

    metrics = {
        "meta": {"ticker": meta.get("ticker"), "name": meta.get("name"),
                 "as_of": meta.get("as_of"), "currency": meta.get("currency", "CNY"),
                 "years_used": len(rows_asc), "window": years},
        "valuation": {
            "pe": out(pe), "pb": out(pb), "pe_x_pb": out(pe_pb),
            "dividend_yield_pct": pct(dividend_yield),
            "eps": out(latest_eps), "bvps": out(bvps),
            "market_cap": out(D(price.get("market_cap")), "0.01"),
            "peg": out(peg),
        },
        "profitability": {
            "roe_latest_pct": pct(roe_direct[-1]) if roe_direct else None,
            "roe_min_pct": pct(min_of(roe_direct)),
            "roe_years_below_15pct": count_below(roe_direct, Decimal("0.15")),
            "roic_min_pct": pct(min_of(roic_direct)),
            "gross_margin_min_pct": pct(min_of(gm_direct)),
        },
        "growth": {
            "revenue_cagr_pct": pct(revenue_cagr),
            "net_profit_cagr_pct": pct(profit_cagr),
            "growth_window_years": span,
            "revenue_cagr_5y_pct": pct(rev_cagr_5y),
            "net_profit_cagr_5y_pct": pct(np_cagr_5y),
            "revenue_negative_growth_years": rev_neg_years,
            "net_profit_negative_growth_years": np_neg_years,
            "eps_cumulative_growth_pct": pct(eps_growth_cum),
            "shares_3y_growth_pct": pct(shares_3y_growth),
            "inventory_cagr_last_pct": pct(inv_cagr_last),
            "receivables_cagr_last_pct": pct(rec_cagr_last),
            "revenue_cagr_last_pct": pct(rev_cagr_last),
        },
        "profitability_extra": {
            "eps_min": out(eps_min),
        },
        "cash_and_quality": {
            "fcf_to_net_profit_avg": out(fcf_np_avg),
            "owner_earnings_latest": out(owner_earnings, "0.01"),
            "debt_to_assets_latest_pct": pct(safe_div(D(latest.get("total_liab")), D(latest.get("total_assets")))),
            "current_ratio_latest": out(safe_div(D(latest.get("current_assets")), D(latest.get("current_liab")))),
            "rd_ratio_latest_pct": pct(safe_div(D(latest.get("rd_expense")), D(latest.get("revenue")))),
        },
        "per_year": per_year,
        "notes": [
            "所有数值由 decimal 精确计算，AI 不得重算或改写。",
            "roe/roic 为空表示源数据缺失，技能须计入 data_gaps 并降级 confidence。",
            "ROIC 为近似口径（NOPAT≈净利润，未做税项调整）；如需严谨请提供所得税数据。",
            "growth.*_cagr_5y 为最近5年窗口口径；基期数值<=0 时返回 null——禁止用其他年份顶替或自行估算。",
            "eps_cumulative_growth_pct / shares_3y_growth_pct 供 graham g5 与 RF-07 直接引用，均为保守口径（基期非正返回 null）。",
            "inventory/receivables/revenue_cagr_last_pct 为最近相邻期间复合增速，供 ly3/ly6 与费雪要点4 做膨胀对比。",
        ],
    }

    # 市值一致性校验（单位陷阱兜底）
    cap_check = verify_market_cap(
        D(price.get("close")), D(latest.get("shares_outstanding")) or D(price.get("shares_outstanding")),
        D(price.get("market_cap")))
    if cap_check:
        metrics["market_cap_check"] = cap_check
    return metrics


def verify_market_cap(price: Decimal | None, shares: Decimal | None, reported: Decimal | None) -> dict | None:
    if price is None or shares is None or reported is None:
        return None
    calc = price * shares
    diff = abs(calc - reported) / reported if reported else None
    ok = diff is not None and diff <= Decimal("0.01")
    return {
        "calc_market_cap": out(calc, "0.01"),
        "reported_market_cap": out(reported, "0.01"),
        "deviation_pct": pct(diff),
        "pass": bool(ok),
        "hint": None if ok else "偏差>1%，疑似股本口径或币种单位错误（港币亿/人民币亿），必须人工复核后再进入判据",
    }


# ---------- CLI ----------

def main(argv: list[str]) -> int:
    # Windows 控制台/重定向默认 GBK，会把中文 JSON 写坏，固定为 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="选股指标精确计算器")
    ap.add_argument("--data", help="数据包 JSON 路径（见 docs/data-contract.md）")
    ap.add_argument("--years", type=int, default=10, help="回看年数，默认10")
    ap.add_argument("--verify-cap", action="store_true", help="仅做市值校验")
    ap.add_argument("--price", help="股价")
    ap.add_argument("--shares", help="总股本")
    ap.add_argument("--reported", help="报告市值")
    args = ap.parse_args(argv)

    if args.verify_cap:
        try:
            res = verify_market_cap(D(args.price), D(args.shares), D(args.reported))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": f"参数无法解析: {exc}"}, ensure_ascii=False))
            return 2
        print(json.dumps({"market_cap_check": res}, ensure_ascii=False, indent=2))
        return 0

    if not args.data:
        ap.print_help()
        return 2

    try:
        with open(args.data, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(json.dumps({"error": f"数据文件不存在: {args.data}"}, ensure_ascii=False))
        return 2
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"JSON 解析失败: {exc}"}, ensure_ascii=False))
        return 2

    print(json.dumps(compute(data, args.years), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
