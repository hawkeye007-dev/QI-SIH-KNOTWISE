import type { Metadata } from "next";
import Link from "next/link";
import { Geist } from "next/font/google";
import "./globals.css";
import { AtlasProvider } from "@/lib/AtlasContext";
import { ThemeProvider } from "@/lib/ThemeProvider";
import { Navbar } from "@/components/Navbar";
import { Toast } from "@/components/Toast";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "KnotWise — Quantum-Inspired Green Fleet Optimization",
  description:
    "Fuel consumption prediction and multi-objective green fleet optimization across IMO NZF, CII, FuelEU Maritime and EU ETS, solved with a quantum-inspired evolutionary algorithm. SIH26138 · Egreen Quanta.",
};

// Sets the .dark class before React hydrates, reading the same localStorage
// key ThemeProvider writes to (falling back to system preference on a first
// visit), so there is no flash of the wrong theme on load.
const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('knotwise:theme');
    var dark = stored ? stored === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={geistSans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-[var(--surface)] text-[var(--text-primary)] flex flex-col font-sans">
        <ThemeProvider>
          <AtlasProvider>
            <Navbar />
            <div className="flex-1 flex flex-col">{children}</div>
            <footer className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] bg-[var(--surface-sunken)] px-6 py-4 text-xs text-[var(--text-tertiary)]">
              <div className="font-mono">KNOTWISE · SIH26138 · EGREEN QUANTA</div>
              <div className="flex flex-wrap items-center gap-4">
                <Link href="/guide" className="font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:underline">
                  How to read this platform
                </Link>
                <span className="font-mono">CII · NZF · FUELEU MARITIME · EU ETS</span>
              </div>
            </footer>
            <Toast />
          </AtlasProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
