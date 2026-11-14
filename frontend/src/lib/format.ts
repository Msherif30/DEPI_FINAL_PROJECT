export function money(value: number | string | null | undefined, currency = "EGP"): string {
  const num = typeof value === "string" ? Number(value) : value ?? 0;
  return `${Number(num || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })} ${currency}`;
}

export function number(value: number | string | null | undefined, digits = 0): string {
  const num = typeof value === "string" ? Number(value) : value ?? 0;
  return Number(num || 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

export function dateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function day(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function daysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return isoDate(d);
}

export function statusTone(status: string): string {
  switch (status) {
    case "pending":
      return "bg-amber-100 text-amber-800 ring-amber-200";
    case "confirmed":
      return "bg-sky-100 text-sky-800 ring-sky-200";
    case "preparing":
      return "bg-violet-100 text-violet-800 ring-violet-200";
    case "completed":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "cancelled":
      return "bg-rose-100 text-rose-800 ring-rose-200";
    case "paid":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "unpaid":
      return "bg-ink-100 text-ink-700 ring-ink-200";
    case "refunded":
    case "partially_refunded":
      return "bg-orange-100 text-orange-800 ring-orange-200";
    case "failed":
      return "bg-rose-100 text-rose-800 ring-rose-200";
    case "ok":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "low":
      return "bg-amber-100 text-amber-800 ring-amber-200";
    case "critical":
      return "bg-rose-100 text-rose-800 ring-rose-200";
    default:
      return "bg-ink-100 text-ink-700 ring-ink-200";
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
