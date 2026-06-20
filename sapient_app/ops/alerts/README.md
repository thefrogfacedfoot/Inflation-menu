# Alerting recipes

PromQL queries for the four guardrail signals worth paging on. These are
documented queries, not Alertmanager rules — wire them up when you stand up
Alertmanager. Each query is paired with the *why* so you can re-derive the
threshold when traffic shape changes.

All metrics are scraped from the per-service sidecar:

| service     | sidecar port | metric prefix |
| ----------- | ------------ | -------------- |
| finder      | 9090         | `finder_`       |
| dashboard   | 9091         | `dashboard_`    |
| visibility  | 9092         | `visibility_`   |

## 1. Runaway user — a single user tripping guardrails repeatedly

```promql
sum by (user_id) (
  rate(dashboard_guardrail_rejections_total[1h])
) > N
```

`N` is empirical — start at `0.05` (≈ 3 rejections/min sustained for an hour).
Tighten as you watch real traffic.

Note the rejection counter is labelled by `code`, NOT `user_id`. The PromQL
above relies on join labels from the recording rule below — without the
recording rule it's a guardrail aggregate by code, useful for "are rejections
spiking globally" but not for runaway-user attribution. If/when you need
per-user attribution, emit `user_id` as a structured-log field (already done
in `guardrails.ts`) and feed it through Loki/Logfire alongside Prometheus.

**Why:** repeated guardrail trips from one user usually means either (a) a
real abuser to ban manually, or (b) a bug in the guardrail itself rejecting a
legitimate workflow. Either is worth a page.

## 2. Pause spike — guardrails auto-pausing more users than usual

```promql
increase(dashboard_guardrail_pauses_total[15m]) > 3
```

**Why:** auto-pause is the system's "circuit breaker" — three trips in
fifteen minutes means we either ramped a threshold too tight or there's a
correlated issue (Reddit returning 5xx so removal_rate spikes, a buggy
detection model flipping mentions_product wrongly, etc.).

Break out by reason if you want a sharper signal:

```promql
sum by (reason) (increase(dashboard_guardrail_pauses_total[15m])) > 3
```

## 3. Cost-cap hit — visibility burned the daily budget

```promql
increase(visibility_cost_cap_short_circuits_total[1h]) > 0
```

**Why:** the per-source per-day cap exists to prevent runaway LLM spend. ANY
fire of this metric in production means the cap caught real spending — page
on the first hit so an operator can decide whether to raise the cap, kill the
schedule, or investigate a degenerate query that's getting retried.

Split by source to know which provider:

```promql
sum by (source) (increase(visibility_cost_cap_short_circuits_total[1h])) > 0
```

## 4. Scoring errors — finder's LLM call repeatedly failing

```promql
rate(finder_scoring_errors_total[5m]) > 0.1
```

Sustain for 5+ minutes before paging. Most likely cause: model outage,
quota exhaustion, or a response-shape change that broke parsing.

The `reason` label tells you which:

```promql
sum by (reason) (rate(finder_scoring_errors_total[5m]))
```

`rate_limited` → request a quota bump or throttle the poll cycle;
`timeout` / `upstream_5xx` → Anthropic incident, wait it out;
`json_parse` / `schema_invalid` → the model started returning something we
don't expect — bump the model pin or tighten the prompt;
`other` → unrecognized exception class, check logs for the
`type(e).__name__` field the poller emits.

Important: low-relevance posts (`scored-but-not-stored`) increment
`finder_opportunities_scored_total{stored="false"}`, NOT this counter. A
spike here means real failures, not just picky scoring.

## 5. Cross-schema breakage — visibility can't see public.opportunities

```promql
rate(visibility_cross_schema_link_failures_total[10m]) > 0
```

Sustain for 10 minutes before paging — transient DB blips aren't worth a
page, but persistent failures mean visibility tasks won't link back to
finder rows and the dashboard's "claim from visibility task" flow breaks
silently.

The `exception_class` label is bounded (it's the Python exception type name,
not user input), so cardinality is safe. Break out by class to triage:

```promql
sum by (exception_class) (rate(visibility_cross_schema_link_failures_total[10m]))
```

`UndefinedTable` → finder hasn't migrated yet; `OperationalError` →
connectivity; `ProgrammingError` → permission/grant issue on the schema.

## Out of scope (today)

- Alertmanager wiring
- OpenTelemetry traces
- Loki / log-based alerts
- Per-user attribution on rejection counters (see note in §1)

The `/metrics` endpoints are stubs — a scraper gets wired later. These
queries are runnable as soon as Prometheus discovers the sidecar ports.
