/** Where to go after signing in: the guarded page the visitor was sent from, if it is one of ours. */
export function returnPath(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from
  const ours =
    typeof from === 'string' &&
    from.startsWith('/') &&
    !from.startsWith('//') && // a protocol-relative URL leaves the site
    !/^\/sign-(in|up)\b/.test(from)
  return ours ? from : '/documents'
}
