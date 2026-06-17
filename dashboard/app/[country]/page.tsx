import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { getCountryData, getIndexSeries, seriesToCsv } from "@/lib/data";
import IndexChart from "@/components/IndexChart";
import StatCard from "@/components/StatCard";
import {
  SLUG_TO_COUNTRY,
  COUNTRY_FLAGS,
  COUNTRY_SLUGS,
  COVERAGE_NOTES,
  DEVELOPMENT_STATUS,
  COUNTRIES,
} from "@/types";
import type { Metadata } from "next";

interface PageProps {
  params: Promise<{ country: string }>;
}

export async function generateStaticParams() {
  return Object.values(COUNTRY_SLUGS).map((slug) => ({ country: slug }));
}

/**
 * Resolve a raw URL segment to a canonical lowercase slug + country name.
 * Accepts: "singapore", "Singapore", "SINGAPORE", "Singapore%20", "united_states",
 * "United%20States", "united-states", etc.
 * Returns null if the segment cannot be matched.
 */
function resolveSlug(raw: string): { slug: string; country: string } | null {
  const decoded = (() => {
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  })();
  const normalized = decoded
    .toLowerCase()
    .trim()
    .replace(/[_\s]+/g, "-");
  const country = SLUG_TO_COUNTRY[normalized];
  if (!country) return null;
  return { slug: normalized, country };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { country: raw } = await params;
  const resolved = resolveSlug(raw);
  if (!resolved) return { title: "Country not found" };
  return {
    title: `${resolved.country} — UIFPI`,
    description: `UIFPI price index and CPI comparison for ${resolved.country}.`,
  };
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

function DownloadButton({ country, csvData }: { country: string; csvData: string }) {
  const blob = `data:text/csv;charset=utf-8,${encodeURIComponent(csvData)}`;
  const filename = `uifpi_${country.toLowerCase().replace(/\s+/g, "_")}.csv`;
  return (
    <a
      href={blob}
      download={filename}
      className="inline-flex items-center gap-2 bg-[#1a365d] text-white font-medium px-4 py-2 rounded-lg hover:bg-[#2a4a7f] transition-colors text-sm"
    >
      ↓ Download CSV
    </a>
  );
}

export default async function CountryPage({ params }: PageProps) {
  const { country: raw } = await params;
  const resolved = resolveSlug(raw);

  if (!resolved) {
    notFound();
  }

  // Canonicalise: if the URL segment differs from the canonical lowercase
  // slug (e.g. "Singapore", "United%20States"), 308-redirect so search
  // engines and shared links converge on one URL per country.
  if (raw !== resolved.slug) {
    permanentRedirect(`/${resolved.slug}`);
  }

  const countryName = resolved.country;

  const { summary, latest, series } = await getCountryData(countryName);
  const csvData = seriesToCsv(countryName, series);
  const devStatus = DEVELOPMENT_STATUS[countryName];
  const totalItems = (summary?.items_formal ?? 0) + (summary?.items_informal ?? 0);
  const hasCpi = series.some((d) => d.cpi != null);

  const prevCountryIdx =
    (COUNTRIES.indexOf(countryName as (typeof COUNTRIES)[number]) - 1 + COUNTRIES.length) %
    COUNTRIES.length;
  const nextCountryIdx =
    (COUNTRIES.indexOf(countryName as (typeof COUNTRIES)[number]) + 1) % COUNTRIES.length;
  const prevCountry = COUNTRIES[prevCountryIdx];
  const nextCountry = COUNTRIES[nextCountryIdx];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/" className="hover:text-gray-700 transition-colors">
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">{countryName}</span>
      </nav>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{COUNTRY_FLAGS[countryName]}</span>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              {countryName}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${
                  devStatus === "Developed"
                    ? "bg-blue-50 text-blue-700"
                    : "bg-amber-50 text-amber-700"
                }`}
              >
                {devStatus}
              </span>
              {summary?.granger_significant ? (
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  Granger Significant
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                  Data Collection Ongoing
                </span>
              )}
            </div>
          </div>
        </div>
        <DownloadButton country={countryName} csvData={csvData} />
      </div>

      {/* Chart */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">
            UIFPI vs Official CPI — {countryName}
          </h2>
          {!hasCpi && (
            <span className="text-xs text-gray-400 bg-gray-50 px-2 py-1 rounded">
              Official CPI data not yet available for this country
            </span>
          )}
        </div>
        <IndexChart
          data={series}
          country={countryName}
          showFormal
          showInformal
          showCpi={hasCpi}
          height={380}
        />
        {series.length === 0 && (
          <p className="text-sm text-gray-500 mt-3 text-center">
            Index data not yet available — price collection is ongoing.
          </p>
        )}
        {COVERAGE_NOTES[countryName] && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 mt-3 leading-relaxed">
            <span className="font-semibold">Coverage note:</span>{" "}
            {COVERAGE_NOTES[countryName]}
          </p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        <StatCard
          label="Lead Time"
          value={summary?.lead_months != null ? summary.lead_months : null}
          unit={summary?.lead_months != null ? "months" : undefined}
          sub="Ahead of official CPI"
          highlight={summary?.lead_months != null}
        />
        <StatCard
          label="Formal Pass-Through"
          value={
            summary?.pass_through_formal != null
              ? fmt(summary.pass_through_formal)
              : null
          }
          unit={summary?.pass_through_formal != null ? "β" : undefined}
          sub="Cost transmission rate"
        />
        <StatCard
          label="Informal Pass-Through"
          value={
            summary?.pass_through_informal != null
              ? fmt(summary.pass_through_informal)
              : null
          }
          unit={summary?.pass_through_informal != null ? "β" : undefined}
          sub="Cost transmission rate"
        />
        <StatCard
          label="Price Observations"
          value={totalItems.toLocaleString()}
          sub={`${summary?.items_formal ?? 0} formal / ${summary?.items_informal ?? 0} informal`}
        />
        <StatCard
          label="Months Indexed"
          value={summary?.months_of_data ?? 0}
          sub={`Since ${summary?.base_month ?? "2018"}`}
        />
      </div>

      {/* Coverage details */}
      <div className="grid sm:grid-cols-2 gap-6 mb-8">
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Formal Sector</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Restaurants</dt>
              <dd className="font-medium text-gray-900">
                {summary?.restaurants_formal ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Price items</dt>
              <dd className="font-medium text-gray-900">
                {summary?.items_formal ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Avg. price (USD)</dt>
              <dd className="font-medium text-gray-900">
                {summary?.avg_price_formal_usd != null
                  ? `$${summary.avg_price_formal_usd.toFixed(2)}`
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="font-semibold text-gray-900 mb-3">
            Informal Sector
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Hawker stalls / vendors</dt>
              <dd className="font-medium text-gray-900">
                {summary?.restaurants_informal ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Price items</dt>
              <dd className="font-medium text-gray-900">
                {summary?.items_informal ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Avg. price (USD)</dt>
              <dd className="font-medium text-gray-900">
                {summary?.avg_price_informal_usd != null
                  ? `$${summary.avg_price_informal_usd.toFixed(2)}`
                  : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Data status notice */}
      {!summary?.granger_significant && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 mb-8 text-sm text-amber-800">
          <strong>Data Collection Ongoing:</strong> Full Granger causality
          testing requires ≥24 monthly observations. Current dataset has{" "}
          {summary?.months_of_data ?? 0} months. Results will update
          automatically as more data is collected.
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t border-gray-200">
        <Link
          href={`/${COUNTRY_SLUGS[prevCountry]}`}
          className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-[#1a365d] transition-colors"
        >
          ← {COUNTRY_FLAGS[prevCountry]} {prevCountry}
        </Link>
        <Link
          href="/"
          className="text-sm font-medium text-gray-500 hover:text-[#1a365d] transition-colors"
        >
          All Countries
        </Link>
        <Link
          href={`/${COUNTRY_SLUGS[nextCountry]}`}
          className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-[#1a365d] transition-colors"
        >
          {COUNTRY_FLAGS[nextCountry]} {nextCountry} →
        </Link>
      </div>
    </div>
  );
}
