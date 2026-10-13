import { ApiError } from '@/shared/api/api-error';
import { i18n } from '@/shared/i18n';

export function describeSendError(error: unknown): string {
  if (!ApiError.isApiError(error)) return i18n.t('chat:sendError.generic');
  if (error.status === 409) return i18n.t('chat:sendError.busy');
  if (error.status === 429) {
    const wait = error.retryAfter;
    return wait === undefined
      ? i18n.t('chat:sendError.tooFast')
      : i18n.t('chat:sendError.tooFastWait', { seconds: wait });
  }
  return error.message;
}
