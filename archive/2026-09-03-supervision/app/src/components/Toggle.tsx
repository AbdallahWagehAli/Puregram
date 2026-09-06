/** Accessible switch used for chat allow/block toggles. */
export function Toggle({
  checked,
  onChange,
  disabled = false,
  labelOn,
  labelOff,
  id,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  labelOn: string;
  labelOff: string;
  id?: string;
}): JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={checked ? labelOn : labelOff}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors duration-200 ease-brand disabled:opacity-50 ${
        checked ? 'bg-grad' : 'bg-[var(--line-2)]'
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ease-brand ${
          checked ? 'ltr:translate-x-6 rtl:-translate-x-6' : 'ltr:translate-x-1 rtl:-translate-x-1'
        }`}
      />
    </button>
  );
}
