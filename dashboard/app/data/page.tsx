import type { Metadata } from "next";
import Link from "next/link";
import { getCountrySummaries, getIndexSeries, seriesToCsv } from "@/lib/data";
import {
  COUNTRIES,
  COUNTRY_FLAGS,
  COUNTRY_SLUGS,
  DEVELOPMENT_STATUS,
} from "@/types";

export const metadata: Metadata = {
  title: "Data Download — UIFPI",
  description:
    "Download UIFPI price index data for all 8 countries as CSV files.",
};

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

export default async function DataPage() {
  const [summaries, seriesMap] = await Promise.all([
    getCountrySummaries(),
    getIndexSeries(),
  ]);

  const totalItems = COUNTRIES.reduce(
    (acc, c) =>
      acc +
      (summaries[c]?.items_formal ?? 0) +
      (summaries[c]?.items_informal ?? 0),
    0
  );

  // Build per-country CSV data URLs
  const csvByCountry = COUNTRIES.reduce(
    (acc, country) => {
      const csv = seriesToCsv(country, seriesMap[country] ?? []);
      acc[country] = `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
      return acc;
    },
    {} as Record<string, string>
  );

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-8">
        <nav className="text-sm text-gray-500 mb-4">
          <Link href="/" className="hover:text-gray-700">
            Dashboard
          </Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">Data Download</span>
        </nav>
        <h1 className="text-3xl font-bold text-gray-900">Data Download</h1>
        <p className="text-gray-600 mt-2">
          Download UIFPI index series and raw price data for all 8 countries.
          All data is open source under MIT license.
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Countries", value: "8" },
          {
            label: "Price Observations",
            value: totalItems.toLocaleString(),
          },
          { label: "Period", value: "2018–2026" },
          { label: "License", value: "MIT" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-center"
          >
            <p className="text-xl font-bold text-[#1a365d]">{s.value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Country table */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">
            Per-Country Index Data
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Monthly UICPI, chain, independent sub-indices, and official CPI
            where available
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                <th className="px-4 py-3">Country</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Chain Items</th>
                <th className="px-4 py-3 text-right">Independent Items</th>
                <th className="px-4 py-3 text-right">Months</th>
                <th className="px-4 py-3 text-right">From</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {COUNTRIES.map((country) => {
                const s = summaries[country];
                const series = seriesMap[country] ?? [];
                const csvHref = csvByCountry[country];
                const filename = `uifpi_${country
                  .toLowerCase()
                  .replace(/\s+/g, "_")}.csv`;
                const devStatus = DEVELOPMENT_STATUS[country];

                return (
                  <tr
                    key={country}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">
                          {COUNTRY_FLAGS[country]}
                        </span>
                        <div>
                          <Link
                            href={`/${COUNTRY_SLUGS[country]}`}
                            className="font-medium text-gray-900 hover:text-[#1a365d] transition-colors"
                          >
                            {country}
                          </Link>
                          <p
                            className={`text-xs ${
                              devStatus === "Developed"
                                ? "text-blue-600"
                                : "text-amber-600"
                            }`}
                          >
                            {devStatus}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {s?.granger_significant ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-800 font-medium">
                          ✓ Granger sig.
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600 font-medium">
                          Collecting
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-700">
                      {(s?.items_formal ?? 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-700">
                      {(s?.items_informal ?? 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-700">
                      {s?.months_of_data ?? 0}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-500 text-xs">
                      {s?.base_month ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={csvHref}
                        download={filename}
                        className="inline-flex items-center gap-1 text-xs font-medium text-[#1a365d] hover:text-blue-800 border border-[#1a365d] rounded px-2.5 py-1 hover:bg-blue-50 transition-colors"
                      >
                        ↓ CSV
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="bg-gray-50 border-t-2 border-gray-200">
                <td
                  colSpan={2}
                  className="px-4 py-3 font-semibold text-gray-700"
                >
                  Total
                </td>
                <td className="px-4 py-3 text-right font-semibold font-mono text-gray-900">
                  {COUNTRIES.reduce(
                    (acc, c) => acc + (summaries[c]?.items_formal ?? 0),
                    0
                  ).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right font-semibold font-mono text-gray-900">
                  {COUNTRIES.reduce(
                    (acc, c) => acc + (summaries[c]?.items_informal ?? 0),
                    0
                  ).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right font-semibold font-mono text-gray-900">
                  {COUNTRIES.reduce(
                    (acc, c) => acc + (summaries[c]?.months_of_data ?? 0),
                    0
                  )}
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* CSV format docs */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-8">
        <h2 className="font-semibold text-gray-900 mb-3">CSV Format</h2>
        <p className="text-sm text-gray-600 mb-3">
          Each country CSV contains the following columns (CSV/JSON column
          names retain the legacy <code className="font-mono">formal</code> /
          <code className="font-mono"> informal</code> field identifiers; UI
          labels them Chain / Independent):
        </p>
        <div className="bg-gray-50 rounded-lg p-3 font-mono text-xs text-gray-700 mb-3">
          month,uifpi,formal,informal,cpi,item_count
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
          {[
            ["month", "YYYY-MM period"],
            ["uifpi", "Combined UICPI index (base = 100)"],
            ["formal", "Chain sub-index"],
            ["informal", "Independent sub-index"],
            ["cpi", "Official CPI index (where available)"],
            ["item_count", "Number of price items in that month"],
          ].map(([col, desc]) => (
            <div key={col} className="flex gap-2">
              <dt className="font-mono text-[#1a365d] font-medium shrink-0">
                {col}
              </dt>
              <dd className="text-gray-600">{desc}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Citation */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-8">
        <h2 className="font-semibold text-gray-900 mb-3">How to Cite</h2>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-xs text-gray-700 leading-relaxed">
          Chen, E. (2026). UICPI: A Unified Independent-Chain Restaurant Price
          Index as a Leading Indicator of Consumer Price Inflation. Singapore
          Science and Engineering Fair Research Paper. Available at:
          github.com/thefrogfacedfoot/Inflation-menu
        </div>
        <p className="text-xs text-gray-500 mt-2">
          SSRN preprint forthcoming. Please cite the GitHub repository until
          the preprint is available.
        </p>
      </div>

      {/* Full dataset link */}
      <div className="rounded-xl bg-[#1a365d] text-white p-6">
        <h2 className="font-semibold mb-2">Full Dataset</h2>
        <p className="text-blue-200 text-sm mb-4">
          The complete dataset including raw price observations, NLP
          classification results, and analysis scripts is available on GitHub.
        </p>
        <a
          href="https://github.com/thefrogfacedfoot/Inflation-menu"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 bg-white text-[#1a365d] font-semibold px-5 py-2.5 rounded-lg hover:bg-blue-50 transition-colors text-sm"
        >
          View on GitHub →
        </a>
      </div>
    </div>
  );
}
