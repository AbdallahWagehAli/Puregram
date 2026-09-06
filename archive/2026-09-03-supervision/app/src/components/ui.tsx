import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';
import { useI18n } from '@/context/I18nContext';
import { AlertIcon, InboxIcon } from '@/components/icons';

/* -------------------------------- Button ---------------------------------- */

type ButtonVariant = 'primary' | 'line' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-grad text-white shadow-glow hover:-translate-y-0.5 hover:shadow-[0_20px_44px_-16px_rgba(46,158,79,.8)]',
  line: 'border border-line-2 text-text hover:border-brand-red hover:text-brand-red hover:-translate-y-0.5 bg-transparent',
  ghost: 'text-muted hover:text-text hover:bg-[var(--surface)]',
  danger:
    'border border-[rgba(46,158,79,.4)] text-brand-red hover:bg-[rgba(46,158,79,.1)]',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'px-4 py-2 text-sm',
  md: 'px-6 py-3 text-[15px]',
  lg: 'px-8 py-4 text-base',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, className = '', children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-bold transition-all duration-200 ease-brand disabled:cursor-not-allowed disabled:opacity-60 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading}
      {...props}
    >
      {loading && <Spinner size={16} />}
      {children}
    </button>
  );
});

/* -------------------------------- Spinner --------------------------------- */

export function Spinner({ size = 20 }: { size?: number }): JSX.Element {
  return (
    <span
      role="status"
      aria-label="loading"
      className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size }}
    />
  );
}

/* --------------------------------- Card ----------------------------------- */

export function Card({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <div className={`rounded-brand-lg border border-line bg-bg-2 ${className}`}>{children}</div>
  );
}

/* --------------------------------- Field ---------------------------------- */

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string | null;
}

export function Field({ label, hint, error, id, className = '', ...props }: FieldProps): JSX.Element {
  const inputId = id ?? props.name ?? label;
  return (
    <label className="block" htmlFor={inputId}>
      <span className="mb-1.5 flex items-baseline justify-between text-sm font-semibold text-text">
        <span>{label}</span>
        {hint && <span className="text-xs font-normal text-dim">{hint}</span>}
      </span>
      <input
        id={inputId}
        className={`w-full rounded-xl border bg-[var(--surface)] px-4 py-3 text-text outline-none transition-colors placeholder:text-dim focus:border-brand-red ${error ? 'border-[rgba(46,158,79,.6)]' : 'border-line-2'} ${className}`}
        aria-invalid={error ? true : undefined}
        {...props}
      />
      {error && <span className="mt-1 block text-xs font-semibold text-brand-red">{error}</span>}
    </label>
  );
}

/* ------------------------------ Empty state ------------------------------- */

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="flex flex-col items-center gap-3 rounded-brand-lg border border-dashed border-line-2 bg-bg-2 px-6 py-14 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-[linear-gradient(135deg,rgba(46,158,79,.14),rgba(212,175,55,.14))] text-brand-red">
        <InboxIcon size={26} />
      </span>
      <p className="text-lg font-bold text-text">{title}</p>
      {hint && <p className="max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/* ------------------------------ Error state ------------------------------- */

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-brand-lg border border-[rgba(46,158,79,.3)] bg-[rgba(46,158,79,.06)] px-6 py-12 text-center"
    >
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-[rgba(46,158,79,.12)] text-brand-red">
        <AlertIcon size={26} />
      </span>
      <p className="text-base font-bold text-text">{message}</p>
      {onRetry && (
        <Button variant="line" size="sm" onClick={onRetry}>
          {t('action.retry')}
        </Button>
      )}
    </div>
  );
}

/* ----------------------------- Stat / metric ------------------------------ */

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'gold' | 'red' | 'green';
}): JSX.Element {
  const tones: Record<string, string> = {
    neutral: 'bg-[var(--surface)] text-muted border-line-2',
    gold: 'bg-[rgba(212,175,55,.12)] text-[var(--gold)] border-[rgba(212,175,55,.4)]',
    red: 'bg-[rgba(46,158,79,.12)] text-brand-red border-[rgba(46,158,79,.4)]',
    green: 'bg-[rgba(52,199,120,.12)] text-[#34c778] border-[rgba(52,199,120,.4)]',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
