import { describe, expect, it } from 'vitest';
import { formatDueDate, isOverdue } from '../due';

describe('formatDueDate', () => {
  it('keeps a bare date on its calendar day whatever the time zone', () => {
    expect(formatDueDate('2026-01-05')).toBe('Jan 5, 2026');
  });
});

describe('isOverdue', () => {
  const now = Date.parse('2026-01-05T12:00:00Z');

  it('treats a date due today as still on time and yesterday as overdue', () => {
    expect(isOverdue({ status: 'open', due_date: '2026-01-05' }, now)).toBe(false);
    expect(isOverdue({ status: 'open', due_date: '2026-01-04' }, now)).toBe(true);
  });

  it('compares full timestamps exactly', () => {
    expect(isOverdue({ status: 'open', due_date: '2026-01-05T11:00:00Z' }, now)).toBe(true);
    expect(isOverdue({ status: 'open', due_date: '2026-01-05T13:00:00Z' }, now)).toBe(false);
  });

  it('never flags done tasks or tasks without a due date', () => {
    expect(isOverdue({ status: 'done', due_date: '2020-01-01' }, now)).toBe(false);
    expect(isOverdue({ status: 'open', due_date: null }, now)).toBe(false);
  });
});
