import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CrashWalkthrough } from '../ui/CrashWalkthrough';

function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe('CrashWalkthrough', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('moves between steps with Next and Prev', async () => {
    const user = userEvent.setup();
    render(<CrashWalkthrough />);
    expect(screen.getByText('A checkpoint is saved after every step')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Prev' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('The worker crashes mid-tool')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Step 2: Crash' }).closest('li')).toHaveAttribute(
      'aria-current',
      'step',
    );

    await user.click(screen.getByRole('button', { name: 'Prev' }));
    expect(screen.getByText('A checkpoint is saved after every step')).toBeVisible();
  });

  it('advances on its own while autoplay is on', () => {
    mockReducedMotion(false);
    vi.useFakeTimers();
    render(<CrashWalkthrough />);

    act(() => {
      screen.getByRole('button', { name: /autoplay/i }).click();
    });
    act(() => {
      vi.advanceTimersByTime(4100);
    });

    expect(screen.getByText('The worker crashes mid-tool')).toBeVisible();
  });

  it('keeps autoplay off when reduced motion is preferred', () => {
    mockReducedMotion(true);
    vi.useFakeTimers();
    render(<CrashWalkthrough />);

    expect(screen.getByRole('button', { name: /autoplay/i })).toBeDisabled();
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    expect(screen.getByText('A checkpoint is saved after every step')).toBeVisible();
  });
});
