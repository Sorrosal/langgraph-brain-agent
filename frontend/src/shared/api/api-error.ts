import { z } from 'zod';

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().nullish(),
  }),
});

export interface ApiErrorOptions {
  code?: string | undefined;
  requestId?: string | undefined;
  /** Seconds to wait before retrying (429 `Retry-After`). */
  retryAfter?: number | undefined;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly requestId: string | undefined;
  readonly retryAfter: number | undefined;

  constructor(message: string, status: number, options: ApiErrorOptions = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = options.code;
    this.requestId = options.requestId;
    this.retryAfter = options.retryAfter;
  }

  static isApiError(error: unknown): error is ApiError {
    return error instanceof ApiError;
  }
}

/** Build an ApiError from a response body of the shape `{"error": {"code", "message"}}`. */
export function parseApiError(
  status: number,
  body: unknown,
  fallbackMessage: string,
  retryAfter?: string,
): ApiError {
  const parsed = errorEnvelopeSchema.safeParse(body);
  const seconds = retryAfter === undefined ? Number.NaN : Number(retryAfter);
  const options: ApiErrorOptions = {
    retryAfter: Number.isFinite(seconds) ? seconds : undefined,
  };
  if (!parsed.success) return new ApiError(fallbackMessage, status, options);
  const { code, message, request_id } = parsed.data.error;
  return new ApiError(message, status, { ...options, code, requestId: request_id ?? undefined });
}
