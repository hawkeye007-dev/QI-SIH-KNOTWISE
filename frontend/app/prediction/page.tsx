'use client';

import { DataGate } from '@/components/DataGate';
import { FuelPredictionView } from '@/components/FuelPredictionView';

export default function PredictionPage() {
  return <DataGate>{data => <FuelPredictionView data={data} />}</DataGate>;
}
