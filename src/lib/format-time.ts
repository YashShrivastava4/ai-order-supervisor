// Shared timestamp helpers. The backend always sends UTC ISO-8601 strings
// ending in "Z", and this file is the one place that parses and formats them.
// If a timestamp is ever missing its timezone suffix, treat it as UTC rather
// than letting the browser guess and silently show the wrong local time.
export const normalizeUtcTimestamp = (
  value: string | null | undefined
): string | null => {
  if (!value) return null;

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return hasTimezone ? value : `${value}Z`;
};

const parseUtc = (value: string | null | undefined): Date | null => {
  const normalized = normalizeUtcTimestamp(value);
  if (!normalized) return null;

  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

// Full date + time, e.g. "Aug 16, 2026, 5:43 AM"
export const formatDateTime = (
  value: string | null | undefined,
  fallback = "Not available"
): string => {
  const date = parseUtc(value);
  if (!date) return fallback;

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date);
};

// Clock time only, e.g. "5:43 AM"
export const formatTimeOnly = (
  value: string | null | undefined,
  fallback = "No wake-up scheduled"
): string => {
  const date = parseUtc(value);
  if (!date) return fallback;

  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: "UTC",
  }).format(date);
};