import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnotWise — Compliance & Regulatory Risk Atlas",
  description: "IMO 4 Dec 2026 Vote Sensitivity · Quantum-Inspired Multi-Scenario Fleet Decision Demo · SIH26138",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
