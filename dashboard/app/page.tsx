import Link from "next/link";
import { getCountrySummaries, getLatestValues } from "@/lib/data";
import CountryMap from "@/components/CountryMap";
import {
  COUNTRIES,
  COUNTRY_FLAGS,
  COUNTRY_SLUGS,
  DEVELOPMENT_STATUS,
} from "@/types";
import type { CountrySummaryMap, LatestValueMap } from "@/types";

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

function StatusBadge({ significant }: { significant: boolean }) {
  return significant ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
      Granger Significant
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
      Collecting Data
    </span>
  );
}

function CountryCard({
  country,
  summaries,
  latest,
}: {
  country: string;
  summaries: CountrySummaryMap;
  latest: LatestValueMap;
}) {
  const s = summaries[country];
  const lv = latest[country];
  const slug = COUNTRY_SLUGS[country];
  const devStatus = DEVELOPMENT_STATUS[country];
  const totalItems = (s?.items_formal ?? 0) + (s?.items_informal ?? 0);

  return (
    <Link
      href={`/${slug}`}
      className="block rounded-xl border border-gray-200 bg-white p-5 hover:border-blue-300 hover:shadow-md transition-all duration-200 group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl leading-none">{COUNTRY_FLAGS[country]}</span>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-[#1a365d] transition-colors text-sm leading-tight">
              {country}
            </h3>
            <span
              className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                devStatus === "Developed"
                  ? "bg-blue-50 text-blue-700"
                  : "bg-amber-50 text-amber-700"
              }`}
            >
              {devStatus}
            </span>
          </div>
        </div>
        <StatusBadge significant={s?.granger_significant ?? false} />
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="bg-gray-50 rounded-lg p-2.5">
          <p className="text-xs text-gray-500 mb-0.5">UIFPI Index</p>
          <p className="font-bold text-gray-900 text-xl">
            {fmt(lv?.uifpi ?? s?.latest_uifpi)}
          </p>
          <p className="text-xs text-gray-400">Base = 100</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2.5">
          <p className="text-xs text-gray-500 mb-0.5">Official CPI</p>
          {lv?.cpi != null ? (
            <>
              <p className="font-bold text-gray-900 text-xl">{fmt(lv.cpi)}</p>
              <p className="text-xs text-gray-400">Index level</p>
            </>
          ) : (
            <>
              <p className="font-bold text-gray-400 text-sm mt-1">No data</p>
              <p className="text-xs text-gray-400">Pending</p>
            </>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>
          {s?.lead_months != null
            ? `Leads CPI by ${s.lead_months} month${s.lead_months !== 1 ? "s" : ""}`
            : `${s?.months_of_data ?? 0} months collected`}
        </span>
        <span className="text-gray-400">{totalItems} items →</span>
      </div>
    </Link>
  );
}

export default async function HomePage() {
  const [summaries, latest] = await Promise.all([
    getCountrySummaries(),
    getLatestValues(),
  ]);

  const sigCount = COUNTRIES.filter(
    (c) => summaries[c]?.granger_significant
  ).length;
  const totalItems = COUNTRIES.reduce(
    (acc, c) =>
      acc +
      (summaries[c]?.items_formal ?? 0) +
      (summaries[c]?.items_informal ?? 0),
    0
  );
  const totalMonths = COUNTRIES.reduce(
    (acc, c) => acc + (summaries[c]?.months_of_data ?? 0),
    0
  );

  return (
    <div>
      {/* Hero */}
      <section className="bg-[#1a365d] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-blue-200 text-sm font-medium mb-5">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              Open source research — SSEF 2026
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4 leading-tight">
              UIFPI
              <span className="block text-blue-300 text-2xl sm:text-3xl font-normal mt-1">
                Unified Informal-Formal Price Index
              </span>
            </h1>
            <p className="text-lg text-blue-100 leading-relaxed max-w-2xl">
              A real-time restaurant price index extending the{" "}
              <span className="text-white font-medium">
                MIT Billion Prices Project
              </span>{" "}
              to formal restaurants and informal hawker stalls across 8
              countries. Tests whether food service prices lead official CPI as
              an early inflation signal.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/methodology"
                className="inline-flex items-center gap-2 bg-white text-[#1a365d] font-semibold px-5 py-2.5 rounded-lg hover:bg-blue-50 transition-colors"
              >
                Methodology
              </Link>
              <Link
                href="/data"
                className="inline-flex items-center gap-2 border border-white/40 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-white/10 transition-colors"
              >
                Download Data
              </Link>
              <a
                href="https://github.com/thefrogfacedfoot/Inflation-menu"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 border border-white/40 text-white font-medium px-5 py-2.5 rounded-lg hover:bg-white/10 transition-colors"
              >
                GitHub →
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-b border-gray-200 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
            {[
              { label: "Countries", value: "8" },
              {
                label: "Price Observations",
                value: totalItems.toLocaleString(),
              },
              { label: "Index-Months", value: totalMonths.toString() },
              { label: "Granger Significant", value: `${sigCount} / 8` },
            ].map((stat) => (
              <div key={stat.label}>
                <p className="text-2xl font-bold text-[#1a365d]">
                  {stat.value}
                </p>
                <p className="text-sm text-gray-500 mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Country cards */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">
            Country Dashboard
          </h2>
          <span className="text-sm text-gray-500">
            Click any country for full chart
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {COUNTRIES.map((country) => (
            <CountryCard
              key={country}
              country={country}
              summaries={summaries}
              latest={latest}
            />
          ))}
        </div>
      </section>

      {/* Map */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Country Coverage
          </h2>
          <CountryMap summaries={summaries} />
        </div>
      </section>

      {/* About */}
      <section className="bg-gray-50 border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid sm:grid-cols-3 gap-8">
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">
                What is UIFPI?
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                The Unified Informal-Formal Price Index tracks restaurant menu
                prices across formal restaurants and informal hawker stalls /
                street vendors in 8 countries, testing whether they lead
                official CPI readings.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">
                Why it matters
              </h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                In developing economies, street food represents 40–65% of
                household food expenditure but is entirely absent from all
                existing alternative price indices, including the MIT Billion
                Prices Project.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">Data status</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                Collection began 2018. Full monthly time-series pending —
                current dataset has {totalItems.toLocaleString()} price
                observations. Granger causality testing requires ≥24 monthly
                observations per country.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
