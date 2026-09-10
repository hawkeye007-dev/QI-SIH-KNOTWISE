'use client';

import { DataGate } from '@/components/DataGate';
import { OptimizerView } from '@/components/OptimizerView';

export default function EnginePage() {
  return <DataGate>{data => <OptimizerView data={data} />}</DataGate>;
}
