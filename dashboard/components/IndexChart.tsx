"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { IndexPoint } from "@/types";

interface Props {
  data: IndexPoint[];
  country: string;
  showFormal?: boolean;
  showInformal?: boolean;
  showCpi?: boolean;
  height?: number;
}

function fmt(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(1);
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded shadow-lg p-3 text-sm min-w-[160px]">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex justify-between gap-4">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-mono font-medium">{fmt(entry.value)}</span>
        </div>
      ))}
    </div>
  );
};

export default function IndexChart({
  data,
  country,
  showFormal = true,
  showInformal = true,
  showCpi = true,
  height = 360,
}: Props) {
  const hasFormal = showFormal && data.some((d) => d.formal != null && d.formal !== d.uifpi);
  const hasInformal = showInformal && data.some((d) => d.informal != null && d.informal !== d.uifpi);
  const hasCpi = showCpi && data.some((d) => d.cpi != null);
  const hasUifpi = data.some((d) => d.uifpi != null);

  if (!data.length) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center bg-gray-50 rounded-lg text-gray-400 text-sm"
      >
        No index data available yet
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
            axisLine={{ stroke: "#e5e7eb" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(v) => v.toFixed(0)}
            label={{
              value: "Index (base = 100)",
              angle: -90,
              position: "insideLeft",
              offset: 12,
              style: { fontSize: 10, fill: "#9ca3af" },
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            iconType="line"
          />
          <ReferenceLine y={100} stroke="#d1d5db" strokeDasharray="4 4" />

          {hasUifpi && (
            <Line
              type="monotone"
              dataKey="uifpi"
              name="UIFPI Combined"
              stroke="#1a365d"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "#1a365d" }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          )}
          {hasFormal && (
            <Line
              type="monotone"
              dataKey="formal"
              name="Chain"
              stroke="#3182ce"
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
              connectNulls
            />
          )}
          {hasInformal && (
            <Line
              type="monotone"
              dataKey="informal"
              name="Independent"
              stroke="#e53e3e"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              connectNulls
            />
          )}
          {hasCpi && (
            <Line
              type="monotone"
              dataKey="cpi"
              name="Official CPI"
              stroke="#718096"
              strokeWidth={2}
              dot={{ r: 3, fill: "#718096" }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
