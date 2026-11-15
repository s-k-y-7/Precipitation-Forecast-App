import { describe, expect, it } from 'vitest';
import { formatRunTimestamp, formatTimelineTimestamp } from './time';

describe('forecast timestamp formatting', () => {
  const timestamp = '2026-11-14T18:30:00Z';

  it('formats the same instant in IST and UTC with the correct day rollover', () => {
    expect(formatTimelineTimestamp(timestamp, 'Asia/Kolkata')).toBe('15 Nov 2026 · 12:00 AM IST');
    expect(formatTimelineTimestamp(timestamp, 'UTC')).toBe('14 Nov 2026 · 6:30 PM UTC');
  });

  it('formats run timestamps in the selected timezone', () => {
    expect(formatRunTimestamp(timestamp, 'Asia/Kolkata')).toBe('15 Nov 2026, 12:00 AM IST');
    expect(formatRunTimestamp(timestamp, 'UTC')).toBe('14 Nov 2026, 6:30 PM UTC');
  });
});
