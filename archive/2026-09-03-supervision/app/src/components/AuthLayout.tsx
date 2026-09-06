import type { ReactNode } from 'react';
import { useI18n } from '@/context/I18nContext';
import { LogoLockup } from '@/components/Logo';
import { LangToggle, ThemeToggle } from '@/components/Controls';

/** Centered card layout for the login / register screens with brand backdrop. */
export function AuthLayout({
  title,
  children,
  footer,
}: {
  title: string;
  children: ReactNode;
  footer: ReactNode;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden px-4 py-10">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_80%_at_85%_0%,rgba(46,158,79,.12),transparent_60%),radial-gradient(50%_70%_at_10%_20%,rgba(212,175,55,.09),transparent_60%)]"
      />
      <div className="absolute top-5 flex items-center gap-2 ltr:right-5 rtl:left-5">
        <LangToggle />
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-md animate-fade-in">
        <div className="mb-6 flex flex-col items-center gap-4 text-center">
          <LogoLockup size={52} />
          <div>
            <h1 className="text-2xl font-extrabold text-text">{title}</h1>
            <p className="mt-1 text-sm text-muted">{t('auth.subtitle')}</p>
          </div>
        </div>

        <div className="rounded-brand-lg border border-line bg-bg-2 p-6 shadow-brand sm:p-8">
          {children}
        </div>

        <p className="mt-5 text-center text-sm text-muted">{footer}</p>
      </div>
    </div>
  );
}
