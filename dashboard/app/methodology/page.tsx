import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Methodology — UIFPI",
  description:
    "How the Unified Informal-Formal Price Index is constructed: data collection, index methodology, and statistical analysis.",
};

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
        {title}
      </h2>
      <div className="space-y-3 text-gray-700 leading-relaxed">{children}</div>
    </section>
  );
}

const COMPARISON_DATA = [
  {
    feature: "Scope",
    bigMac: "Single item (Big Mac)",
    bpp: "Online retail goods",
    uifpi: "Restaurant menus + hawker stalls",
  },
  {
    feature: "Sector coverage",
    bigMac: "Formal only (McDonald's)",
    bpp: "Formal only (e-commerce)",
    uifpi: "Formal + Informal",
  },
  {
    feature: "Service sector",
    bigMac: "No",
    bpp: "No",
    uifpi: "Yes",
  },
  {
    feature: "Informal economy",
    bigMac: "No",
    bpp: "No",
    uifpi: "Yes",
  },
  {
    feature: "Collection method",
    bigMac: "Manual annual survey",
    bpp: "Automated web scraping",
    uifpi: "Automated web scraping + archives",
  },
  {
    feature: "Countries (developing)",
    bigMac: "Limited",
    bpp: "Mostly developed",
    uifpi: "8 incl. 4 emerging",
  },
  {
    feature: "Update frequency",
    bigMac: "Annual",
    bpp: "Daily",
    uifpi: "Monthly (in progress)",
  },
  {
    feature: "Lead indicator test",
    bigMac: "No",
    bpp: "Yes (formal sector)",
    uifpi: "Yes (formal + informal)",
  },
];

