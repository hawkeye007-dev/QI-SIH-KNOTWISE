'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SunIcon, MoonIcon } from '@phosphor-icons/react';
import { useTheme } from '@/lib/ThemeProvider';

/** Two tiers, because a flat list of eight is a list a judge skips.
 *  `primary` is the decision narrative — the path through the product.
 *  `evidence` is the proof behind it. */
const PRIMARY = [
  { href: '/', label: 'Overview' },
  { href: '/plans', label: 'Plans' },
  { href: '/fleet-matrix', label: 'Fleet' },
  { href: '/fuels', label: 'Fuels' },
];

const EVIDENCE = [
  { href: '/sensitivity', label: 'Sensitivity' },
  { href: '/exposure', label: 'Exposure' },
  { href: '/engine', label: 'Engine' },
  { href: '/prediction', label: 'Prediction' },
];

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const linkClass = (href: string, emphasis: 'primary' | 'evidence') => {
    const active = pathname === href;
    if (active) return 'bg-[var(--action-bg)] text-[var(--action-text)]';
    return emphasis === 'primary'
      ? 'text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)]';
  };

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--surface)] px-4 sm:px-6">
      <div className="mx-auto flex max-w-[1152px] flex-wrap items-center justify-between gap-x-6 gap-y-0 py-3">
        <Link
          href="/"
          className="shrink-0 rounded-full font-mono text-sm font-bold tracking-widest text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
        >
          KNOTWISE
        </Link>

        <nav aria-label="Main" className="order-3 flex w-full items-center gap-0.5 overflow-x-auto pt-2 md:order-none md:w-auto md:pt-0">
          {PRIMARY.map(link => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? 'page' : undefined}
              className={`whitespace-nowrap rounded px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${linkClass(link.href, 'primary')}`}
            >
              {link.label}
            </Link>
          ))}

          <span aria-hidden className="mx-1.5 h-4 w-px shrink-0 bg-[var(--border-strong)]" />

          {EVIDENCE.map(link => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? 'page' : undefined}
              className={`whitespace-nowrap rounded px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${linkClass(link.href, 'evidence')}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--border)] text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] active:scale-[0.96]"
        >
          {theme === 'dark' ? <SunIcon size={16} weight="bold" /> : <MoonIcon size={16} weight="bold" />}
        </button>
      </div>
    </header>
  );
};
