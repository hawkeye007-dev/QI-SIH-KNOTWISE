'use client';

import { DataGate } from '@/components/DataGate';
import { ExposureView } from '@/components/ExposureView';

export default function ExposurePage() {
  return <DataGate>{(data) => <ExposureView data={data} />}</DataGate>;
}
