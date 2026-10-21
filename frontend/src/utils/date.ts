// The user's calendar day (YYYY-MM-DD) in their own time zone.
// new Date().toISOString() is UTC: in Australia that puts anything logged
// before ~10-11am on yesterday's date.
export function localDateString(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
