import { useI18n } from '@/context/I18nContext';
import { useTheme } from '@/context/ThemeContext';
import { MoonIcon, SunIcon } from '@/components/icons';

const ICON_BTN =
  'grid h-10 w-10 place-items-center rounded-xl border border-line-2 text-text transition-colors hover:border-brand-red hover:text-brand-red';

/** Toggles between Arabic and English. Shows the target language label. */
export function LangToggle(): JSX.Element {
  const { lang, toggleLang, t } = useI18n();
  return (
    <button
      type="button"
      onClick={toggleLang}
      className={`${ICON_BTN} font-en text-sm font-bold`}
      aria-label={t('lang.toggle')}
      title={t('lang.toggle')}
    >
      {lang === 'ar' ? 'EN' : 'ع'}
    </button>
  );
}

/** Toggles between dark and light themes. */
export function ThemeToggle(): JSX.Element {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={ICON_BTN}
      aria-label={t('theme.toggle')}
      title={t('theme.toggle')}
    >
      {theme === 'dark' ? <SunIcon size={18} /> : <MoonIcon size={18} />}
    </button>
  );
}
