import { ApiError } from '@/shared/api/api-error';
import { i18n } from '@/shared/i18n';

/**
 * User-facing text for a failed sign-in or sign-up. Resolved when called (not at import) so it
 * follows the active language. Backend texts are English-only, so only enveloped messages
 * (those with a `code`) are shown as sent; transport fallbacks become a translated generic line.
 */
export function authErrorMessage(error: unknown, flow: 'login' | 'register'): string {
  if (!ApiError.isApiError(error)) return i18n.t('common:errors.generic');
  // Status 0: the request never got a response (offline, CORS, timeout, API down).
  if (error.status === 0) return i18n.t('common:errors.network');
  if (error.status === 401) {
    // After a 202 on register, a 401 on the follow-up login means the email already has an
    // account (the backend does not reveal it), so the login wording would be misleading.
    return flow === 'register'
      ? i18n.t('auth:errors.registerFailed')
      : i18n.t('auth:errors.invalidCredentials');
  }
  if (error.status === 429) {
    return error.retryAfter === undefined
      ? i18n.t('auth:errors.rateLimitedNoTime')
      : i18n.t('auth:errors.rateLimited', { count: Math.ceil(error.retryAfter) });
  }
  return error.code ? error.message : i18n.t('common:errors.generic');
}
