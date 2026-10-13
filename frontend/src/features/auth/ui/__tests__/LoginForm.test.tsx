import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { api } from '@/shared/api/axios-instance';
import { LoginForm } from '../LoginForm';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

function renderForm() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LoginForm />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function submitCredentials() {
  await userEvent.type(screen.getByLabelText('Email'), 'a@b.co');
  await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('LoginForm', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the backend message when the credentials are wrong', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(
      new ApiError('Invalid email or password', 401, { code: 'unauthorized' }),
    );
    renderForm();

    await submitCredentials();

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });

  it('explains an unreachable server instead of the transport message', async () => {
    vi.spyOn(api, 'post').mockRejectedValue(new ApiError('Unable to reach the server', 0));
    renderForm();

    await submitCredentials();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to reach the server. Check your connection and try again.',
    );
  });

  it('flags empty fields with described, invalid inputs', async () => {
    renderForm();

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    const email = screen.getByLabelText('Email');
    expect(email).toHaveAttribute('aria-invalid', 'true');
    expect(email).toHaveAccessibleDescription('Please enter a valid email address');
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription('Password is required');
  });

  it('reveals and hides the password', async () => {
    renderForm();
    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('type', 'password');

    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');

    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });
});
