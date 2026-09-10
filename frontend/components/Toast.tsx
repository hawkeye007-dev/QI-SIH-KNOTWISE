'use client';

import React from 'react';
import { useAtlas } from '@/lib/AtlasContext';

/** Global notification toast -- rendered once in the root layout so it
 *  survives page navigation regardless of which route triggered it. */
export const Toast: React.FC = () => {
  const { notification } = useAtlas();
  if (!notification) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[1000] max-w-sm bg-[var(--action-bg)] text-[var(--action-text)] px-4 py-3 rounded-xl shadow-2xl flex items-start gap-3">
      <span className="w-2 h-2 mt-1.5 rounded-full bg-[var(--success)] animate-ping shrink-0" />
      <span className="text-sm font-medium leading-relaxed">{notification}</span>
    </div>
  );
};
