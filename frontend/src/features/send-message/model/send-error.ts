import { ApiError } from '@/shared/api/api-error';

export function describeSendError(error: unknown): string {
  if (!ApiError.isApiError(error)) return 'Could not send the message. Please try again.';
  if (error.status === 409) {
    return 'This conversation is busy. Wait for the current run to finish or resolve the pending approval.';
  }
  if (error.status === 429) {
    const wait = error.retryAfter;
    return wait === undefined
      ? 'You are sending messages too fast. Please wait a moment.'
      : `You are sending messages too fast. Try again in ${String(wait)} seconds.`;
  }
  return error.message;
}
