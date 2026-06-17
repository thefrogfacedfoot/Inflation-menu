import { readFileSync } from "fs";
import { join } from "path";
import type {
  CountrySummaryMap,
  LatestValueMap,
  IndexSeriesMap,
  IndexPoint,
  CountrySummary,
  LatestValue,
  FloorData,
  FloorDataMap,
} from "@/types";

// Read JSON files directly from disk during build/SSR.
// Falls back to an empty object if the file is missing.
function readDataFile<T>(filename: string): T {
  try {
    const filePath = join(process.cwd(), "public", "data", filename);
    const raw = readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return {} as T;
  }
}

export async function getCountrySummaries(): Promise<CountrySummaryMap> {
  return readDataFile<CountrySummaryMap>("country_summary.json");
}

export async function getLatestValues(): Promise<LatestValueMap> {
  return readDataFile<LatestValueMap>("latest_values.json");
}

export async function getIndexSeries(): Promise<IndexSeriesMap> {
  return readDataFile<IndexSeriesMap>("index_series.json");
}

export async function getFloorData(): Promise<FloorDataMap> {
  return readDataFile<FloorDataMap>("floor_data.json");
}

export async function getFloorDataForCountry(
  country: string
): Promise<FloorData | null> {
  const all = await getFloorData();
  return all[country] ?? null;
}

export async function getCountryData(country: string): Promise<{
  summary: CountrySummary | null;
  latest: LatestValue | null;
  series: IndexPoint[];
}> {
  const [summaries, latestMap, seriesMap] = await Promise.all([
    getCountrySummaries(),
    getLatestValues(),
    getIndexSeries(),
  ]);
  return {
    summary: summaries[country] ?? null,
    latest: latestMap[country] ?? null,
    series: seriesMap[country] ?? [],
  };
}

// Convert series to CSV string
export function seriesToCsv(country: string, series: IndexPoint[]): string {
  const header = "month,uifpi,formal,informal,cpi,item_count\n";
  const rows = series
    .map(
      (d) =>
        `${d.month},${d.uifpi ?? ""},${d.formal ?? ""},${d.informal ?? ""},${d.cpi ?? ""},${d.item_count}`
    )
    .join("\n");
  return header + rows;
}
