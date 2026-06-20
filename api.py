"""
UIFPI — Public read-only API

Exposes the cleaned UIFPI series, country summaries, raw prices, and
detected price changes over HTTP so the dashboard and external researchers
can query the data programmatically instead of reading static JSON files.

Endpoints:
    GET /api/countries              — list of countries + summary stats
    GET /api/index/<country>        — UIFPI time series for one country
    GET /api/prices/<country>       — raw prices (paginated)
    GET /api/latest                 — latest UIFPI per country
    GET /api/changes                — recent rows from price_history
    GET /api/health                 — liveness probe

Run with:
    python3 api.py

Then GET http://localhost:5000/api/countries
"""
import json
import os
import sqlite3

from flask import Flask, jsonify, request
from flask_cors import CORS


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'uifpi.db')
DASHBOARD_DIR = os.path.join(BASE_DIR, 'dashboard_data')


app = Flask(__name__)
CORS(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _db():
    """Open a row-friendly SQLite connection per request."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_json(name):
    path = os.path.join(DASHBOARD_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def _err(message, status=400):
    return jsonify({'error': message}), status


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'db_exists': os.path.exists(DB_PATH)})


@app.route('/api/countries')
def countries():
    """
    Return the canonical list of 8 countries with their summary stats
    (Granger p-value, latest UIFPI, item counts).
    """
    summary = _load_json('country_summary.json') or {}
    out = []
    for name, stats in sorted(summary.items()):
        entry = {'country': name}
        entry.update(stats)
        out.append(entry)
    if not out:
        # Fallback: derive from the prices table
        with _db() as conn:
            rows = conn.execute(
                'SELECT country, COUNT(*) AS n_items, '
                '       COUNT(DISTINCT restaurant_name) AS n_restaurants '
                'FROM prices GROUP BY country ORDER BY country'
            ).fetchall()
            out = [dict(r) for r in rows]
    return jsonify({'countries': out, 'count': len(out)})


@app.route('/api/index/<country>')
def index_series(country):
    """UIFPI monthly series for one country."""
    series_blob = _load_json('index_series.json') or {}
    # Try case-insensitive country lookup
    key = next((k for k in series_blob if k.lower() == country.lower()), None)
    if not key:
        return _err(f"No index series found for country: {country}", 404)
    return jsonify({
        'country': key,
        'series': series_blob[key],
        'points': len(series_blob[key]),
    })


@app.route('/api/prices/<country>')
def prices(country):
    """
    Paginated raw prices for one country.

    Query params:
        page      (default 1)
        per_page  (default 100, max 1000)
        sector    (optional: 'formal' | 'informal')
        start     (optional: YYYY-MM-DD lower bound on collection_date)
        end       (optional: YYYY-MM-DD upper bound)
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(1000, max(1, int(request.args.get('per_page', 100))))
    except ValueError:
        return _err('page and per_page must be integers')

    sector = request.args.get('sector')
    start = request.args.get('start')
    end = request.args.get('end')

    where = ['LOWER(country) = LOWER(?)']
    params = [country]
    if sector in ('formal', 'informal'):
        where.append('sector = ?')
        params.append(sector)
    if start:
        where.append('collection_date >= ?')
        params.append(start)
    if end:
        where.append('collection_date <= ?')
        params.append(end)
    where_sql = ' AND '.join(where)

    with _db() as conn:
        total = conn.execute(
            f'SELECT COUNT(*) FROM prices WHERE {where_sql}', params,
        ).fetchone()[0]
        rows = conn.execute(
            f'''SELECT restaurant_name, item_name, price, currency, price_usd,
                       country, sector, source, collection_date, url
                FROM prices
                WHERE {where_sql}
                ORDER BY collection_date DESC, restaurant_name, item_name
                LIMIT ? OFFSET ?''',
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

    return jsonify({
        'country': country,
        'page': page,
        'per_page': per_page,
        'total': total,
        'returned': len(rows),
        'prices': [dict(r) for r in rows],
    })


@app.route('/api/latest')
def latest():
    """Latest UIFPI value for each country (from the static dashboard file)."""
    blob = _load_json('latest_values.json')
    if blob is None:
        return _err('latest_values.json not found — run dashboard_data.py first', 503)
    return jsonify(blob)


@app.route('/api/changes')
def changes():
    """
    Recent rows from price_history.

    Query params:
        limit     (default 100, max 1000)
        country   (optional)
        min_pct   (optional: only changes with |pct| >= min_pct)
    """
    try:
        limit = min(1000, max(1, int(request.args.get('limit', 100))))
    except ValueError:
        return _err('limit must be an integer')

    country = request.args.get('country')
    min_pct = request.args.get('min_pct')

    where = ['1=1']
    params = []
    if country:
        where.append('LOWER(country) = LOWER(?)')
        params.append(country)
    if min_pct:
        try:
            mp = float(min_pct)
        except ValueError:
            return _err('min_pct must be numeric')
        where.append('ABS(price_change_pct) >= ?')
        params.append(mp)
    where_sql = ' AND '.join(where)

    with _db() as conn:
        # Guard against the table not yet existing on older DBs
        has_table = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='price_history'"
        ).fetchone()
        if not has_table:
            return jsonify({'changes': [], 'returned': 0,
                            'note': 'price_history table not initialised yet'})
        rows = conn.execute(
            f'''SELECT restaurant_name, item_name, old_price, new_price,
                       price_change_pct, country, sector, change_detected_date
                FROM price_history
                WHERE {where_sql}
                ORDER BY change_detected_date DESC, ABS(price_change_pct) DESC
                LIMIT ?''',
            params + [limit],
        ).fetchall()

    return jsonify({
        'changes': [dict(r) for r in rows],
        'returned': len(rows),
    })


@app.route('/')
def root():
    return jsonify({
        'name': 'UIFPI API',
        'endpoints': [
            '/api/countries',
            '/api/index/<country>',
            '/api/prices/<country>',
            '/api/latest',
            '/api/changes',
            '/api/health',
        ],
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT_API', 5000)),
            debug=False)
