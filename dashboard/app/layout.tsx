import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "UICPI — Unified Independent-Chain Price Index",
  description:
    "A real-time restaurant price index tracking chain and independent food vendors across 10 countries as a leading indicator of official CPI.",
  openGraph: {
    title: "UICPI — Unified Independent-Chain Price Index",
    description:
      "Real-time restaurant price index across 10 countries. Extends MIT Billion Prices Project to independent vendors.",
    type: "website",
  },
};

function NavBar() {
  return (
    <nav className="bg-[#1a365d] text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <Link href="/" className="font-bold text-lg tracking-tight hover:text-blue-200 transition-colors">
            UICPI
          </Link>
          <div className="flex items-center gap-6 text-sm font-medium">
            <Link href="/" className="hover:text-blue-200 transition-colors hidden sm:block">
              Dashboard
            </Link>
            <Link href="/methodology" className="hover:text-blue-200 transition-colors">
              Methodology
            </Link>
            <Link href="/data" className="hover:text-blue-200 transition-colors">
              Data
            </Link>
            <a
              href="https://github.com/thefrogfacedfoot/Inflation-menu"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-blue-200 transition-colors"
            >
              GitHub
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-white text-gray-900">
        <NavBar />
        <main className="flex-1">{children}</main>
        <footer className="border-t border-gray-200 py-6 text-center text-sm text-gray-500">
          <p>
            Open source research project &mdash;{" "}
            <a
              href="https://github.com/thefrogfacedfoot/Inflation-menu"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-gray-700"
            >
              GitHub
            </a>{" "}
            &mdash; Raffles Institution, Singapore. 2026.
          </p>
        </footer>
      </body>
    </html>
  );
}
