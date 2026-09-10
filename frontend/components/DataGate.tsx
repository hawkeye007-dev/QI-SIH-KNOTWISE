'use client';

import React from 'react';
import { ArrowClockwiseIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { useAtlas } from '@/lib/AtlasContext';
import { DemoData } from '@/types/demo';

/** Shared loading/error boundary for every page -- `demo_data.json` is
 *  fetched once in AtlasProvider, and every page renders through this so
 *  the loading/"file not found" states aren't re-implemented per route. */
export function DataGate({ children }: { children: (data: DemoData) => React.ReactNode }) {
  const { data, loading, error } = useAtlas();

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-[var(--text-tertiary)] text-sm gap-3 py-24">
        <div className="w-6 h-6 border-2 border-[var(--border)] border-t-[var(--text-primary)] rounded-full animate-spin" />
        <span>Loading KnotWise Compliance Atlas…</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="bg-[var(--surface-elevated)] border border-[var(--border)] shadow-sm p-6 rounded-xl max-w-sm text-center">
          <WarningCircleIcon size={28} weight="bold" className="mx-auto mb-3 text-[var(--danger)]" />
          <div className="text-sm font-semibold text-[var(--danger)] mb-2">Data file not found</div>
          <p className="text-sm text-[var(--text-secondary)] mb-4">Could not load demo_data.json.</p>
          <button
            onClick={() => location.reload()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--action-bg)] text-[var(--action-text)] font-semibold text-sm rounded-lg hover:bg-[var(--action-bg-hover)] transition-colors active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:outline-none"
          >
            <ArrowClockwiseIcon size={15} weight="bold" />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return <>{children(data)}</>;
}
