"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { FloorDataPoint } from "@/types";

interface Props {
  data: FloorDataPoint[];
  label: string;
  yUnit?: string;
  color?: string;
  height?: number;
}

export default function FloorChart({
  data,
  label,
  yUnit,
  color = "#1a365d",
  height = 220,
}: Props) {
  if (!data.length) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center bg-gray-50 rounded text-xs text-gray-400"
      >
        No {label.toLowerCase()} data available
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={{ stroke: "#e5e7eb" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <Tooltip
            formatter={(v) => {
              const n = typeof v === "number" ? v : Number(v);
              return Number.isFinite(n)
                ? `${n.toFixed(2)}${yUnit ? ` ${yUnit}` : ""}`
                : "—";
            }}
            contentStyle={{
              fontSize: 12,
              borderRadius: 4,
              borderColor: "#e5e7eb",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            name={label}
            stroke={color}
            strokeWidth={2}
            dot={{ r: 2, fill: color }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
