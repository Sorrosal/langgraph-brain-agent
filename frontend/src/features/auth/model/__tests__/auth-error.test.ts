import { describe, expect, it } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { authErrorMessage } from '../auth-error';

describe('authErrorMessage', () => {
  it('maps a missing response to the network message', () => {
    expect(authErrorMessage(new ApiError('Unable to reach the server', 0), 'login')).toMatch(
      /Unable to reach the server\. Check your connection/,
    );
  });

  it('words a 401 differently for sign-in and sign-up', () => {
    const error = new ApiError('Invalid email or password', 401);
    expect(authErrorMessage(error, 'login')).toBe('Invalid email or password');
    expect(authErrorMessage(error, 'register')).toMatch(/couldn't create your account/);
  });

  it('pluralises the retry delay on 429', () => {
    expect(authErrorMessage(new ApiError('slow down', 429, { retryAfter: 1 }), 'login')).toMatch(
      /in 1 second\./,
    );
    expect(authErrorMessage(new ApiError('slow down', 429, { retryAfter: 30 }), 'login')).toMatch(
      /in 30 seconds\./,
    );
    expect(authErrorMessage(new ApiError('slow down', 429), 'login')).toMatch(/wait a moment/);
  });

  it('keeps enveloped server messages and hides transport fallbacks', () => {
    expect(
      authErrorMessage(new ApiError('Email blocked', 403, { code: 'forbidden' }), 'login'),
    ).toBe('Email blocked');
    expect(authErrorMessage(new ApiError('Request failed with status 500', 500), 'login')).toBe(
      'Something went wrong. Please try again.',
    );
    expect(authErrorMessage(new Error('boom'), 'login')).toBe(
      'Something went wrong. Please try again.',
    );
  });
});
