// A number typed by the user: accepts "82,5" as well as "82.5"; 0 when it
// isn't a positive number.
export function parseAmount(text: string | number | undefined | null): number {
  const n = parseFloat(String(text ?? '').replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

// Minutes the user's clock is ahead of UTC (Sydney summer = 660).
export function tzOffsetMinutes(d: Date = new Date()): number {
  return -d.getTimezoneOffset();
}
