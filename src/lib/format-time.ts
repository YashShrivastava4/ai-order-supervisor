// Shared timestamp helpers.
//
// The FastAPI backend always serializes timestamps as UTC ISO-8601 with an
// explicit "Z" (see _format_utc_datetime in backend/app/main.py). This file is
// the single place that interprets those strings, so next_wakeup_at,
// created_at, updated_at, and activity-log created_at all render the same
// way everywhere in the UI.
//
// normalizeUtcTimestamp keeps a defensive fallback: if a timestamp is ever
// missing an explicit timezone suffix, we treat it as UTC rather than
// letting the browser guess (which silently parses it as local time and
// produces an offset display bug).
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