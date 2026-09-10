import { ReactNode } from 'react';

export function PageHeader({ category, title, children, detail }: {
  category: string;
  title: string;
  children: ReactNode;
  detail?: ReactNode;
}) {
  return (
    <header className="report-header">
      <div className="report-masthead"><span>Fleet intelligence / {category}</span><span>KnotWise · 2026–2030</span></div>
      <div className="report-intro"><div><h1>{title}</h1>{detail && <div className="report-detail">{detail}</div>}</div><div className="report-description">{children}</div></div>
    </header>
  );
}
