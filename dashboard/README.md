# UICPI Dashboard

Public-facing Next.js dashboard for the **Unified Independent-Chain Price Index**
research project. Displays UICPI vs official CPI for 8 countries with charts,
methodology, and data downloads.

## Local Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Deploy to Vercel (one command)

```bash
npx vercel --prod
```

Or connect the GitHub repository at vercel.com/new for automatic deploys
on every push to main.

## Project Structure

```
dashboard/
├── app/
│   ├── page.tsx              # Homepage — country grid + map
│   ├── [country]/page.tsx    # Country detail — chart + stats
│   ├── methodology/page.tsx  # Methodology page
│   ├── data/page.tsx         # Data download page
│   ├── layout.tsx            # Global navbar + footer
│   └── globals.css
├── components/
│   ├── IndexChart.tsx        # Recharts line chart (reusable)
│   ├── CountryMap.tsx        # SVG world map with hover
│   └── StatCard.tsx          # Stat display card
├── lib/
│   └── data.ts               # Data fetching utilities
├── types/
│   └── index.ts              # Shared TypeScript types
└── public/
    └── data/                 # JSON data files
        ├── index_series.json
        ├── country_summary.json
        └── latest_values.json
```

## Updating Data

Data files live in `public/data/`. To refresh:

```bash
# From the root Inflation-menu/ directory:
python3 dashboard_data.py          # regenerate dashboard_data/*.json
cp dashboard_data/*.json dashboard/public/data/
```

Then redeploy: `npx vercel --prod`

## Tech Stack

- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS v4
- Recharts (charts)
- Lucide React (icons)

## Pages

| Route | Description |
|-------|-------------|
| `/` | Homepage with 8-country grid and world map |
| `/[country]` | Country detail with full chart and stats |
| `/methodology` | Research methodology and comparison table |
| `/data` | Data download page with per-country CSV |
