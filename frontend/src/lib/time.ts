const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const exact = new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })

const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 3600],
  ['month', 30 * 24 * 3600],
  ['week', 7 * 24 * 3600],
  ['day', 24 * 3600],
  ['hour', 3600],
  ['minute', 60],
]

/** "2 hours ago", "yesterday"; anything under a minute is "just now". */
export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

/** "28 Nov 2026, 09:14", for a tooltip and the `<time>` element's meaning. */
export function exactTime(iso: string): string {
  return exact.format(new Date(iso))
}

export function isWithinLastDay(iso: string, now = Date.now()): boolean {
  return now - new Date(iso).getTime() < 24 * 3600 * 1000
}
