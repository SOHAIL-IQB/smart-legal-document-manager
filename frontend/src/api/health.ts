import type { operations } from './schema'

// Typed from the API's own schema (src/api/schema.d.ts), so a changed response shape fails the build.
export type Readiness =
  operations['readiness_api_health_ready_get']['responses'][200]['content']['application/json']

/** The API's readiness: `{ status, database }` when it can serve traffic. */
export async function fetchReadiness(signal?: AbortSignal): Promise<Readiness> {
  const response = await fetch('/api/health/ready', {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`The API is not ready (HTTP ${response.status}).`)
  }
  return (await response.json()) as Readiness
}
