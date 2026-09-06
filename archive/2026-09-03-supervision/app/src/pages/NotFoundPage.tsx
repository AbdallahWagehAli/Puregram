import { Link } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { LogoMark } from '@/components/Logo';
import { Button } from '@/components/ui';

export function NotFoundPage(): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 text-center">
      <LogoMark size={64} />
      <p className="grad-text text-5xl font-extrabold font-en">404</p>
      <p className="text-lg font-bold text-text">{t('route.notFound')}</p>
      <Link to="/">
        <Button variant="line">{t('route.goHome')}</Button>
      </Link>
    </div>
  );
}
