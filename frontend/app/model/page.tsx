'use client';

import { DataGate } from '@/components/DataGate';
import { FormulationView } from '@/components/FormulationView';

export default function FormulationPage() {
  return <DataGate>{data => <FormulationView data={data} />}</DataGate>;
}
