"""
UIFPI — Monthly PDF report generator

Generates a one-page-per-section PDF summary of each month's findings:

  - Total items collected this month
  - Price changes detected vs last month
  - Current UIFPI vs official CPI per country
  - Restaurants added / removed this month
  - Running Granger p-value tracker

Output: reports/uifpi_report_YYYY-MM.pdf

Usage:
    python3 monthly_report.py                 # current month
    python3 monthly_report.py 2026-05         # explicit month
"""
import json
import os
import sqlite3
import sys
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'uifpi.db')
DASHBOARD_DIR = os.path.join(BASE_DIR, 'dashboard_data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')


# ── Data helpers ──────────────────────────────────────────────────────────────

def _month_bounds(month_str):
    """Return (start_date, end_date) ISO strings for the given YYYY-MM."""
    year, month = (int(p) for p in month_str.split('-'))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def _prev_month(month_str):
    year, month = (int(p) for p in month_str.split('-'))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json(name):
    path = os.path.join(DASHBOARD_DIR, name)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def gather_items_collected(conn, month):
    start, end = _month_bounds(month)
    rows = conn.execute(
        '''SELECT country, COUNT(*) AS n_items,
                  COUNT(DISTINCT restaurant_name) AS n_restaurants
           FROM prices
           WHERE collection_date >= ? AND collection_date < ?
           GROUP BY country
           ORDER BY country''',
        (start, end),
    ).fetchall()
    total_items = sum(r['n_items'] for r in rows)
    total_restaurants = conn.execute(
        '''SELECT COUNT(DISTINCT restaurant_name)
           FROM prices
           WHERE collection_date >= ? AND collection_date < ?''',
        (start, end),
    ).fetchone()[0]
    return [dict(r) for r in rows], total_items, total_restaurants


def gather_price_changes(conn, month):
    start, end = _month_bounds(month)
    has_table = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='price_history'"
    ).fetchone()
    if not has_table:
        return [], 0
    rows = conn.execute(
        '''SELECT country, COUNT(*) AS n_changes,
                  AVG(price_change_pct) AS avg_pct,
                  MAX(price_change_pct) AS max_pct,
                  MIN(price_change_pct) AS min_pct
           FROM price_history
           WHERE change_detected_date >= ? AND change_detected_date < ?
           GROUP BY country
           ORDER BY country''',
        (start, end),
    ).fetchall()
    total = sum(r['n_changes'] for r in rows)
    return [dict(r) for r in rows], total


def gather_uifpi_vs_cpi(month):
    """Per-country: latest UIFPI value compared to most recent CPI."""
    latest = _load_json('latest_values.json')
    out = []
    for country, blob in sorted(latest.items()):
        out.append({
            'country': country,
            'month': blob.get('month'),
            'uifpi': blob.get('uifpi'),
            'cpi': blob.get('cpi'),
            'yoy_change_pct': blob.get('yoy_change_pct'),
        })
    return out


def gather_restaurant_changes(conn, month):
    """Restaurants newly seen this month, or absent vs last month."""
    start, end = _month_bounds(month)
    prev_start, prev_end = _month_bounds(_prev_month(month))

    this_month = set(r[0] for r in conn.execute(
        '''SELECT DISTINCT restaurant_name
           FROM prices
           WHERE collection_date >= ? AND collection_date < ?''',
        (start, end),
    ).fetchall())
    last_month = set(r[0] for r in conn.execute(
        '''SELECT DISTINCT restaurant_name
           FROM prices
           WHERE collection_date >= ? AND collection_date < ?''',
        (prev_start, prev_end),
    ).fetchall())
    added = sorted(this_month - last_month)
    removed = sorted(last_month - this_month)
    return added, removed


def gather_granger():
    summary = _load_json('country_summary.json')
    rows = []
    for country, stats in sorted(summary.items()):
        rows.append({
            'country': country,
            'p_value': stats.get('granger_p_value'),
            'significant': stats.get('granger_significant'),
            'lead_months': stats.get('lead_months'),
            'n_obs': stats.get('n_obs'),
            'status': stats.get('status'),
        })
    return rows


# ── PDF rendering ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name='SectionHeader',
        parent=base['Heading2'],
        textColor=colors.HexColor('#1F3A93'),
        spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name='SmallNote',
        parent=base['BodyText'],
        fontSize=9,
        textColor=colors.grey,
    ))
    return base


