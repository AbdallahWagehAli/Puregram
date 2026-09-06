import { useI18n } from '@/context/I18nContext';

/**
 * Inline brand mark reproduced from site/assets/icons/logo.svg — red disk,
 * gold ring, paper plane. Used for crisp small UI marks.
 */
export function LogoMark({ size = 40 }: { size?: number }): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      role="img"
      aria-label="Puregram Control"
      className="shrink-0 rounded-[28%]"
    >
      <defs>
        <linearGradient id="pgBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0C1426" />
          <stop offset="1" stopColor="#070C18" />
        </linearGradient>
        <linearGradient id="pgPlane" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FF4040" />
          <stop offset="1" stopColor="#E01F1F" />
        </linearGradient>
        <linearGradient id="pgGoldMark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#E6C24A" />
          <stop offset="1" stopColor="#C79A2B" />
        </linearGradient>
      </defs>
      <rect width="96" height="96" rx="24" fill="url(#pgBg)" />
      <circle cx="48" cy="48" r="33" fill="none" stroke="url(#pgGoldMark)" strokeWidth="2.4" opacity="0.55" />
      <path d="M71 28 L27 47 L42 53 L47 70 L55 56 L71 28 Z" fill="url(#pgPlane)" />
      <path d="M71 28 L42 53 L47 70 L55 56 Z" fill="url(#pgGoldMark)" opacity="0.92" />
      <path d="M71 28 L42 53" fill="none" stroke="#070C18" strokeWidth="1.6" opacity="0.35" strokeLinecap="round" />
    </svg>
  );
}

/** Logo + wordmark lockup used in the sidebar and auth screens. */
export function LogoLockup({ size = 40 }: { size?: number }): JSX.Element {
  const { t, lang } = useI18n();
  return (
    <span className="flex items-center gap-3">
      <LogoMark size={size} />
      <span className="flex flex-col leading-none">
        <span
          className={`grad-text font-extrabold tracking-tight ${lang === 'ar' ? 'font-cairo text-xl' : 'font-en text-lg'}`}
        >
          {t('app.name')}
        </span>
        <span className="gold-text text-[10px] font-bold uppercase tracking-[0.2em] font-en">
          Control
        </span>
      </span>
    </span>
  );
}
