import { useEffect, useRef } from 'react';
import { useI18n } from '@/context/I18nContext';
import { Button } from '@/components/ui';

/**
 * Lightweight modal confirmation. Traps Escape, restores focus, and dims the
 * background. Rendered only when `open` is true.
 */
export function ConfirmDialog({
  open,
  message,
  confirmLabel,
  tone = 'danger',
  onConfirm,
  onCancel,
  busy = false,
}: {
  open: boolean;
  message: string;
  confirmLabel?: string;
  tone?: 'danger' | 'primary';
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}): JSX.Element | null {
  const { t } = useI18n();
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[120] grid place-items-center bg-black/55 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm animate-fade-in rounded-brand-lg border border-line-2 bg-bg-2 p-6 shadow-brand"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-base font-semibold text-text">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
            {t('action.cancel')}
          </Button>
          <Button
            ref={confirmRef}
            variant={tone === 'danger' ? 'danger' : 'primary'}
            size="sm"
            onClick={onConfirm}
            loading={busy}
          >
            {confirmLabel ?? t('action.confirm')}
          </Button>
        </div>
      </div>
    </div>
  );
}
