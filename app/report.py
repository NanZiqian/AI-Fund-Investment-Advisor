from decimal import Decimal


def text(value):
    return str(value).replace("|", "／").replace("\n", " ").replace("<", "&lt;")


def pct(value):
    return f"{Decimal(str(value)) * 100:.1f}%" if value is not None else "Unknown"


def number(value):
    return f"{Decimal(str(value)):,.2f}" if value is not None else "Unknown"


def daily_report(now, portfolio, risk, macro, recommendations, evidence, health):
    lines = [
        f"# Daily Fund Research Briefing · {now:%Y-%m-%d}",
        "",
        "Research and decision support · CNY · No automated trading",
        "",
        "## Portfolio Overview",
        "",
        f"Invested **¥{number(portfolio['invested'])}** | "
        f"Available cash **{number(portfolio['cash'])}** | "
        f"Total assets **{number(portfolio['total'])}** | "
        f"Cash ratio **{pct(portfolio['cash_ratio'])}**",
        "",
        f"Annualized portfolio volatility: {pct(risk.get('volatility'))}; "
        f"maximum drawdown: {pct(risk.get('max_drawdown'))}.",
        "Risk metrics use current weights and published NAV data; they are not the "
        "account's realized history.",
        "",
        "## Macro Environment",
        "",
    ]
    for region, item in macro.items():
        lines.append(
            f"- {region}: risk {item['risk_regime']} / "
            f"inflation {item['inflation_regime']} / rates {item['rate_regime']}"
        )
    lines += [
        "",
        "## Current Holdings",
        "",
        "Fund | Weight | Tactical score | Strategic score | Action | Proposed amount | Confidence",
        "--- | ---: | ---: | ---: | --- | ---: | ---:",
    ]
    for r in recommendations:
        if r["held"]:
            lines.append(
                f"{text(r['name'])} {r['symbol']} | {pct(r['current_weight'])} | "
                f"{r['tactical']['score']} | {r['strategic']['score']} | {r['action']} | "
                f"¥{number(r['proposed_amount'])} | {pct(r['confidence'])}"
            )
    for kind, label in (("tactical", "Tactical Watchlist"), ("strategic", "Strategic Candidates")):
        lines += ["", f"## {label}", ""]
        candidates = sorted(
            [r for r in recommendations if not r["held"] and r[kind]["score"] is not None],
            key=lambda r: -r[kind]["score"],
        )[:3]
        lines += [
            f"- {text(r['name'])}: {r[kind]['score']} / 100; coverage {pct(r[kind]['coverage'])}"
            for r in candidates
        ] or ["No approved candidate currently passes the data checks."]
    lines += ["", "## Risk and Data Warnings", ""]
    lines += [f"- {text(w)}" for w in portfolio["warnings"]]
    for r in recommendations:
        if r["rules_triggered"]:
            lines.append(f"- {text(r['name'])}：{'、'.join(r['rules_triggered'])}")
    for stage, state in health.items():
        lines.append(f"- {stage}：{text(state)}")
    lines += ["", "## Recommendation Explanations", ""]
    for r in recommendations:
        lines += [
            f"### {text(r['name'])} · {r['action']}",
            "",
            f"Amount ¥{number(r['proposed_amount'])}; coverage {pct(r['data_coverage'])}; "
            f"confidence {pct(r['confidence'])} "
            "(a rule-based score, not a calibrated profit probability).",
            "",
            text(r["thesis"]),
            "",
            "Risks: " + "; ".join(map(text, r["risks"])),
            "",
            "Invalidation conditions: " + "; ".join(map(text, r["invalidation_conditions"])),
            "",
            "Evidence: "
            + (
                ", ".join(f"[{e}]" for e in r["evidence_ids"])
                or "No qualifying news evidence"
            ),
            "",
        ]
    lines += ["## Material News and Evidence", ""]
    for item in evidence[:10]:
        p = item["payload"]
        lines += [
            f"- [{text(p['title'])}]({item['source_url']}) [{item['id']}] · {item['published_at']}",
            f"  Model-extracted fact: {text(p['fact'])}; "
            f"interpretation: {text(p['interpretation'])}; "
            f"uncertainty: {text(p['uncertainty'])}",
        ]
    if not evidence:
        lines.append("No research evidence passed the source and publication-time checks.")
    lines += ["", "## NAV Sources", ""]
    for r in recommendations:
        if r.get("market_source"):
            lines.append(
                f"- {r['symbol']}: [data source]({r['market_source']}) · "
                f"NAV date {r.get('nav_date', 'Unknown')}"
            )
    lines += [
        "",
        "Off-exchange funds transact at an unknown NAV. Confirm purchase limits, "
        "redemption fees, and settlement timing with the fund manager and sales platform.",
        "No trades were executed. This report is personal research and does not promise returns.",
        "",
    ]
    return "\n".join(lines)
