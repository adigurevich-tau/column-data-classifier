"""Generate a self-contained HTML report without exposing CSV cell values."""
from html import escape
from pathlib import Path
from datetime import datetime


def _percent(value):
    return f"{value:.0%}"


def _candidate_rows(candidates):
    if not candidates:
        return '<p class="muted">No candidate checks were available.</p>'
    rows = []
    for candidate in candidates:
        status = "Passed" if candidate.get("accepted") else "Not passed"
        status_class = "passed" if candidate.get("accepted") else "failed"
        rows.append(
            "<tr>"
            f"<td>{escape(str(candidate.get('data_class', 'Unknown')))}</td>"
            f"<td>{_percent(candidate.get('mandatory_rate', 0))}</td>"
            f"<td>{_percent(candidate.get('supplemental_rate', 0))}</td>"
            f'<td><span class="check-status {status_class}">{status}</span></td>'
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>Category</th><th>Mandatory</th><th>Supplemental</th><th>Decision</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def render_report(results, source_name, rows_evaluated):
    """Return report HTML. CSV cell values are deliberately never accepted here."""
    total = len(results)
    classified = sum(item.get("data_class") != "Not classified" for item in results)
    unclassified = total - classified
    categories = sorted({
        item.get("data_class") for item in results
        if item.get("data_class") != "Not classified"
    })
    cards = []

    for index, item in enumerate(results, 1):
        category = item.get("data_class", "Not classified")
        is_classified = category != "Not classified"
        confidence = item.get("confidence") or "—"
        status_class = "classified" if is_classified else "unclassified"
        candidates = item.get("candidates", [])
        details = _candidate_rows(candidates)
        mandatory = supplemental = None
        if is_classified:
            matched = next((c for c in candidates if c.get("data_class") == category and c.get("accepted")), None)
            if matched:
                mandatory = _percent(matched.get("mandatory_rate", 0))
                supplemental = _percent(matched.get("supplemental_rate", 0))
        metrics = ""
        if is_classified and mandatory is not None:
            metrics = (
                '<div class="metrics">'
                f'<div><span>Mandatory matches</span><strong>{mandatory}</strong></div>'
                f'<div><span>Supplemental matches</span><strong>{supplemental}</strong></div>'
                "</div>"
            )
        cards.append(
            f'<article class="column-card {status_class}">'
            '<div class="card-heading">'
            f'<div><span class="eyebrow">COLUMN {index:02d}</span><h3>{escape(str(item.get("column", "")))}</h3></div>'
            f'<span class="pill {status_class}">{escape(category)}</span>'
            "</div>"
            f'<div class="card-subtitle"><span>Confidence: <strong>{escape(str(confidence))}</strong></span>'
            f'<span>Non-empty rows: <strong>{int(item.get("rows_non_empty", 0)):,}</strong></span></div>'
            f'{metrics}'
            f'<p class="reason">{escape(str(item.get("reason", "")))}</p>'
            '<details><summary>View category checks</summary>'
            f'{details}</details></article>'
        )

    overview_rows = []
    for item in results:
        column_name = escape(str(item.get("column", "")))
        tag = escape(str(item.get("data_class") or "Not classified"))
        overview_rows.append(f"<tr><td>{column_name}</td><td>{tag}</td></tr>")
    overview_table = (
        '<section aria-label="Column classification summary">'
        '<h2>Column classification summary</h2>'
        '<div class="table-wrap"><table>'
        '<thead><tr><th>Column name</th><th>Tag</th></tr></thead>'
        '<tbody>' + "".join(overview_rows) + '</tbody></table></div></section>'
    )

    category_text = ", ".join(escape(str(name)) for name in categories) if categories else "None"
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Classification report — {escape(str(source_name))}</title>
<style>
:root {{ color-scheme: light; --ink:#172033; --muted:#667085; --line:#e5e9f0; --bg:#f5f7fb; --blue:#3157c8; --green:#137a52; --amber:#946200; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:36px 22px 60px; }}
header {{ display:flex; justify-content:space-between; align-items:flex-start; gap:20px; margin-bottom:26px; }}
h1 {{ margin:0 0 5px; font-size:clamp(25px,4vw,34px); letter-spacing:-.7px; }}
h2 {{ margin:30px 0 14px; font-size:19px; }}
h3 {{ margin:2px 0 0; font-size:18px; overflow-wrap:anywhere; }}
p {{ margin:0; }}
.muted,.eyebrow,.card-subtitle {{ color:var(--muted); }}
.eyebrow {{ font-size:11px; font-weight:700; letter-spacing:1px; }}
.generated {{ color:var(--muted); font-size:12px; text-align:right; }}
.summary {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; }}
.stat,.column-card {{ background:white; border:1px solid var(--line); border-radius:14px; box-shadow:0 2px 8px #17203308; }}
.stat {{ padding:18px; }}
.stat strong {{ display:block; font-size:29px; letter-spacing:-1px; }}
.stat span {{ color:var(--muted); font-size:13px; }}
.column-list {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.column-card {{ padding:18px; min-width:0; }}
.column-card.unclassified {{ border-left:4px solid #c5cbd5; }}
.column-card.classified {{ border-left:4px solid #4ba982; }}
.card-heading {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
.pill {{ border-radius:999px; padding:5px 9px; font-size:11px; font-weight:700; text-align:center; }}
.pill.classified {{ background:#e8f6ef; color:var(--green); }}
.pill.unclassified {{ background:#eef1f5; color:#596273; }}
.card-subtitle {{ display:flex; flex-wrap:wrap; gap:14px; font-size:12px; margin-top:12px; }}
.card-subtitle strong {{ color:var(--ink); }}
.metrics {{ display:flex; gap:24px; margin-top:14px; padding:12px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
.metrics div {{ display:grid; gap:2px; }}
.metrics span {{ color:var(--muted); font-size:11px; }}
.metrics strong {{ font-size:18px; }}
.reason {{ color:#475467; font-size:13px; margin-top:13px; }}
details {{ margin-top:14px; border-top:1px solid var(--line); padding-top:12px; }}
summary {{ cursor:pointer; color:var(--blue); font-size:13px; font-weight:650; }}
.table-wrap {{ overflow-x:auto; margin-top:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ padding:8px 7px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }}
th {{ color:var(--muted); font-weight:650; }}
.check-status.passed {{ color:var(--green); font-weight:700; }}
.check-status.failed {{ color:var(--muted); }}
.privacy {{ margin-top:26px; padding:14px 16px; background:#edf3ff; border:1px solid #dce6ff; border-radius:12px; color:#34466f; font-size:13px; }}
footer {{ margin-top:24px; color:var(--muted); font-size:12px; }}
@media(max-width:760px) {{ .summary {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .column-list {{ grid-template-columns:1fr; }} header {{ display:block; }} .generated {{ text-align:left; margin-top:8px; }} }}
</style>
</head>
<body><main>
<header><div><h1>Column classification report</h1><p class="muted">{escape(str(source_name))}</p></div><div class="generated">Generated {escape(generated)}</div></header>
{overview_table}\n<section class="summary" aria-label="Summary">
<div class="stat"><strong>{total:,}</strong><span>Total columns</span></div>
<div class="stat"><strong>{classified:,}</strong><span>Classified</span></div>
<div class="stat"><strong>{unclassified:,}</strong><span>Not classified</span></div>
<div class="stat"><strong>{int(rows_evaluated):,}</strong><span>Rows evaluated</span></div>
</section>
<h2>Column results</h2>
<p class="muted">Detected categories: {category_text}</p>
<section class="column-list" aria-label="Column results" style="margin-top:14px">{"".join(cards)}</section>
<div class="privacy"><strong>Privacy:</strong> This report contains column headers and classification statistics only. It does not include CSV cell values or sample records.</div>
<footer>Generated by Column Data Classifier. The original CSV is not modified.</footer>
</main></body></html>"""


def write_report(results, csv_path, rows_evaluated):
    """Write <csv-stem>_report.html beside the source CSV and return its path."""
    csv_path = Path(csv_path)
    output_path = csv_path.with_name(f"{csv_path.stem}_report.html")
    html = render_report(results, csv_path.name, rows_evaluated)
    output_path.write_text(html, encoding="utf-8")
    return output_path
