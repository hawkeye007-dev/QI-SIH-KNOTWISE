/** Display names for identifiers the optimizer works in.
 *
 *  One table, imported everywhere, so a fuel is spelled the same on the
 *  Overview chart, the Fleet Matrix and the Fuels page. Unknown ids fall
 *  through to the raw identifier rather than being hidden.
 */

export const FUEL_NAMES: Record<string, string> = {
  hfo_scrubber: 'HFO + Scrubber',
  vlsfo: 'VLSFO',
  mgo: 'MGO',
  lng: 'LNG',
  b30_blend: 'B30 Biofuel',
  methanol: 'e-Methanol',
  ammonia: 'Green Ammonia',
  hydrogen: 'Green Hydrogen',
};

export const FUEL_NOTES: Record<string, string> = {
  hfo_scrubber: 'Heavy fuel oil with an exhaust scrubber — the incumbent, and the cheapest per tonne.',
  vlsfo: 'Very-low-sulphur fuel oil: the post-2020 default bunker.',
  mgo: 'Marine gas oil — a cleaner distillate, priced well above residual fuels.',
  lng: 'Liquefied natural gas: a real intensity cut, limited by methane slip.',
  b30_blend: 'A 30% biofuel blend, drop-in compatible with existing engines.',
  methanol: 'Renewable methanol — deep intensity cut, roughly half the energy per tonne.',
  ammonia: 'Zero-carbon at the stack, the lowest well-to-wake intensity in the catalog.',
  hydrogen: 'Green hydrogen: highest energy per tonne, hardest to bunker.',
};

export const ROUTE_NAMES: Record<string, string> = {
  india_northeurope: 'India → N. Europe',
  india_mediterranean: 'India → Mediterranean',
  india_gulf: 'India → Arabian Gulf',
  india_seasia: 'India → SE Asia',
  coastal_westcoast: 'India West Feeder',
  coastal_eastcoast: 'India East Feeder',
};

export const VESSEL_CLASS_NAMES: Record<string, string> = {
  A: 'Panamax containership',
  B: 'Handysize bulk carrier',
  C: 'Coastal feeder',
};

export const fuelName = (fuelId: string) => FUEL_NAMES[fuelId] ?? fuelId;
export const routeName = (routeId: string) => ROUTE_NAMES[routeId] ?? routeId;
