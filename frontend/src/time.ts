export type DisplayTimezone = 'Asia/Kolkata' | 'UTC';

function dateTimeParts(value: string, timeZone: DisplayTimezone) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone,
  }).formatToParts(new Date(value));
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find(part => part.type === type)?.value ?? '';
  return {
    date: `${get('day')} ${get('month')} ${get('year')}`,
    time: `${get('hour')}:${get('minute')} ${get('dayPeriod').toUpperCase()}`,
    zone: timeZone === 'UTC' ? 'UTC' : 'IST',
  };
}

export function formatRunTimestamp(value: string, timeZone: DisplayTimezone): string {
  const parts = dateTimeParts(value, timeZone);
  return `${parts.date}, ${parts.time} ${parts.zone}`;
}

export function formatTimelineTimestamp(value: string, timeZone: DisplayTimezone): string {
  const parts = dateTimeParts(value, timeZone);
  return `${parts.date} · ${parts.time} ${parts.zone}`;
}
