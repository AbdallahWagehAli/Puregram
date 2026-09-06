import { useToast, type ToastTone } from '@/context/ToastContext';
import { AlertIcon, CheckIcon, XIcon } from '@/components/icons';

const TONE_STYLES: Record<ToastTone, string> = {
  success: 'border-[rgba(52,199,120,.5)] text-text',
  error: 'border-[rgba(46,158,79,.5)] text-text',
  info: 'border-line-2 text-text',
};

function ToneIcon({ tone }: { tone: ToastTone }): JSX.Element {
  if (tone === 'success') return <CheckIcon size={18} className="text-[#34c778]" />;
  if (tone === 'error') return <AlertIcon size={18} className="text-brand-red" />;
  return <CheckIcon size={18} className="text-[var(--gold)]" />;
}

/** Fixed, ARIA-live stack of dismissible toasts. */
export function ToastViewport(): JSX.Element {
  const { toasts, dismiss } = useToast();
  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-6 z-[100] flex flex-col items-center gap-2 px-4"
      role="region"
      aria-live="polite"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex w-full max-w-sm animate-toast-in items-center gap-3 rounded-2xl border bg-[var(--nav-bg-2)] px-4 py-3 shadow-brand backdrop-blur ${TONE_STYLES[toast.tone]}`}
        >
          <ToneIcon tone={toast.tone} />
          <span className="flex-1 text-sm font-semibold">{toast.message}</span>
          <button
            type="button"
            onClick={() => dismiss(toast.id)}
            className="text-dim transition-colors hover:text-text"
            aria-label="Dismiss"
          >
            <XIcon size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
