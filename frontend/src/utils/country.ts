// The phone's country from its region settings ("en-AU" → "AU"), or '' when
// unknown. Food lookups use it so an Australian Big Mac isn't the US one.
export function phoneCountry(): string {
  try {
    const locale = Intl.DateTimeFormat().resolvedOptions().locale || '';
    const m = locale.match(/[-_]([A-Za-z]{2})\b/);
    return m ? m[1].toUpperCase() : '';
  } catch {
    return '';
  }
}