def _table(data, col_widths=None, header_bg='#1F3A93'):
    t = Table(data, colWidths=col_widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.HexColor('#F4F6FB'), colors.white]),
        ('GRID',         (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _fmt(v, digits=2):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def build_report(month, out_path):
    conn = _conn()

    items_per_country, total_items, total_restaurants = gather_items_collected(conn, month)
    change_rows, total_changes = gather_price_changes(conn, month)
    uifpi_vs_cpi = gather_uifpi_vs_cpi(month)
    added, removed = gather_restaurant_changes(conn, month)
    granger = gather_granger()
    conn.close()

    styles = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph(
        f"UIFPI Monthly Report — {month}",
        styles['Title'],
    ))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles['SmallNote'],
    ))
    story.append(Spacer(1, 0.25 * inch))

    # ── Items collected ──────────────────────────────────────────────────
    story.append(Paragraph("1. Items collected this month", styles['SectionHeader']))
    story.append(Paragraph(
        f"Total items: <b>{total_items:,}</b> across <b>{total_restaurants}</b> "
        "distinct restaurants.",
        styles['BodyText'],
    ))
    story.append(Spacer(1, 0.1 * inch))
    table_rows = [['Country', 'Items', 'Restaurants']]
    for row in items_per_country:
        table_rows.append([row['country'], f"{row['n_items']:,}",
                           str(row['n_restaurants'])])
    if len(table_rows) > 1:
        story.append(_table(table_rows, col_widths=[2.2*inch, 1.0*inch, 1.2*inch]))
    else:
        story.append(Paragraph("No data collected for this month.", styles['SmallNote']))
    story.append(PageBreak())

    # ── Price changes ────────────────────────────────────────────────────
    story.append(Paragraph("2. Price changes vs prior month", styles['SectionHeader']))
    story.append(Paragraph(
        f"Total changes detected: <b>{total_changes:,}</b>",
        styles['BodyText'],
    ))
    story.append(Spacer(1, 0.1 * inch))
    rows = [['Country', 'Changes', 'Avg %', 'Max %', 'Min %']]
    for r in change_rows:
        rows.append([
            r['country'], str(r['n_changes']),
            _fmt(r['avg_pct'], 2),
            _fmt(r['max_pct'], 2),
            _fmt(r['min_pct'], 2),
        ])
    if len(rows) > 1:
        story.append(_table(rows, col_widths=[1.7*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch]))
    else:
        story.append(Paragraph(
            "No price changes were detected this month.",
            styles['SmallNote'],
        ))
    story.append(PageBreak())

    # ── UIFPI vs CPI ─────────────────────────────────────────────────────
    story.append(Paragraph("3. UIFPI vs official CPI", styles['SectionHeader']))
    rows = [['Country', 'Month', 'UIFPI', 'CPI', 'YoY %']]
    for r in uifpi_vs_cpi:
        rows.append([
            r['country'],
            r['month'] or '—',
            _fmt(r['uifpi']),
            _fmt(r['cpi']),
            _fmt(r['yoy_change_pct']),
        ])
    story.append(_table(rows, col_widths=[1.6*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch]))
    story.append(PageBreak())

    # ── Restaurants added/removed ────────────────────────────────────────
    story.append(Paragraph("4. Restaurants added or removed", styles['SectionHeader']))
    story.append(Paragraph(
        f"<b>{len(added)}</b> added · <b>{len(removed)}</b> removed "
        f"vs {_prev_month(month)}.",
        styles['BodyText'],
    ))
    story.append(Spacer(1, 0.1 * inch))
    if added:
        story.append(Paragraph("<b>Added:</b>", styles['BodyText']))
        for name in added[:60]:
            story.append(Paragraph(f"• {name}", styles['BodyText']))
        if len(added) > 60:
            story.append(Paragraph(f"… and {len(added) - 60} more",
                                   styles['SmallNote']))
        story.append(Spacer(1, 0.1 * inch))
    if removed:
        story.append(Paragraph("<b>Removed:</b>", styles['BodyText']))
        for name in removed[:60]:
            story.append(Paragraph(f"• {name}", styles['BodyText']))
        if len(removed) > 60:
            story.append(Paragraph(f"… and {len(removed) - 60} more",
                                   styles['SmallNote']))
    if not added and not removed:
        story.append(Paragraph("No additions or removals this month.",
                               styles['SmallNote']))
    story.append(PageBreak())

    # ── Granger p-value tracker ──────────────────────────────────────────
    story.append(Paragraph("5. Granger causality p-value tracker",
                           styles['SectionHeader']))
    rows = [['Country', 'p-value', 'Lead months', 'n obs', 'Significant', 'Status']]
    for r in granger:
        rows.append([
            r['country'],
            _fmt(r['p_value'], 4),
            str(r['lead_months'] if r['lead_months'] is not None else '—'),
            str(r['n_obs'] if r['n_obs'] is not None else '—'),
            'Yes' if r['significant'] else 'No',
            r['status'] or '—',
        ])
    story.append(_table(rows, col_widths=[1.4*inch, 0.8*inch, 0.9*inch,
                                          0.7*inch, 0.8*inch, 1.4*inch]))

    doc = SimpleDocTemplate(
        out_path,
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"UIFPI Monthly Report — {month}",
    )
    doc.build(story)


def main(argv):
    if len(argv) > 1:
        month = argv[1]
    else:
        today = date.today()
        month = f"{today.year}-{today.month:02d}"

    # basic sanity check
    try:
        year, mo = (int(p) for p in month.split('-'))
        assert 2000 <= year <= 2100 and 1 <= mo <= 12
    except Exception:
        print(f"Invalid month: {month} (expected YYYY-MM)")
        sys.exit(2)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, f"uifpi_report_{month}.pdf")
    build_report(month, out_path)
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main(sys.argv)
