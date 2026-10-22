/**
 * Timezone utilities for StayTrack.
 *
 * Ensures all timestamps across the application are parsed and rendered consistently
 * in America/New_York (Eastern Time: EDT in summer/fall, EST in winter),
 * regardless of the visitor's local system timezone.
 */

export const NY_TIMEZONE = 'America/New_York';

/**
 * Safely parses any date representation into a Date object.
 * If the input is an ISO string without a timezone offset (naive UTC from DB),
 * it appends 'Z' so JavaScript treats it as UTC rather than device local time.
 */
export const parseToDate = (input?: string | number | Date | null): Date | null => {
  if (input === null || input === undefined || input === '') {
    return null;
  }
  if (input instanceof Date) {
    return isNaN(input.getTime()) ? null : input;
  }
  if (typeof input === 'number') {
    const d = new Date(input);
    return isNaN(d.getTime()) ? null : d;
  }

  let str = String(input).trim();
  // If naive ISO datetime without timezone indicator (e.g. "2026-10-22T14:15:30.123456" or "2026-10-22 14:15:30")
  if (str.includes('T') || (str.includes('-') && str.includes(':'))) {
    str = str.replace(' ', 'T');
    if (!str.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(str)) {
      str = str + 'Z';
    }
  }

  const parsed = new Date(str);
  return isNaN(parsed.getTime()) ? null : parsed;
};

/**
 * Formats a date/timestamp into a New York date & time string.
 * e.g. "Oct 16, 2026, 8:37 AM EDT"
 */
export const formatNYDateTime = (
  input?: string | number | Date | null,
  options?: Intl.DateTimeFormatOptions
): string => {
  const date = parseToDate(input);
  if (!date) return input ? String(input) : '—';

  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: NY_TIMEZONE,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short',
      ...options,
    }).format(date);
  } catch (e) {
    return date.toLocaleString();
  }
};

/**
 * Formats a date into a New York date string.
 * e.g. "Oct 16, 2026"
 */
export const formatNYDate = (
  input?: string | number | Date | null,
  options?: Intl.DateTimeFormatOptions
): string => {
  const date = parseToDate(input);
  if (!date) return input ? String(input) : '—';

  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: NY_TIMEZONE,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...options,
    }).format(date);
  } catch (e) {
    return date.toLocaleDateString();
  }
};

/**
 * Formats a time into a New York time string.
 * e.g. "8:37 AM EDT"
 */
export const formatNYTime = (
  input?: string | number | Date | null,
  options?: Intl.DateTimeFormatOptions
): string => {
  const date = parseToDate(input);
  if (!date) return input ? String(input) : '—';

  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: NY_TIMEZONE,
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short',
      ...options,
    }).format(date);
  } catch (e) {
    return date.toLocaleTimeString();
  }
};

/**
 * Returns today's date formatted as YYYY-MM-DD in New York time.
 * Essential for upload default date to prevent UTC next-day rollover at night.
 */
export const getTodayNYDateString = (): string => {
  try {
    // en-CA formats as YYYY-MM-DD
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: NY_TIMEZONE,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date());
  } catch (e) {
    return new Date().toISOString().split('T')[0];
  }
};

/**
 * Returns live New York clock display string.
 * e.g. "Oct 22, 10:25 AM EDT"
 */
export const getCurrentNYTimeDisplay = (): string => {
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: NY_TIMEZONE,
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZoneName: 'short',
    }).format(new Date());
  } catch (e) {
    return new Date().toLocaleTimeString();
  }
};
