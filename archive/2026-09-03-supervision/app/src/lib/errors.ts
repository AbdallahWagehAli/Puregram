import { ApiError } from '@/lib/api';
import { translate, type MessageKey } from '@/i18n/dictionary';
import type { Lang } from '@/types';

/**
 * Turn an unknown error into a localized, user-facing message. Falls back to the
 * server's `detail` text for statuses we do not specifically translate, so the
 * UI stays informative without leaking stack traces.
 */
export function errorMessage(error: unknown, lang: Lang): string {
  const tr = (key: MessageKey): string => translate(key, lang);

  if (error instanceof ApiError) {
    switch (error.status) {
      case 0:
        return tr('err.network');
      case 401:
        return tr('err.unauthorized');
      case 404:
        return tr('err.notFound');
      default:
        return error.detail || tr('common.error');
    }
  }
  return tr('common.error');
}
