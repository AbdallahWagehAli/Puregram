import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useAuth } from '@/context/AuthContext';
import { AuthLayout } from '@/components/AuthLayout';
import { Button, Field } from '@/components/ui';
import { errorMessage } from '@/lib/errors';
import { cleanString, isValidEmail } from '@/lib/format';

const MIN_PASSWORD_LENGTH = 8;

export function RegisterPage(): JSX.Element {
  const { t, lang } = useI18n();
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setError(t('err.email'));
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(t('err.passwordLen'));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const name = cleanString(displayName);
      await register({
        email: email.trim().toLowerCase(),
        password,
        lang,
        ...(name ? { display_name: name } : {}),
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(errorMessage(err, lang));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title={t('auth.registerTitle')}
      footer={
        <>
          {t('auth.haveAccount')}{' '}
          <Link to="/login" className="font-bold text-brand-red hover:underline">
            {t('auth.goLogin')}
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
        <Field
          label={t('auth.displayName')}
          hint={t('common.optional')}
          name="name"
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <Field
          label={t('common.email')}
          name="email"
          type="email"
          autoComplete="email"
          dir="ltr"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Field
          label={t('common.password')}
          hint={t('auth.passwordHint')}
          name="password"
          type="password"
          autoComplete="new-password"
          dir="ltr"
          minLength={MIN_PASSWORD_LENGTH}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && (
          <p role="alert" className="text-sm font-semibold text-brand-red">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" loading={submitting} className="mt-1 w-full">
          {t('auth.registerCta')}
        </Button>
      </form>
    </AuthLayout>
  );
}