export default function MethodologyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-10">
        <nav className="text-sm text-gray-500 mb-4">
          <Link href="/" className="hover:text-gray-700">Dashboard</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">Methodology</span>
        </nav>
        <h1 className="text-3xl font-bold text-gray-900">Methodology</h1>
        <p className="text-gray-600 mt-2">
          How UIFPI collects data, constructs the index, and tests for Granger
          causality against official CPI.
        </p>
      </div>

      {/* TOC */}
      <nav className="rounded-lg bg-gray-50 border border-gray-200 p-4 mb-10 text-sm">
        <p className="font-semibold text-gray-700 mb-2">Contents</p>
        <ol className="space-y-1 text-gray-600 list-decimal list-inside">
          {[
            ["#data-collection", "Data Collection"],
            ["#sector-definitions", "Formal vs Informal Sector"],
            ["#index-construction", "Index Construction"],
            ["#matched-model", "Matched-Model Approach"],
            ["#granger", "Granger Causality Testing"],
            ["#pass-through", "Pass-Through Regression"],
            ["#comparison", "Comparison: UIFPI vs Big Mac vs BPP"],
          ].map(([href, label]) => (
            <li key={href}>
              <a href={href} className="hover:text-[#1a365d] hover:underline">
                {label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-10">
        <Section id="data-collection" title="1. Data Collection">
          <p>
            UIFPI collects restaurant menu prices from two sources: (1){" "}
            <strong>live scraping</strong> of food delivery and restaurant
            aggregator platforms (Zomato, GrabFood, GoFood, Deliveroo, JustEat,
            Uber Eats, Yelp) and (2){" "}
            <strong>historical archive</strong> reconstruction via the Wayback
            Machine to extend series back to 2018.
          </p>
          <p>
            Item names are classified into food categories (RICE_DISH,
            NOODLE_DISH, SOUP_STEW, BREAD_PASTRY, etc.) using an NLP pipeline
            combining keyword matching and language detection across English,
            Malay, Indonesian, Thai, and Hindi.
          </p>
          <p>
            All prices are converted to USD at collection-date exchange rates
            to enable cross-country comparison.
          </p>
        </Section>

        <Section id="sector-definitions" title="2. Formal vs Informal Sector">
          <p>
            <strong>Formal sector</strong> restaurants are defined as
            registered businesses listed on major food delivery platforms with
            consistent branding and menu structure: sit-down restaurants, fast
            food chains, and café chains.
          </p>
          <p>
            <strong>Informal sector</strong> vendors are defined as unbranded
            or lightly branded single-stall operations typically associated
            with street food culture: hawker stalls (Singapore/Malaysia),
            warung (Indonesia), food courts, roadside vendors. These are
            identified by low price points, absence of a formal business name,
            and listing in hawker-specific sections of aggregator platforms.
          </p>
          <p>
            In economies such as Indonesia, India, and Thailand, the informal
            food sector represents 40–65% of household food expenditure
            (UNDP data) yet remains entirely absent from all existing
            alternative price indices.
          </p>
        </Section>

        <Section id="index-construction" title="3. Index Construction">
          <p>
            The UIFPI follows a Laspeyres-type chain-linked index. For each
            country and month:
          </p>
          <ol className="list-decimal list-inside space-y-2 ml-4">
            <li>
              Item-level price relatives are computed: p<sub>t</sub> / p
              <sub>0</sub> where p<sub>0</sub> is the base period price.
            </li>
            <li>
              Relatives are averaged within food categories
              (RICE_DISH, NOODLE_DISH, etc.) weighted by item count.
            </li>
            <li>
              Category relatives are aggregated to sector-level sub-indices
              (formal, informal).
            </li>
            <li>
              The combined UIFPI is a weighted average of formal and informal
              sub-indices (default weights: 50/50, robustness-tested at ±10pp).
            </li>
          </ol>
          <p>
            All indices are normalised to 100 at the base month. Where
            matched-model overlap is insufficient, a mean-price fallback method
            is used (flagged in the coverage_note field).
          </p>
        </Section>

        <Section id="matched-model" title="4. Matched-Model Approach">
          <p>
            Following Cavallo &amp; Rigobon (2016), UIFPI attempts to track
            identical or closely matched items across time periods. A{" "}
            <em>matched pair</em> exists when the same restaurant and item name
            appears in both the current and base period.
          </p>
          <p>
            When matched-model overlap is below a minimum threshold (currently
            2 items), the index falls back to average price relatives computed
            from all available items in that category and month. This fallback
            is transparent — all index observations carry a coverage_note
            field indicating the method used.
          </p>
          <p>
            Singapore, which has the largest dataset (6,527 price
            observations), has the highest matched-model coverage; other
            countries currently rely primarily on the mean-price fallback
            pending additional data collection.
          </p>
        </Section>

        <Section id="granger" title="5. Granger Causality Testing">
          <p>
            To test whether UIFPI leads official CPI, we apply the{" "}
            <strong>Granger causality test</strong> following Cavallo &amp;
            Rigobon (2016, <em>Review of Economics and Statistics</em>):
          </p>
          <ol className="list-decimal list-inside space-y-2 ml-4">
            <li>
              Both UIFPI and CPI series are first-differenced to achieve
              stationarity (verified by ADF test).
            </li>
            <li>
              Lag order is selected by AIC (max 6 lags for monthly data, 3 for
              annual).
            </li>
            <li>
              F-test of joint significance of lagged ΔUIFPI terms in the ΔCPI
              equation. A significant result (p &lt; 0.10) indicates UIFPI
              Granger-causes CPI.
            </li>
            <li>
              The lag at which the F-statistic is maximised is reported as the
              estimated lead time in months.
            </li>
          </ol>
          <p>
            <strong>Data requirement:</strong> ≥24 monthly observations per
            country. Current dataset has 10–15 observations per country —
            full testing will be enabled once monthly collection is complete.
          </p>
        </Section>

        <Section id="pass-through" title="6. Pass-Through Regression">
          <p>
            To test the hypothesis that informal vendors exhibit lower cost
            pass-through than formal restaurants, we estimate:
          </p>
          <p className="font-mono text-sm bg-gray-50 border border-gray-200 rounded p-3">
            Δln P<sup>sector</sup>
            <sub>t</sub> = α + β × Δln CPI<sub>t</sub> + ε<sub>t</sub>
          </p>
          <p>
            A coefficient β = 1 indicates full pass-through (prices move
            one-for-one with official CPI). β &lt; 1 indicates partial
            absorption. The hypothesis predicts β<sub>informal</sub> &lt; β
            <sub>formal</sub> — informal vendors absorb more of any input
            cost increase rather than passing it to consumers.
          </p>
        </Section>

        <Section id="comparison" title="7. Comparison vs Big Mac Index and BPP">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-[#1a365d] text-white">
                  <th className="text-left p-3 font-semibold rounded-tl-lg">
                    Feature
                  </th>
                  <th className="text-left p-3 font-semibold">
                    Big Mac Index
                  </th>
                  <th className="text-left p-3 font-semibold">
                    MIT BPP
                  </th>
                  <th className="text-left p-3 font-semibold text-blue-200 rounded-tr-lg">
                    UIFPI ★
                  </th>
                </tr>
              </thead>
              <tbody>
                {COMPARISON_DATA.map((row, i) => (
                  <tr
                    key={row.feature}
                    className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
                  >
                    <td className="p-3 font-medium text-gray-700 border-b border-gray-100">
                      {row.feature}
                    </td>
                    <td className="p-3 text-gray-600 border-b border-gray-100">
                      {row.bigMac}
                    </td>
                    <td className="p-3 text-gray-600 border-b border-gray-100">
                      {row.bpp}
                    </td>
                    <td className="p-3 text-[#1a365d] font-medium border-b border-gray-100">
                      {row.uifpi}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            BPP = MIT Billion Prices Project (Cavallo &amp; Rigobon 2016).
            ★ UIFPI is the only index to cover the informal food economy.
          </p>
        </Section>

        {/* References */}
        <section id="references" className="scroll-mt-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4 pb-2 border-b border-gray-200">
            Key References
          </h2>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>
              Cavallo, A. &amp; Rigobon, R. (2016). The Billion Prices Project:
              Using online prices for measurement and research.{" "}
              <em>Journal of Economic Perspectives</em>, 30(2), 151–178.
            </li>
            <li>
              The Economist. (1986). The Big Mac Index.{" "}
              <em>The Economist</em>.
            </li>
            <li>
              UNDP. (2021). Informal food systems and household expenditure in
              developing economies. United Nations Development Programme.
            </li>
            <li>
              Granger, C.W.J. (1969). Investigating causal relations by
              econometric models and cross-spectral methods.{" "}
              <em>Econometrica</em>, 37(3), 424–438.
            </li>
          </ul>
        </section>
      </div>

      <div className="mt-10 pt-6 border-t border-gray-200 flex gap-4">
        <Link
          href="/data"
          className="inline-flex items-center gap-2 bg-[#1a365d] text-white font-medium px-5 py-2.5 rounded-lg hover:bg-[#2a4a7f] transition-colors text-sm"
        >
          Download Data →
        </Link>
        <a
          href="https://github.com/thefrogfacedfoot/Inflation-menu"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 border border-gray-300 text-gray-700 font-medium px-5 py-2.5 rounded-lg hover:border-gray-400 transition-colors text-sm"
        >
          GitHub Repository →
        </a>
      </div>
    </div>
  );
}
