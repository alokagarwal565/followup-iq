// Date-only values ("2026-10-12") are business-timezone calendar days. They are never passed to
// `new Date("YYYY-MM-DD")` in local time, which would shift them by a day west of UTC; they are
// built in UTC and formatted in UTC instead. "Today" always comes from the server (meta.today).

import type { LeadRow } from "./types";

function utcDate(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date));
}

function toDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(day: string, amount: number): string {
  const date = utcDate(day);
  date.setUTCDate(date.getUTCDate() + amount);
  return toDay(date);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((utcDate(to).getTime() - utcDate(from).getTime()) / 86_400_000);
}

const DAY_PARTS = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

export function formatDateOnly(day: string): string {
  const parts = Object.fromEntries(
    DAY_PARTS.formatToParts(utcDate(day)).map((p) => [p.type, p.value]),
  );
  return `${parts.weekday}, ${parts.day} ${parts.month}`;
}

export function formatFullDate(day: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(utcDate(day));
}

/** The calendar day of an instant, in the business timezone. */
export function businessDay(iso: string, timeZone: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone,
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function formatDateTime(iso: string, timeZone: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone,
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  return `${parts.day} ${parts.month}, ${parts.hour}:${parts.minute} ${String(parts.dayPeriod).toLowerCase()}`;
}

export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  })
    .format(new Date(iso))
    .toLowerCase();
}

export function dueLabel(
  row: Pick<LeadRow, "due_state" | "days_overdue" | "next_follow_up_date">,
  today: string,
): string {
  switch (row.due_state) {
    case "overdue":
      return `${row.days_overdue}d overdue`;
    case "today":
      return "Today";
    case "upcoming":
      if (row.next_follow_up_date === addDays(today, 1)) return "Tomorrow";
      return row.next_follow_up_date ? formatDateOnly(row.next_follow_up_date) : "Upcoming";
    default:
      return "No follow-up";
  }
}

export function lastContactLabel(
  iso: string | null | undefined,
  today: string,
  timeZone: string,
): string {
  if (!iso) return "Never contacted";
  const days = daysBetween(businessDay(iso, timeZone), today);
  if (days <= 0) return "Last contact today";
  if (days === 1) return "Last contact yesterday";
  return `Last contact ${days}d ago`;
}

export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function zoneOffsetMs(utcMs: number, timeZone: string): number {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
      .formatToParts(new Date(utcMs))
      .map((p) => [p.type, p.value]),
  );
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return asUtc - utcMs;
}

/** Reads a `datetime-local` value ("2026-10-12T16:05") as business time and returns UTC ISO. */
export function businessLocalToIso(local: string, timeZone: string): string {
  const [day, time] = local.split("T");
  const [year, month, date] = day.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const guess = Date.UTC(year, month - 1, date, hour, minute);
  // Two passes settle the offset correctly even when the guess falls across a DST change.
  const first = guess - zoneOffsetMs(guess, timeZone);
  return new Date(guess - zoneOffsetMs(first, timeZone)).toISOString();
}

/** Current business-local time as a `datetime-local` value, used as the input's max. */
export function businessNowLocal(timeZone: string, now: Date = new Date()): string {
  const shifted = new Date(now.getTime() + zoneOffsetMs(now.getTime(), timeZone));
  return shifted.toISOString().slice(0, 16);
}
