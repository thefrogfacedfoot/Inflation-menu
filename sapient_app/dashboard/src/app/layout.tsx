import type { ReactNode } from "react";

export const metadata = { title: "Opportunity Dashboard" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          margin: 0,
          background: "#0b0b0d",
          color: "#e7e7ea",
        }}
      >
        <main style={{ maxWidth: 960, margin: "0 auto", padding: "32px 24px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
