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
  "United States",
  "United Kingdom",
  "Australia",
] as const;

export type Country = (typeof COUNTRIES)[number];

export const COUNTRY_FLAGS: Record<string, string> = {
  Singapore: "🇸🇬",
  Malaysia: "🇲🇾",
  Indonesia: "🇮🇩",
  Thailand: "🇹🇭",
  India: "🇮🇳",
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
  "United States": "united-states",
  "United Kingdom": "united-kingdom",
  Australia: "australia",
};

export const SLUG_TO_COUNTRY: Record<string, string> = Object.fromEntries(
  Object.entries(COUNTRY_SLUGS).map(([k, v]) => [v, k])
);

export const DEVELOPMENT_STATUS: Record<string, "Developed" | "Emerging"> = {
  Singapore: "Developed",
  Malaysia: "Emerging",
  Indonesia: "Emerging",
  Thailand: "Emerging",
  India: "Emerging",
  "United States": "Developed",
  "United Kingdom": "Developed",
  Australia: "Developed",
};
