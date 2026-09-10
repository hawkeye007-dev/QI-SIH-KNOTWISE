import { DemoData } from '@/types/demo';
import { fuelMixByPrice, fuelsElectedInSweep } from '@/lib/planAnalytics';
import { fuelName } from '@/lib/labels';
import { seriesColor } from './Charts';
import styles from './FuelTransitionStages.module.css';

/** Collapse only adjacent identical fuel counts; retain the tested price ranges.
 * This describes composition, not equivalence of the full operating plans. */
export function FuelTransitionStages({ data }: { data: DemoData }) {
  const mix = fuelMixByPrice(data);
  const fuels = fuelsElectedInSweep(data);
  const stages: { start: number; end: number; counts: Record<string, number>; total: number }[] = [];
  for (const point of mix) {
    const previous = stages[stages.length - 1];
    if (previous && previous.total === point.totalSlots && fuels.every(id => (previous.counts[id] ?? 0) === (point.counts[id] ?? 0))) {
      previous.end = point.price;
    } else {
      stages.push({ start: point.price, end: point.price, counts: point.counts, total: point.totalSlots });
    }
  }
  if (!stages.length) return <p>No fuel choices are available in this dataset.</p>;

  return (
    <div className={styles.stages}>
      <div className={styles.intro}><div><span className="report-eyebrow">The transition, simplified</span><h2>{stages.length} fuel mixes across {mix.length} tested prices.</h2></div><p>Read from lower to higher carbon prices. Each column groups consecutive tested prices with the same fuel mix; other operating decisions may still change.</p></div>
      <ol className={styles.grid} style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
        {stages.map((stage, index) => {
          const previous = stages[index - 1];
          const entering = previous ? fuels.filter(id => (stage.counts[id] ?? 0) > 0 && !(previous.counts[id] ?? 0)) : [];
          return <li key={stage.start} className={styles.stage}>
            <div className={styles.price}><span>{index === 0 ? 'Starting mix' : entering.length ? 'New fuel enters' : 'Mix shifts'}</span><h3>${stage.start}{stage.end !== stage.start && <>–{stage.end.toLocaleString()}</>}</h3><small>per tCO₂e</small></div>
            <dl className={styles.fuels}>{fuels.map((id, fuelIndex) => {
              const count = stage.counts[id] ?? 0;
              const share = stage.total > 0 ? count / stage.total * 100 : 0;
              return <div key={id} className={styles.fuel}><dt>{fuelName(id)}</dt><dd><strong>{share.toFixed(0)}%</strong><span>{count} vessel-years</span></dd><div className={styles.track} aria-hidden="true"><span style={{width:`${share}%`,background:seriesColor(fuelIndex)}} /></div></div>;
            })}</dl>
            <p className={styles.caption}>{index === 0 ? 'The reference mix before carbon pricing changes fuel choices.' : entering.length ? `${entering.map(fuelName).join(', ')} is first elected at $${stage.start}/t.` : `The fuel mix first changes at the tested price of $${stage.start}/t.`}</p>
          </li>;
        })}
      </ol>
      <p className={styles.note}>Shares count vessel-years, not fuel mass. One vessel-year is one vessel’s fuel choice for one year. Ranges describe tested prices only; thresholds between sampled prices are not inferred.</p>
    </div>
  );
}
