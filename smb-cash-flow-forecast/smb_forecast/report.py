"""Portable CSV exports and a self-contained, escaped HTML management report."""

import csv
from html import escape
from io import StringIO


def csv_output(result):
    stream = StringIO(newline="")
    rows = result["months"]
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if value is None else value for key, value in row.items()})
    return stream.getvalue()


def chart(scenarios):
    width, height, left, top = 900, 290, 100, 24
    plot_width, plot_height = 775, 220
    values = [float(row["ending_cash"]) for result in scenarios.values() for row in result["months"]]
    low, high = min(0, min(values)), max(0, max(values))
    if high == low:
        high = low + 1
    pad = (high - low) * .08
    low, high = low - pad, high + pad
    colors = ["#2563eb", "#d97706", "#059669", "#7c3aed", "#dc2626"]
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Monthly ending cash by scenario">']
    for step in range(5):
        value = low + (high - low) * step / 4
        y = top + plot_height * (1 - step / 4)
        parts.append(f'<line x1="{left}" y1="{y}" x2="{left+plot_width}" y2="{y}" stroke="#e2e8f0"/>')
        parts.append(f'<text x="{left-10}" y="{y+4}" text-anchor="end" fill="#475569" font-size="12">{value:,.0f}</text>')
    for index, (name, result) in enumerate(scenarios.items()):
        rows = result["months"]
        points = []
        for t, row in enumerate(rows):
            x = left + plot_width * t / max(1, len(rows) - 1)
            y = top + plot_height * (high - float(row["ending_cash"])) / (high - low)
            points.append(f"{x:.2f},{y:.2f}")
        color = colors[index % len(colors)]
        parts.append(f'<polyline points="{" ".join(points)}" stroke="{color}" fill="none" stroke-width="3"/>')
        if len(rows) == 1:
            x, y = points[0].split(",")
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    rows = next(iter(scenarios.values()))["months"]
    for t in sorted({0, len(rows)//2, len(rows)-1}):
        x = left + plot_width * t / max(1, len(rows) - 1)
        parts.append(f'<text x="{x}" y="{top+plot_height+25}" text-anchor="middle" font-size="12" fill="#475569">{escape(rows[t]["month"])}</text>')
    parts.append('</svg><div class="legend">')
    for index, name in enumerate(scenarios):
        parts.append(f'<span style="color:{colors[index % len(colors)]}">{escape(name)}</span>')
    parts.append('</div>')
    return "".join(parts)


def report_html(model):
    title, currency = escape(model["model_name"]), escape(model["currency"])
    sections = []
    for name, result in model["scenarios"].items():
        summary = result["summary"]
        fields = ("month", "revenue", "gross_profit", "operating_expenses", "operating_income",
                  "customer_receipts", "cash_outflows", "ending_cash", "ending_cash_variance")
        headers = "".join(f"<th>{escape(field.replace('_', ' ').title())}</th>" for field in fields)
        body = []
        for row in result["months"]:
            cells = "".join(f"<td>{escape(row[key]) if key == 'month' else format(row[key], ',.2f')}</td>" for key in fields)
            body.append(f"<tr>{cells}</tr>")
        runway = summary["cash_runway_months"]
        runway_text = "No recent cash burn" if runway is None else f"{runway} months"
        sections.append(f'''<section><h2>{escape(name.title())}</h2><div class="cards">
        <div><span>Forecast revenue</span><strong>{summary['total_revenue']:,.2f}</strong></div>
        <div><span>Ending cash</span><strong>{summary['ending_cash']:,.2f}</strong></div>
        <div><span>Lowest month-end cash</span><strong>{summary['minimum_ending_cash']:,.2f}</strong></div>
        <div><span>Runway at horizon end</span><strong>{escape(runway_text)}</strong></div></div>
        <p>First negative cash month: {escape(summary['first_negative_cash_month'] or 'None within forecast')}.</p>
        <div class="scroll"><table><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table></div>
        <details><summary>Resolved assumptions</summary><dl>'''
        + "".join(f"<dt>{escape(key)}</dt><dd>{escape(str(value))}</dd>" for key, value in result["assumptions"].items())
        + "</dl></details></section>")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{title}</title><style>
    body{{font:15px system-ui,sans-serif;color:#172033;background:#f1f5f9;margin:0;padding:32px}}
    main{{max-width:1250px;margin:auto}}h1{{font-size:34px;margin:8px 0}}h2{{font-size:23px}}
    .eyebrow{{text-transform:uppercase;letter-spacing:.15em;font-size:12px;color:#2563eb}}
    section{{background:white;border:1px solid #dbe3ed;border-radius:12px;padding:24px;margin:22px 0}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
    .cards div{{background:#f8fafc;border-radius:8px;padding:16px}}span{{display:block;color:#475569;font-size:13px}}
    strong{{display:block;font-size:23px;margin-top:8px}}svg{{width:100%;height:auto}}.legend{{display:flex;gap:20px;flex-wrap:wrap}}
    .scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}}
    th,td{{padding:12px;text-align:right;border-bottom:1px solid #e2e8f0}}th:first-child,td:first-child{{text-align:left}}
    th{{background:#f8fafc}}details{{margin-top:18px}}dl{{display:grid;grid-template-columns:minmax(170px,1fr) 3fr;gap:10px}}
    dd{{margin:0;overflow-wrap:anywhere}}footer{{font-size:13px;color:#475569;line-height:1.6}}
    @media print{{body{{padding:0;background:white}}section{{break-inside:avoid}}}}
    </style></head><body><main><div class="eyebrow">Monthly management report · {currency}</div>
    <h1>{title}</h1><p>Assumption-driven forecast. Amounts in {currency}; scenario variances are signed differences versus base.</p>
    <section><h2>Cash across scenarios</h2>{chart(model['scenarios'])}</section>{''.join(sections)}
    <footer>Operating income excludes depreciation. Taxes are a user-defined arithmetic assumption, with no tax rules modeled.
    Runway divides positive ending cash by trailing three-month average cash burn before debt draws, including capital spending and principal payments;
    it is a heuristic, not a forecast of the exhaustion date. Null runway means no recent burn. Break-even is an operating estimate before interest and tax.
    This model provides calculations, not financial, tax, legal, or investment advice.</footer></main></body></html>'''
