'use client';

import { DataGate } from '@/components/DataGate';
import { FleetMatrixView } from '@/components/FleetMatrixView';

export default function FleetMatrixPage() {
  return <DataGate>{(data) => <FleetMatrixView data={data} />}</DataGate>;
}
