"""
Data-quality quarantine list — (country, source) slices excluded from
index construction and dashboard aggregates.

Discovered 2026-07-09 while validating a baseline diff for the parked
fx-rates refactor: two wayback-archived slices carry systematically
corrupted prices (100% NULL price_usd; garbage raw values once backfilled
through FALLBACK_RATES). Root cause, evidence, and index-contamination
quantification are in docs/data_quality_2026-07.md. Raw rows are left
untouched in `prices` — this module only says "don't use these for
index/dashboard aggregation."

Slices:
  - United Arab Emirates / wayback-deliveroo: the AE Deliveroo archive's
    price field is a structured {"code","fractional","formatted"} object
    (not the plain typed `raw_price` the UK parser expects). The generic
    JSON-LD/NEXT_DATA walker (`_walk_ld` in historical_html_scraper.py)
    stringifies that dict and strips non-digit characters, which fuses
    the `fractional` minor-units figure with stray digits leaking out of
    the `formatted` string's non-breaking-space escape (`\\xa0` repr'd as
    literal backslash-x-a-0, contributing a spurious "0"). E.g. an actual
    AED 9 item ("Butter Roti") becomes 90009. 100% of AE wayback-deliveroo
    rows (9,243) are affected — every item on every page uses this price
    shape.
  - Vietnam / wayback-grabfood: GrabFood's `priceInMinorUnit` handling in
    `_walk_ld` (added 2026-06-18 for GrabFood MY/SG) unconditionally
    divides by 100 to convert minor units (cents) to major units. VND has
    no minor currency subunit in practice, so GrabFood VN's
    `priceInMinorUnit` already carries the raw VND amount — dividing by
    100 corrupts every price by ~2 orders of magnitude (an 18,000 VND
    coffee becomes 180.0; an unavailable placeholder item with
    priceInMinorUnit=17 becomes 0.17). All 4,309 VN wayback-grabfood rows
    are affected. Live `grabfood` VN rows use a different code path and
    are healthy.

Neither country is in the final 8-country panel (US, UK, Singapore,
Malaysia, India, Australia, Indonesia, Thailand), so quarantining these
slices costs nothing the paper depends on.
"""

QUARANTINED_SLICES = (
    # (country, source) — raw rows stay in `prices`; excluded from index
    # construction and dashboard aggregates. See docs/data_quality_2026-07.md.
    ("United Arab Emirates", "wayback-deliveroo"),
    ("Vietnam", "wayback-grabfood"),
)

# Grocery/convenience/general-retail chains that show up in wayback
# delivery-platform sweeps (Deliveroo UK in particular carries supermarket
# "dark stores" under the same /menu/ URL shape as restaurants). These are
# SKU-catalog dumps (thousands of items each — Sainsbury's/Morrisons/Co-op
# pages ran 4,000-17,000+ "items" in the 2026-08-02 UK sweep, dwarfing every
# real restaurant) with no place in a restaurant menu-price panel. Match
# against a lowercased restaurant name substring. Any script that builds a
# candidate list from a wayback delivery-platform pool (any country/source,
# not just UK Deliveroo) should filter through this before ranking/probing.
GROCERY_RETAIL_NAME_MARKERS = (
    # UK
    'sainsbury', 'morrison', 'tesco', 'asda', 'co-op', 'co op', 'waitrose',
    'wilko', 'iceland', 'aldi', 'lidl', 'spar', 'marks and spencer', 'm&s',
    'boots', 'superdrug', 'gopuff', 'poundland', 'wh smith', 'costcutter',
    'nisa', 'budgens', 'londis',
    # Malaysia — added 2026-08-03 for the GrabFood MY candidate build;
    # convenience-store / hypermarket chains carry the same SKU-dump-vs-
    # restaurant-menu problem as UK Deliveroo's supermarkets. NOTE: bare
    # 'aeon' was deliberately left out — the MY pool has AEON-mall-tenant
    # restaurants (e.g. "Auntie Anne's - AEON Bandaraya Melaka", "Eato
    # Enjoy Japanese Teppanyaki - AEON Food Market @ MidValley") that use
    # "AEON <mall>" as a location suffix, not the AEON hypermarket itself;
    # a bare substring match would have dropped real restaurant chains.
    '7-eleven', '7 eleven', 'kk mart', 'kk super mart', 'mynews',
    'speedmart', '99 speedmart', 'giant hypermarket', 'giant supermarket',
    'jaya grocer', 'village grocer', 'econsave', "lotus's", 'lotuss',
    'cold storage', 'hero market', 'family mart', 'familymart', 'emart24',
    # United States — added 2026-08-03 for the DoorDash US candidate build;
    # same rationale (drugstores/convenience/big-box carry thousands of
    # non-restaurant SKUs under the same store-page URL shape).
    'cvs', 'walgreens', 'walmart', 'target', 'costco', 'wawa', 'circle k',
    'dollar general', 'family dollar', 'rite aid', 'safeway', 'kroger',
    'publix', 'whole foods', "trader joe's", 'giant eagle', 'wegmans',
    'meijer', 'speedway', 'quiktrip', 'sheetz', "casey's general store",
)


def is_grocery_or_retail(name):
    n = name.lower()
    return any(m in n for m in GROCERY_RETAIL_NAME_MARKERS)
