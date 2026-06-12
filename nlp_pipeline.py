"""
UIFPI — NLP Pipeline
Classifies raw menu item names from uifpi.db into a standardised food
taxonomy and detects quality signals using Claude claude-sonnet-4-6.

Results are written to the nlp_results table and used by index_builder.py.
Run order: after live_scraper.py has populated the prices table.

Requires: ANTHROPIC_API_KEY in .env or environment variable.
"""

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import date

import anthropic
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "uifpi.db"
BATCH_SIZE = 50
MAX_RETRIES = 4
BASE_RETRY_WAIT = 3      # seconds; actual wait = BASE_RETRY_WAIT * 2**attempt

VALID_CATEGORIES = {
    "GRILLED_PROTEIN", "NOODLE_DISH", "RICE_DISH", "SOUP_STEW",
    "DIM_SUM_DUMPLING", "BREAD_PASTRY", "BEVERAGE", "DESSERT",
    "FAST_FOOD", "SEAFOOD_DISH", "SALAD_VEGETABLE", "SNACK_SIDE",
    "SET_MEAL", "OTHER",
}

VALID_SIGNALS = {
    "PORTION_REDUCTION", "PREMIUM_UPGRADE", "INGREDIENT_CHANGE", "SIZE_INCREASE",
}

SYSTEM_PROMPT = """You are a food taxonomy classifier for a restaurant price index research project.

Given a JSON object {"items": [...]} containing menu item names, classify every item.

Return ONLY a valid JSON array — no markdown fences, no preamble, no explanation.
Each element must contain exactly these keys:
  "item"              – the original item name, copied exactly as given
  "category"          – exactly one string from the list below
  "quality_signals"   – JSON array (may be []) with zero or more strings from the signals list
  "language_detected" – ISO 639-1 code: en, zh, ms, th, id, hi, ta, ja, ko, etc.
  "confidence"        – float 0.0–1.0

CATEGORY LIST (choose exactly one):
  GRILLED_PROTEIN   – grilled/roasted/smoked meat, fish, or poultry (steak, BBQ, tandoori, satay, yakitori)
  NOODLE_DISH       – any noodle-based dish (laksa, ramen, pho, pad thai, mee goreng, pasta, udon)
  RICE_DISH         – rice-based dishes (chicken rice, nasi lemak/goreng, biryani, congee, risotto)
  SOUP_STEW         – soups, broths, curries, stews (tom yum, bak kut teh, dhal, rendang, mulligatawny)
  DIM_SUM_DUMPLING  – dumplings, dim sum, bao (har gao, siu mai, xiao long bao, gyoza, momo, pierogi)
  BREAD_PASTRY      – bread, pastries, flatbreads (toast, croissant, roti canai, prata, naan, bun)
  BEVERAGE          – any drink (coffee, tea, juice, beer, bubble tea, milkshake, soft drink, water)
  DESSERT           – sweet items (ice cream, cake, cendol, waffle, pudding, mochi, tart)
  FAST_FOOD         – burgers, fries, pizza, fried chicken, hot dogs, nuggets, wraps
  SEAFOOD_DISH      – seafood-focused dishes (chilli crab, fish and chips, oyster, prawn, calamari)
  SALAD_VEGETABLE   – salads, vegetable sides, coleslaw, acar, kimchi
  SNACK_SIDE        – snacks, sides, appetisers (spring roll, samosa, popiah, chips, garlic bread)
  SET_MEAL          – combo meals, set menus, value meals, family sets, packages
  OTHER             – anything that genuinely does not fit any above category

QUALITY SIGNALS (include any that apply, or use []):
  PORTION_REDUCTION – mini, small, snack size, lite, half, reduced, less
  PREMIUM_UPGRADE   – premium, special, deluxe, signature, wagyu, truffle, aged, fresh
  INGREDIENT_CHANGE – new recipe, improved, real, classic, original, traditional, now with
  SIZE_INCREASE     – jumbo, large, big, super, XXL, double, extra"""


