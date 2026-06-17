"use client";

import { useState } from "react";
import type { CountrySummary } from "@/types";
import { COUNTRY_SLUGS } from "@/types";
import Link from "next/link";

interface Props {
  summaries: Record<string, CountrySummary>;
}

// Approximate [x%, y%] position on the SVG viewBox for each country
const POSITIONS: Record<string, [number, number]> = {
  "United States":  [17,  38],
  "United Kingdom": [46,  28],
  Singapore:        [74,  57],
  Malaysia:         [73,  58.5],
  Indonesia:        [76,  62],
  Thailand:         [72,  53],
  India:            [68,  47],
  Australia:        [79,  73],
  Brazil:           [25,  62],
  Germany:          [49,  30],
  "South Africa":   [54,  77],
};

export default function CountryMap({ summaries }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="relative w-full">
      {/* Simple equirectangular world SVG background */}
      <svg
        viewBox="0 0 1000 500"
        className="w-full h-auto"
        style={{ background: "#dbeafe" }}
        aria-label="World map showing UIFPI country coverage"
      >
        {/* Simple land masses as polygons — very simplified */}
        {/* North America */}
        <path d="M 50 80 L 200 70 L 230 100 L 220 180 L 200 220 L 170 240 L 140 220 L 100 200 L 80 160 L 50 130 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* South America */}
        <path d="M 180 240 L 230 230 L 260 260 L 250 340 L 220 380 L 190 380 L 170 340 L 165 290 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* Europe */}
        <path d="M 430 60 L 520 55 L 530 100 L 500 120 L 460 115 L 435 95 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* Africa */}
        <path d="M 450 130 L 530 120 L 560 160 L 560 240 L 540 310 L 500 340 L 470 320 L 450 270 L 440 200 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* Asia */}
        <path d="M 530 55 L 780 50 L 820 80 L 800 140 L 760 160 L 720 150 L 680 130 L 620 120 L 570 110 L 540 90 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* South/SE Asia */}
        <path d="M 620 140 L 720 155 L 760 200 L 750 250 L 720 260 L 680 240 L 650 220 L 630 200 L 620 170 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* Australia */}
        <path d="M 740 340 L 840 330 L 870 360 L 860 410 L 820 430 L 770 420 L 740 400 L 730 370 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>
        {/* Greenland */}
        <path d="M 320 20 L 380 15 L 390 50 L 360 65 L 320 55 Z" fill="#e2e8f0" stroke="#cbd5e0" strokeWidth="1"/>

        {/* Country dots */}
        {Object.entries(POSITIONS).map(([country, [xPct, yPct]]) => {
          const summary = summaries[country];
          const isHovered = hovered === country;
          const isSignificant = summary?.granger_significant ?? false;
          const color = isSignificant ? "#276749" : "#64748b";
          const cx = (xPct / 100) * 1000;
          const cy = (yPct / 100) * 500;

          return (
            <g key={country}>
              <Link href={`/${COUNTRY_SLUGS[country]}`}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 14 : 10}
                  fill={color}
                  stroke="white"
                  strokeWidth={2}
                  style={{ cursor: "pointer", transition: "r 0.15s" }}
                  onMouseEnter={() => setHovered(country)}
                  onMouseLeave={() => setHovered(null)}
                />
              </Link>
              {isHovered && (
                <g>
                  <rect
                    x={cx + 16}
                    y={cy - 18}
                    width={160}
                    height={36}
                    rx={4}
                    fill="white"
                    stroke="#e2e8f0"
                    strokeWidth={1}
                    filter="url(#shadow)"
                  />
                  <text
                    x={cx + 24}
                    y={cy - 4}
                    fontSize={12}
                    fontWeight="600"
                    fill="#1a202c"
                  >
                    {country}
                  </text>
                  <text
                    x={cx + 24}
                    y={cy + 11}
                    fontSize={10}
                    fill="#6b7280"
                  >
                    {summary?.months_of_data ?? 0} months collected
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* drop shadow filter */}
        <defs>
          <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.15" />
          </filter>
        </defs>
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-6 mt-3 text-xs text-gray-500 justify-center">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full bg-[#276749]" />
          Granger significant
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-full bg-[#64748b]" />
          Data collection ongoing
        </span>
      </div>
    </div>
  );
}
