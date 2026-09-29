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
  hfo_scrubber: 'Incumbent; cheapest per tonne.',
  vlsfo: 'Post-2020 default bunker.',
  mgo: 'Cleaner distillate, costly.',
  lng: 'Limited by methane slip.',
  b30_blend: 'Drop-in for existing engines.',
  methanol: 'Deep cut, half the energy per tonne.',
  ammonia: 'Near-zero well-to-wake.',
  hydrogen: 'Most energy per tonne, hardest to bunker.',
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

export const DECISION_NAMES: Record<string, string> = {
  fuel_id: 'Fuel',
  route_id: 'Route',
  speed_band_index: 'Speed band',
  shore_power: 'Shore power',
  pool_opt_in: 'FuelEU pooling',
  borrow_election: 'FuelEU borrowing',
};

export const fuelName = (fuelId: string) => FUEL_NAMES[fuelId] ?? fuelId;
export const routeName = (routeId: string) => ROUTE_NAMES[routeId] ?? routeId;