# ── Database helpers ──────────────────────────────────────────────────────────

def init_db(conn: sqlite3.Connection) -> None:
    """Create nlp_results table if it doesn't already exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nlp_results (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name        TEXT NOT NULL,
            restaurant_name  TEXT,
            country          TEXT,
            category         TEXT,
            quality_signals  TEXT,
            language_detected TEXT,
            confidence       REAL,
            processed_date   TEXT,
            UNIQUE(item_name)
        )
    """)
    conn.commit()


def get_unprocessed_items(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """
    Return (item_name, restaurant_name, country) for all unique item_names
    in the prices table that are not yet in nlp_results.
    One representative (restaurant_name, country) per unique item_name.
    """
    rows = conn.execute("""
        SELECT item_name, restaurant_name, country
        FROM prices
        WHERE item_name NOT IN (SELECT item_name FROM nlp_results)
        GROUP BY item_name
        ORDER BY item_name
    """).fetchall()
    return rows


def insert_result(conn: sqlite3.Connection, item_name: str, restaurant_name: str,
                  country: str, category: str, quality_signals: list,
                  language_detected: str, confidence: float) -> None:
    """Insert one classified item into nlp_results; silently skip on duplicate."""
    conn.execute("""
        INSERT OR IGNORE INTO nlp_results
            (item_name, restaurant_name, country, category, quality_signals,
             language_detected, confidence, processed_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_name, restaurant_name, country,
        category, json.dumps(quality_signals),
        language_detected, confidence,
        date.today().isoformat(),
    ))


# ── API helpers ───────────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Remove markdown code fences if the model accidentally wraps its output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()


def _validate_item(raw: dict, original: str) -> dict:
    """Normalise and validate a single classified item from the API response."""
    category = raw.get("category", "OTHER")
    if category not in VALID_CATEGORIES:
        category = "OTHER"

    signals = [s for s in raw.get("quality_signals", []) if s in VALID_SIGNALS]

    try:
        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "item": raw.get("item", original),
        "category": category,
        "quality_signals": signals,
        "language_detected": raw.get("language_detected", "en") or "en",
        "confidence": confidence,
    }


def classify_batch(client: anthropic.Anthropic, items: list[str]) -> list[dict]:
    """
    Send one batch of item names to Claude and return a list of classified dicts.
    Retries with exponential backoff on transient API errors.
    Returns an empty list for a batch that fails all retries.
    """
    user_content = json.dumps({"items": items})

    for attempt in range(MAX_RETRIES):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},   # cache across calls
                }],
                messages=[{"role": "user", "content": user_content}],
            )
            raw_text = _strip_markdown(message.content[0].text)
            parsed = json.loads(raw_text)

            if not isinstance(parsed, list):
                raise ValueError(f"Expected list, got {type(parsed).__name__}")

            # Build item → raw dict lookup (model may reorder)
            lookup = {r.get("item", ""): r for r in parsed if isinstance(r, dict)}

            results = []
            for original in items:
                raw = lookup.get(original) or lookup.get(original.strip()) or {}
                results.append(_validate_item(raw, original))
            return results

        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            wait = BASE_RETRY_WAIT * (2 ** attempt)
            print(f"    API error on attempt {attempt+1}/{MAX_RETRIES}: {e} — "
                  f"retrying in {wait}s")
            time.sleep(wait)

        except json.JSONDecodeError as e:
            wait = BASE_RETRY_WAIT * (2 ** attempt)
            print(f"    JSON parse error on attempt {attempt+1}/{MAX_RETRIES}: {e} — "
                  f"retrying in {wait}s")
            time.sleep(wait)

        except Exception as e:
            print(f"    Unexpected error on attempt {attempt+1}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES - 1:
                print(f"    Giving up on this batch.")
                return []
            time.sleep(BASE_RETRY_WAIT * (2 ** attempt))

    return []


# ── Summary printing ──────────────────────────────────────────────────────────

def print_summary(conn: sqlite3.Connection) -> None:
    """Print category breakdown, quality signal frequency, and language distribution."""
    print("\n" + "=" * 60)
    print("NLP Results Summary")
    print("=" * 60)

    total = conn.execute("SELECT COUNT(*) FROM nlp_results").fetchone()[0]
    print(f"\nTotal classified: {total:,}")

    print("\n── Categories ──────────────────────────────────────────")
    rows = conn.execute("""
        SELECT category, COUNT(*) AS n
        FROM nlp_results
        GROUP BY category ORDER BY n DESC
    """).fetchall()
    for cat, n in rows:
        bar = "█" * (n * 30 // max(r[1] for r in rows))
        print(f"  {cat:<22} {n:>5}  {bar}")

    print("\n── Quality signals ─────────────────────────────────────")
    signal_counter: Counter = Counter()
    for (qs_json,) in conn.execute("SELECT quality_signals FROM nlp_results"):
        try:
            signals = json.loads(qs_json or "[]")
            signal_counter.update(signals)
        except json.JSONDecodeError:
            pass
    if signal_counter:
        for sig, cnt in signal_counter.most_common():
            print(f"  {sig:<25} {cnt:>5}")
    else:
        print("  (none detected)")

    print("\n── Languages ───────────────────────────────────────────")
    rows = conn.execute("""
        SELECT language_detected, COUNT(*) AS n
        FROM nlp_results
        GROUP BY language_detected ORDER BY n DESC
    """).fetchall()
    for lang, n in rows:
        print(f"  {lang:<10} {n:>5}")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def run(db_path: str = DB_PATH) -> None:
    """Run the NLP pipeline: classify all unprocessed items and store results."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("✗  ANTHROPIC_API_KEY not found in environment or .env file.")
        print("   Create a .env file with: ANTHROPIC_API_KEY=sk-ant-...")
        return

    client = anthropic.Anthropic(api_key=api_key)

    conn = sqlite3.connect(db_path)
    init_db(conn)

    pending = get_unprocessed_items(conn)
    if not pending:
        print("No unprocessed items found — nlp_results is already up to date.")
        print_summary(conn)
        conn.close()
        return

    print(f"\nNLP Pipeline — classifying {len(pending):,} unique item names")
    print(f"Batch size: {BATCH_SIZE}  |  Model: claude-sonnet-4-6\n")

    # Split into batches of item_names; carry along restaurant+country for storage
    batches = []
    for i in range(0, len(pending), BATCH_SIZE):
        batches.append(pending[i : i + BATCH_SIZE])

    total_batches = len(batches)
    total_inserted = 0
    total_failed = 0

    for batch_idx, batch in enumerate(batches, 1):
        item_names = [row[0] for row in batch]
        meta = {row[0]: (row[1], row[2]) for row in batch}  # item_name → (rest, country)

        print(f"Processing batch {batch_idx}/{total_batches} "
              f"({len(item_names)} items)...", end=" ", flush=True)

        results = classify_batch(client, item_names)

        if not results:
            print(f"FAILED — skipping {len(item_names)} items")
            total_failed += len(item_names)
            continue

        inserted_in_batch = 0
        for res in results:
            iname = res["item"]
            rest_name, country = meta.get(iname, ("", ""))
            insert_result(
                conn, iname, rest_name, country,
                res["category"], res["quality_signals"],
                res["language_detected"], res["confidence"],
            )
            inserted_in_batch += 1

        conn.commit()
        total_inserted += inserted_in_batch
        print(f"✓  {inserted_in_batch} stored")

        # Polite pause between API calls (not needed for batch but avoids burst)
        if batch_idx < total_batches:
            time.sleep(0.5)

    conn.commit()

    print(f"\n── Run complete ────────────────────────────────────────")
    print(f"  Inserted: {total_inserted:,}")
    print(f"  Failed:   {total_failed:,}")

    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    run()
