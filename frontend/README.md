# KnotWise — frontend-claude

SIH26138 presentation build. Fork of `frontend-reimagined`, restructured so the
strongest measured results lead and the supporting detail sits one layer down.

```bash
npm install        # node_modules was copied in; re-run if you move the folder
npm run dev        # http://localhost:3000
npm run build      # production build; all 9 routes prerender
```

The optional live-solve form on `/plans` posts to the Python API:

```bash
python -m knotwise.api.server    # from the repo root, in the project venv
```

Without it the page still renders the alternatives baked into `demo_data.json`.

## Where numbers come from

Everything on screen traces to a file in `public/`:

| Source | Feeds |
|---|---|
| `demo_data.json` | fleet, sweep (41 plans), alternatives, exposure, predictor benchmark |
| `optimizer_scaling_benchmark.json` | the 6.7–8.0% solver headline, paired by seed |
| `optimizer_scaling_fair_start.json` | the attribution check on `/engine` |
| `optimizer_phase6_benchmark.json` | the exact-optimum reference |

`lib/planAnalytics.ts` is the only place that derives anything, and it is
restricted to selecting, grouping and differencing values the optimizer already
emitted. Fuel burn, lifecycle emissions, compliance cost and feasibility are
never recomputed in the browser — if a figure is not in the data, the page says
so instead of reconstructing it.

## Routes

Primary path (the decision narrative): `/` → `/plans` → `/fleet-matrix` → `/fuels`
Evidence: `/sensitivity`, `/exposure`, `/engine`, `/prediction`, plus `/guide`.

## Chart conventions

`components/Charts.tsx` holds every plot. The rules it keeps, so the charts read
as one system:

- **One y-scale per plot.** `/sensitivity` is four small multiples sharing an
  x-axis rather than one dual-axis chart.
- **Fixed series colours.** `--series-1..8` in `globals.css`, assigned to an
  entity once. A fuel keeps its hue regardless of which other fuels are drawn.
  The four-slot palette was validated for colour-vision separation against both
  the light and dark chart surfaces.
- **Relief for low-contrast slots.** Two of the four series sit below 3:1 on the
  light surface, so every chart using them ships a table view beside it.
- Solid hairline grid, 2px surface gaps between stacked fills, legend whenever
  there is more than one series, hover layer on every plot.
