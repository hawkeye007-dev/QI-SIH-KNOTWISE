'use client';

import { useAtlas } from '@/lib/AtlasContext';
import { fuelMixByPrice, fuelsElectedInSweep } from '@/lib/planAnalytics';
import { fuelName } from '@/lib/labels';
import { seriesColor } from '@/components/Charts';
import { DemoData } from '@/types/demo';
import styles from './OverviewFuelMix.module.css';

/** Selected-plan composition, with the zero-price plan as a fixed reference.
 * Counts come from the same optimizer output as the detailed fuel sweep. */
export function OverviewFuelMix({ data }: { data: DemoData }) {
  const { closest } = useAtlas();
  const mix = fuelMixByPrice(data);
  const selected = mix.find(point => point.price === closest?.price_usd_per_tco2e);
  const baseline = mix.find(point => point.price === 0);
  const fuels = fuelsElectedInSweep(data);

  if (!selected || !baseline || !selected.totalSlots || !baseline.totalSlots) {
    return <p className={styles.empty}>Fuel composition is unavailable for this plan.</p>;
  }

  return (
    <div className={styles.mix}>
      <div className={styles.summary}>
        <span>Plan at <strong>${selected.price}/tCO₂e</strong></span>
        <span>{selected.totalSlots} vessel-years</span>
      </div>
      <div className={styles.legend} aria-hidden="true">
        <span><i className={styles.fillKey} /> Selected plan</span>
        <span><i className={styles.markerKey} /> $0 baseline</span>
      </div>
      <ul className={styles.rows} aria-label="Fuel shares in the selected plan compared with the zero-price baseline">
        {fuels.map((fuelId, index) => {
          const count = selected.counts[fuelId] ?? 0;
          const share = count / selected.totalSlots * 100;
          const baselineShare = (baseline.counts[fuelId] ?? 0) / baseline.totalSlots * 100;
          return (
            <li key={fuelId} className={styles.row}>
              <div className={styles.label}><span>{fuelName(fuelId)}</span><strong>{share.toFixed(0)}% <small>{count} / {selected.totalSlots}</small></strong></div>
              <div className={styles.track} aria-hidden="true">
                <span className={styles.fill} style={{ width: `${share}%`, background: seriesColor(index) }} />
                <span className={styles.marker} style={{ left: `${baselineShare}%` }} />
              </div>
              <span className={styles.baseline}>Baseline {baselineShare.toFixed(0)}%<span>{share === baselineShare ? 'Unchanged' : `${share > baselineShare ? '+' : '−'}${Math.abs(share - baselineShare).toFixed(0)} percentage points`}</span></span>
            </li>
          );
        })}
      </ul>
      <p className={styles.note}>One vessel-year is one vessel’s fuel choice for one year. Change the carbon price above to compare the mix.</p>
    </div>
  );
}
