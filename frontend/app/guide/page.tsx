'use client';

import { DataGate } from '@/components/DataGate';
import { GuideView } from '@/components/GuideView';

export default function GuidePage() {
  return <DataGate>{(data) => <GuideView data={data} />}</DataGate>;
}
