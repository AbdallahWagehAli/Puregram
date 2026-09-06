import { useState, type FormEvent, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useTheme } from '@/context/ThemeContext';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/PageHeader';
import { Button, Badge, Card, Field } from '@/components/ui';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { CheckIcon, CopyIcon, LogoutIcon } from '@/components/icons';
import { errorMessage } from '@/lib/errors';
import { cleanString } from '@/lib/format';
import type { Lang, Theme } from '@/types';

const MIN_PASSWORD_LENGTH = 8;

function Section({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-lg font-bold text-text">{title}</h2>
      {children}
    </Card>
  );
}

/* ------------------------------- Profile ---------------------------------- */

function ProfileSection(): JSX.Element {
  const { t, lang } = useI18n();
  const { user, setUser } = useAuth();
  const { notify } = useToast();
  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  const [busy, setBusy] = useState(false);

  const save = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await api.updateProfile({ display_name: cleanString(displayName) ?? '' });
      setUser(updated);
      notify(t('settings.saved'), 'success');
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title={t('settings.profile')}>
      <form onSubmit={save} className="flex flex-col gap-4">
        <Field label={t('common.email')} value={user?.email ?? ''} dir="ltr" readOnly disabled />
        <Field
          label={t('auth.displayName')}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <Button type="submit" size="sm" loading={busy} className="self-start">
          {t('action.save')}
        </Button>
      </form>
    </Section>
  );
}

/* ----------------------------- Appearance --------------------------------- */

