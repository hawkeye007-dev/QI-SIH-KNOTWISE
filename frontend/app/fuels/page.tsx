'use client';

import { DataGate } from '@/components/DataGate';
import { FuelsView } from '@/components/FuelsView';

export default function FuelsPage() {
  return <DataGate>{data => <FuelsView data={data} />}</DataGate>;
}
