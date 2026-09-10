/** Shared display formatters.
 *
 *  Every page renders the same quantity the same way, so a figure a judge
 *  reads on the Overview is character-identical to the one on the page it
 *  links to. Formatting only — no derivation lives here (see planAnalytics).
 */

export const usdM = (value: number, digits = 2) => `$${(value / 1e6).toFixed(digits)}M`;

export const usdCompact = (value: number) =>
  Math.abs(value) >= 1e9 ? `$${(value / 1e9).toFixed(2)}B` : usdM(value);

export const inrCrore = (value: number, digits = 1) => `₹${(value / 1e7).toFixed(digits)} Cr`;

export const ktCO2e = (value: number, digits = 1) => `${(value / 1000).toFixed(digits)}k tCO₂e`;

export const kTonnes = (value: number, digits = 1) => `${(value / 1000).toFixed(digits)}k t`;

export const pct = (fraction: number, digits = 1) => `${(fraction * 100).toFixed(digits)}%`;

export const signedPct = (fraction: number, digits = 1) =>
  `${fraction > 0 ? '+' : fraction < 0 ? '−' : ''}${(Math.abs(fraction) * 100).toFixed(digits)}%`;

export const perTonne = (value: number) => `$${Math.round(value).toLocaleString()}/tCO₂e`;

export const count = (value: number, digits = 0) =>
  value.toLocaleString(undefined, { maximumFractionDigits: digits });
