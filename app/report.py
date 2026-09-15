from decimal import Decimal


def text(value):
    return str(value).replace("|", "／").replace("\n", " ").replace("<", "&lt;")


def pct(value):
    return f"{Decimal(str(value)) * 100:.1f}%" if value is not None else "未知"


def number(value):
    return f"{Decimal(str(value)):,.2f}" if value is not None else "未知"


def daily_report(now, portfolio, risk, macro, recommendations, evidence, health):
    lines = [
        f"# 基金每日研究简报 · {now:%Y-%m-%d}",
        "",
        "研究与决策支持 · 人民币 · 无自动交易",
        "",
        "## 资产概览",
        "",
        f"已投资 **¥{number(portfolio['invested'])}** ｜ 可用现金 **{number(portfolio['cash'])}**"
        f" ｜ 总资产 **{number(portfolio['total'])}** ｜ 现金比例 **{pct(portfolio['cash_ratio'])}**",
        "",
        f"组合年化波动率：{pct(risk.get('volatility'))}；最大回撤：{pct(risk.get('max_drawdown'))}。",
        "风险指标按当前权重和已披露净值估算，非账户真实历史收益。",
        "",
        "## 宏观环境",
        "",
    ]
    for region, item in macro.items():
        lines.append(
            f"- {region}：风险 {item['risk_regime']} / 通胀 {item['inflation_regime']} / 利率 {item['rate_regime']}"
        )
    lines += [
        "",
        "## 现有持仓",
        "",
        "基金 | 权重 | 短期评分 | 长期评分 | 动作 | 建议金额 | 置信度",
        "--- | ---: | ---: | ---: | --- | ---: | ---:",
    ]
    for r in recommendations:
        if r["held"]:
            lines.append(
                f"{text(r['name'])} {r['symbol']} | {pct(r['current_weight'])} | "
                f"{r['tactical']['score']} | {r['strategic']['score']} | {r['action']} | "
                f"¥{number(r['proposed_amount'])} | {pct(r['confidence'])}"
            )
    for kind, label in (("tactical", "短期观察机会"), ("strategic", "长期候选机会")):
        lines += ["", f"## {label}", ""]
        candidates = sorted(
            [r for r in recommendations if not r["held"] and r[kind]["score"] is not None],
            key=lambda r: -r[kind]["score"],
        )[:3]
        lines += [
            f"- {text(r['name'])}：{r[kind]['score']} / 100；覆盖率 {pct(r[kind]['coverage'])}"
            for r in candidates
        ] or ["当前没有通过数据检查的已批准候选基金。"]
    lines += ["", "## 风险与数据提醒", ""]
    lines += [f"- {text(w)}" for w in portfolio["warnings"]]
    for r in recommendations:
        if r["rules_triggered"]:
            lines.append(f"- {text(r['name'])}：{'、'.join(r['rules_triggered'])}")
    for stage, state in health.items():
        lines.append(f"- {stage}：{text(state)}")
    lines += ["", "## 建议解释", ""]
    for r in recommendations:
        lines += [
            f"### {text(r['name'])} · {r['action']}",
            "",
            f"金额 ¥{number(r['proposed_amount'])}；覆盖率 {pct(r['data_coverage'])}；"
            f"置信度 {pct(r['confidence'])}（规则评分，非校准后的获利概率）。",
            "",
            text(r["thesis"]),
            "",
            "风险：" + "；".join(map(text, r["risks"])),
            "",
            "失效条件：" + "；".join(map(text, r["invalidation_conditions"])),
            "",
            "证据：" + (", ".join(f"[{e}]" for e in r["evidence_ids"]) or "无符合要求的新闻证据"),
            "",
        ]
    lines += ["## 主要新闻与证据", ""]
    for item in evidence[:10]:
        p = item["payload"]
        lines += [
            f"- [{text(p['title'])}]({item['source_url']}) [{item['id']}] · {item['published_at']}",
            f"  摘要（模型提取）：{text(p['fact'])}；解释：{text(p['interpretation'])}；不确定性：{text(p['uncertainty'])}",
        ]
    if not evidence:
        lines.append("无通过来源与发布时间检查的研究证据。")
    lines += ["", "## 净值来源", ""]
    for r in recommendations:
        if r.get("market_source"):
            lines.append(
                f"- {r['symbol']}：[数据源]({r['market_source']}) · 净值日期 {r.get('nav_date', '未知')}"
            )
    lines += [
        "",
        "场外基金按未知成交净值申赎；申购额度、赎回费、到账时间以基金公司和销售平台确认为准。",
        "未执行任何交易。报告用于个人研究，不构成收益承诺。",
        "",
    ]
    return "\n".join(lines)
