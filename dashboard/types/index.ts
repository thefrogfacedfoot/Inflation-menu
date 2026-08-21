export interface IndexPoint {
  month: string;
  uifpi: number | null;
  formal: number | null;
  informal: number | null;
  cpi: number | null;
  item_count: number;
}

export interface CountrySummary {
  granger_significant: boolean | null;
  granger_p_value: number | null;
  lead_months: number | null;
  pass_through_formal: number | null;
  pass_through_informal: number | null;
  pass_through_significant: boolean | null;
  r_squared: number | null;
  n_obs: number | null;
  months_of_data: number;
  base_month: string | null;
  latest_uifpi: number | null;
  latest_cpi: number | null;
  status: string;
  items_formal: number;
  items_informal: number;
  restaurants_formal: number;
  restaurants_informal: number;
  avg_price_formal_usd: number | null;
  avg_price_informal_usd: number | null;
}

export interface LatestValue {
  month: string;
  uifpi: number | null;
  formal: number | null;
  informal: number | null;
  cpi: number | null;
  yoy_change_pct: number | null;
  items_formal: number;
  items_informal: number;
}

export type CountrySummaryMap = Record<string, CountrySummary>;
export type LatestValueMap = Record<string, LatestValue>;
export type IndexSeriesMap = Record<string, IndexPoint[]>;

export const COUNTRIES = [
  "Singapore",
  "Malaysia",
  "Indonesia",
  "Thailand",
  "India",
  "Vietnam",
  "United Arab Emirates",
  "United States",
  "United Kingdom",
  "Australia",
] as const;

// Countries whose archival sources have been exhausted but which have too
// little usable data for a Granger test. Still routable, just visually
// demoted on the homepage and excluded from the main grid.
export const LIMITED_COVERAGE = new Set<string>(["Indonesia", "Thailand"]);

// Countries whose entire Wayback price slice was found to be systematically
// mispriced and quarantined from the index on 2026-07-09 (paper §4.7). Not
// "collecting data" — the earlier Granger statistics for these two are
// withdrawn, not merely stale, and no re-scrape has happened yet. Still
// routable, but kept out of the primary grid so they aren't read as
// reporting countries on the same footing as the rest of the panel.
export const WITHDRAWN = new Set<string>(["Vietnam", "United Arab Emirates"]);

export const PRIMARY_COUNTRIES = COUNTRIES.filter(
  (c) => !LIMITED_COVERAGE.has(c) && !WITHDRAWN.has(c)
);
export const LIMITED_COVERAGE_COUNTRIES = COUNTRIES.filter((c) =>
  LIMITED_COVERAGE.has(c)
);
export const WITHDRAWN_COUNTRIES = COUNTRIES.filter((c) => WITHDRAWN.has(c));

export type Country = (typeof COUNTRIES)[number];

export const COUNTRY_FLAGS: Record<string, string> = {
  Singapore: "🇸🇬",
  Malaysia: "🇲🇾",
  Indonesia: "🇮🇩",
  Thailand: "🇹🇭",
  India: "🇮🇳",
  Vietnam: "🇻🇳",
  "United Arab Emirates": "🇦🇪",
  "United States": "🇺🇸",
  "United Kingdom": "🇬🇧",
  Australia: "🇦🇺",
};

export const COUNTRY_SLUGS: Record<string, string> = {
  Singapore: "singapore",
  Malaysia: "malaysia",
  Indonesia: "indonesia",
  Thailand: "thailand",
  India: "india",
  Vietnam: "vietnam",
  "United Arab Emirates": "united-arab-emirates",
  "United States": "united-states",
  "United Kingdom": "united-kingdom",
  Australia: "australia",
};

export const SLUG_TO_COUNTRY: Record<string, string> = Object.fromEntries(
  Object.entries(COUNTRY_SLUGS).map(([k, v]) => [v, k])
);

