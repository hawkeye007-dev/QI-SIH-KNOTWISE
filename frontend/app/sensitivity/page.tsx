'use client';

import { DataGate } from '@/components/DataGate';
import { CostCurveView } from '@/components/CostCurveView';

export default function SensitivityPage() {
  return <DataGate>{data => <CostCurveView data={data} />}</DataGate>;
}
