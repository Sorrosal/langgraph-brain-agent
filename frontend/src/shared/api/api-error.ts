export interface ApiErrorData {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly details: Record<string, unknown> | undefined;

  constructor(message: string, status: number, data?: ApiErrorData) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = data?.code;
    this.details = data?.details;
  }

  static isApiError(error: unknown): error is ApiError {
    return error instanceof ApiError;
  }
}
