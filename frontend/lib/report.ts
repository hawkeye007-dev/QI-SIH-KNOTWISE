import { ComparableRecommendations, VesselYearGene } from '@/types/demo';
import { fuelName, routeName } from './labels';
import { ktCO2e, kTonnes, usdM } from './format';

const escape = (value: unknown) =>
  String(value).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

const yesNo = (value: boolean) => (value ? 'Yes' : 'No');

const sortGenes = (genes: VesselYearGene[]) =>
  [...genes].sort((a, b) => a.vessel_id.localeCompare(b.vessel_id) || a.year - b.year);

/** Save text as a file in the browser. */
export function downloadFile(filename: string, contents: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** One row per plan × vessel × year, for spreadsheets. */
export function plansCsv(recommendations: ComparableRecommendations): string {
  const header = ['plan', 'vessel_id', 'year', 'route', 'speed_band', 'fuel', 'shore_power', 'fueleu_pool', 'fueleu_borrow'];
  const rows = recommendations.alternatives.flatMap(plan =>
    sortGenes(plan.configuration).map(gene => [
      plan.definition, gene.vessel_id, gene.year, routeName(gene.route_id), gene.speed_band_index,
      fuelName(gene.fuel_id), gene.shore_power, gene.pool_opt_in, gene.borrow_election,
    ])
  );
  return [header, ...rows].map(row => row.map(cell => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
}

/** A self-contained, printable HTML report of the current three-plan comparison. */
export function plansReportHtml(recommendations: ComparableRecommendations, generatedAt: Date): string {
  const { scenario, alternatives } = recommendations;
  const summaryRows = alternatives.map(plan => `<tr>
      <td>${escape(plan.definition)}</td>
      <td>${usdM(plan.metrics.total_usd, 1)}</td>
      <td>${ktCO2e(plan.metrics.lifecycle_emissions_tco2e, 0)}</td>
      <td>${kTonnes(plan.metrics.fuel_tonnes)}</td>
      <td>${usdM(plan.metrics.compliance_usd, 2)}</td>
      <td>${plan.emissions_cap_tco2e === null ? '—' : ktCO2e(plan.emissions_cap_tco2e, 0)}</td>
    </tr>`).join('');

  const planSections = alternatives.map(plan => `
    <h2>${escape(plan.definition)} plan: decisions</h2>
    <table>
      <thead><tr><th>Vessel</th><th>Year</th><th>Route</th><th>Speed band</th><th>Fuel</th><th>Shore power</th><th>FuelEU pool</th><th>Borrow</th></tr></thead>
      <tbody>${sortGenes(plan.configuration).map(gene => `<tr>
        <td>${escape(gene.vessel_id)}</td><td>${gene.year}</td><td>${escape(routeName(gene.route_id))}</td>
        <td>${gene.speed_band_index}</td><td>${escape(fuelName(gene.fuel_id))}</td>
        <td>${yesNo(gene.shore_power)}</td><td>${yesNo(gene.pool_opt_in)}</td><td>${yesNo(gene.borrow_election)}</td>
      </tr>`).join('')}</tbody>
    </table>`).join('');

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>KnotWise fleet plan report</title>
<style>
  body { font: 13px/1.5 system-ui, sans-serif; color: #111; max-width: 960px; margin: 32px auto; padding: 0 16px; }
  h1 { font-size: 22px; margin-bottom: 4px; } h2 { font-size: 15px; margin-top: 28px; }
  p.meta { color: #555; margin-top: 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
  th { background: #f2f4f5; }
  @media print { h2 { break-before: auto; } tr { break-inside: avoid; } }
</style></head><body>
<h1>KnotWise fleet plan report</h1>
<p class="meta">SIH26138 · Generated ${escape(generatedAt.toISOString().slice(0, 16).replace('T', ' '))} UTC ·
Scenario: $${scenario.effective_carbon_price_usd_per_tco2e}/tCO₂e carbon price, ${(scenario.cargo_demand_multiplier ?? 1).toFixed(1)}× cargo demand ·
Optimizer: ${escape(recommendations.optimizer.toUpperCase())}</p>
<h2>Plan comparison (five-year totals)</h2>
<table>
  <thead><tr><th>Plan</th><th>Total cost</th><th>Lifecycle GHG</th><th>Bunker mass</th><th>Compliance (negative = credit)</th><th>GHG cap</th></tr></thead>
  <tbody>${summaryRows}</tbody>
</table>
<p>Every plan meets annual cargo demand and service-day limits on every route and year. Balanced: ${escape(recommendations.balanced_definition)}</p>
${planSections}
</body></html>`;
}