function AppearanceSection(): JSX.Element {
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const { user, setUser } = useAuth();
  const { notify } = useToast();

  const chooseLang = async (next: Lang): Promise<void> => {
    setLang(next);
    if (!user || user.lang === next) return;
    try {
      setUser(await api.updateProfile({ lang: next }));
    } catch (err) {
      notify(errorMessage(err, next), 'error');
    }
  };

  const langOptions: { value: Lang; label: string }[] = [
    { value: 'ar', label: 'العربية' },
    { value: 'en', label: 'English' },
  ];
  const themeOptions: { value: Theme; labelKey: 'settings.themeDark' | 'settings.themeLight' }[] = [
    { value: 'dark', labelKey: 'settings.themeDark' },
    { value: 'light', labelKey: 'settings.themeLight' },
  ];

  return (
    <Section title={t('settings.appearance')}>
      <div className="flex flex-col gap-5">
        <div>
          <p className="mb-2 text-sm font-semibold text-text">{t('settings.language')}</p>
          <div className="flex gap-2">
            {langOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => chooseLang(opt.value)}
                aria-pressed={lang === opt.value}
                className={`flex-1 rounded-xl border px-4 py-3 text-sm font-bold transition-colors ${
                  lang === opt.value
                    ? 'border-brand-red bg-[rgba(46,158,79,.08)] text-text'
                    : 'border-line-2 text-muted hover:text-text'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-sm font-semibold text-text">{t('settings.theme')}</p>
          <div className="flex gap-2">
            {themeOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setTheme(opt.value)}
                aria-pressed={theme === opt.value}
                className={`flex-1 rounded-xl border px-4 py-3 text-sm font-bold transition-colors ${
                  theme === opt.value
                    ? 'border-brand-red bg-[rgba(46,158,79,.08)] text-text'
                    : 'border-line-2 text-muted hover:text-text'
                }`}
              >
                {t(opt.labelKey)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}

/* ------------------------------ Telegram ---------------------------------- */

function TelegramSection(): JSX.Element {
  const { t, lang } = useI18n();
  const { user, setUser } = useAuth();
  const { notify } = useToast();
  const [tgId, setTgId] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmUnbind, setConfirmUnbind] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bind = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    const parsed = Number(tgId.trim());
    if (!Number.isInteger(parsed) || parsed <= 0) {
      setError(t('err.tgIdInvalid'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setUser(await api.bindTelegram(parsed));
      notify(t('settings.tgBoundMsg'), 'success');
      setTgId('');
    } catch (err) {
      setError(errorMessage(err, lang));
    } finally {
      setBusy(false);
    }
  };

  const unbind = async (): Promise<void> => {
    setBusy(true);
    try {
      setUser(await api.unbindTelegram());
      notify(t('settings.tgUnboundMsg'), 'success');
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusy(false);
      setConfirmUnbind(false);
    }
  };

  const isBound = user?.tg_user_id != null;

  return (
    <Section title={t('settings.telegram')}>
      {isBound ? (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Badge tone="green">{t('settings.tgBound')}</Badge>
            <span className="font-en text-base font-bold text-text">{user?.tg_user_id}</span>
            <Badge tone={user?.tg_verified ? 'gold' : 'neutral'}>
              {user?.tg_verified ? t('settings.tgVerified') : t('settings.tgUnverified')}
            </Badge>
          </div>
          <Button variant="danger" size="sm" loading={busy} onClick={() => setConfirmUnbind(true)}>
            {t('settings.unbind')}
          </Button>
        </div>
      ) : (
        <form onSubmit={bind} className="flex flex-col gap-3" noValidate>
          <Field
            label={t('settings.tgId')}
            name="tgId"
            inputMode="numeric"
            dir="ltr"
            value={tgId}
            onChange={(e) => setTgId(e.target.value)}
            error={error}
          />
          <Button type="submit" size="sm" loading={busy} className="self-start">
            {t('settings.bind')}
          </Button>
        </form>
      )}

      <ConfirmDialog
        open={confirmUnbind}
        message={t('settings.unbindConfirm')}
        confirmLabel={t('settings.unbind')}
        busy={busy}
        onConfirm={unbind}
        onCancel={() => setConfirmUnbind(false)}
      />
    </Section>
  );
}

/* ------------------------------ Share code -------------------------------- */

function ShareCodeSection(): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
  const { notify } = useToast();
  const [copied, setCopied] = useState(false);
  const code = user?.share_code;

  if (!code) return <></>;

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      notify(t('common.copied'), 'success');
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      notify(t('common.error'), 'error');
    }
  };

  return (
    <Section title={t('settings.shareCode')}>
      <p className="mb-3 text-sm text-muted">{t('settings.shareCodeHint')}</p>
      <div className="flex items-center gap-2 rounded-xl border border-line-2 bg-[var(--surface)] p-2">
        <code className="flex-1 select-all px-2 font-en text-sm font-bold text-text">{code}</code>
        <Button size="sm" variant="line" onClick={copy} aria-label={t('common.copy')}>
          {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
          {copied ? t('common.copied') : t('common.copy')}
        </Button>
      </div>
    </Section>
  );
}

/* ------------------------------- Security --------------------------------- */

function SecuritySection(): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    if (next.length < MIN_PASSWORD_LENGTH) {
      setError(t('err.passwordLen'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.changePassword({ current_password: current, new_password: next });
      notify(t('settings.passwordChanged'), 'success');
      setCurrent('');
      setNext('');
    } catch (err) {
      setError(errorMessage(err, lang));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section title={t('settings.security')}>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <Field
          label={t('settings.currentPassword')}
          type="password"
          autoComplete="current-password"
          dir="ltr"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <Field
          label={t('settings.newPassword')}
          hint={t('auth.passwordHint')}
          type="password"
          autoComplete="new-password"
          dir="ltr"
          minLength={MIN_PASSWORD_LENGTH}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={error}
          required
        />
        <Button type="submit" size="sm" loading={busy} className="self-start">
          {t('settings.changePassword')}
        </Button>
      </form>
    </Section>
  );
}

export function SettingsPage(): JSX.Element {
  const { t } = useI18n();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async (): Promise<void> => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title={t('settings.title')} />
      <div className="flex flex-col gap-6">
        <ProfileSection />
        <AppearanceSection />
        <TelegramSection />
        <ShareCodeSection />
        <SecuritySection />

        <div className="flex justify-end">
          <Button variant="line" onClick={handleLogout}>
            <LogoutIcon size={18} />
            {t('nav.logout')}
          </Button>
        </div>
      </div>
    </div>
  );
}
