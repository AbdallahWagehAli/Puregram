import type { ReactNode } from 'react';

/** Consistent page title block: kicker-style heading + optional subtitle/action. */
export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-text lg:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted lg:text-base">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