// Per-country coverage caveat shown under the chart. Keep terse — the
// methodology page carries the long form. Empty/absent ⇒ no banner.
export const COVERAGE_NOTES: Record<string, string> = {
  Thailand:
    "Single 2026-06 snapshot (11 items, 9 restaurants). Live collection going forward only — no archival depth.",
  Indonesia:
    "Restaurant-aggregate Zomato cost-for-two series (29 monthly observations from Jakarta). Treat each point as a typical-meal-for-two price, not item-level.",
  "United Kingdom":
    "18 months of UIFPI data collected. Granger testing requires n ≥ 24 — threshold expected Q4 2026 via monthly accumulation.",
  Vietnam:
    "Withdrawn 2026-07-09. The Wayback GrabFood slice (4,309 rows — all of Vietnam's archival data) was found to misparse VND's dot-grouped-thousands convention (\"45.000\" = 45,000, not 45.0), leaving every row with a null price. The Granger statistic reported in earlier drafts is not carried forward; no statistic is reported until a corrected re-scrape runs. See paper §4.7.",
  "United Arab Emirates":
    "Withdrawn 2026-07-09. The Wayback Deliveroo slice (9,243 rows — all of the UAE's archival data) was found to digit-fuse an object-valued price field from 2022-01 onward (AED 9 read as 90,009), leaving every row with a null price. The Granger statistic reported in earlier drafts (F = 0.016, p = 0.900) is withdrawn and not carried forward; no statistic is reported until a corrected re-scrape runs. See paper §4.7.",
};

export const DEVELOPMENT_STATUS: Record<string, "Developed" | "Emerging"> = {
  Singapore: "Developed",
  Malaysia: "Emerging",
  Indonesia: "Emerging",
  Thailand: "Emerging",
  India: "Emerging",
  Vietnam: "Emerging",
  "United Arab Emirates": "Developed",
  "United States": "Developed",
  "United Kingdom": "Developed",
  Australia: "Developed",
};

// CPI publication frequency / ingestion path per country. Drives the
// methodology marker shown on tiles and tables; full definitions live in
// paper §4.7. The Granger F-statistic is only interpretable against a
// `real-monthly` series; `quarterly-interp` is power-limited;
// `annual-interp` (linear) is inconclusive-due-to-power; `annual-step`
// (WB FP.CPI.TOTL replicated 12×) leaves the test structurally
// degenerate and uninformative.
export type CpiClass =
  | "real-monthly"
  | "quarterly-interp"
  | "annual-interp"
  | "annual-step";

export const CPI_CLASS: Record<string, CpiClass> = {
  "United States":  "real-monthly",
  "United Kingdom": "real-monthly",
  India:            "real-monthly",
  Malaysia:         "real-monthly",
  Australia:        "quarterly-interp",
  Singapore:        "annual-interp",
  Thailand:         "annual-interp",
  Indonesia:        "annual-interp",
  Vietnam:          "annual-step",
  "United Arab Emirates": "annual-step",
};

export const CPI_CLASS_LABEL: Record<CpiClass, string> = {
  "real-monthly":     "[real-monthly]",
  "quarterly-interp": "[quarterly-interp]",
  "annual-interp":    "[annual-interp]",
  "annual-step":      "[annual-step]",
};

export const CPI_CLASS_TOOLTIP: Record<CpiClass, string> = {
  "real-monthly":
    "CPI published monthly by the national statistics office. Granger test is interpretable on its own terms.",
  "quarterly-interp":
    "CPI published quarterly, linearly interpolated to monthly. Within-quarter variance compressed but nonzero.",
  "annual-interp":
    "World Bank annual CPI, linearly interpolated to monthly. Within-year variance compressed; Granger test is power-limited.",
  "annual-step":
    "World Bank annual CPI, step-replicated 12× per year. ΔCPI = 0 within each year — Granger test is structurally degenerate; null results are uninformative. See paper §4.7.",
};
