import { api } from '@/api/client'
import type { components } from '@/api/schema'

export type AuthResponse = components['schemas']['AuthResponse']
export type LoginRequest = components['schemas']['LoginRequest']
export type RegisterRequest = components['schemas']['RegisterRequest']

export function signIn(body: LoginRequest): Promise<AuthResponse> {
  return api<AuthResponse>('/auth/login', { method: 'POST', body })
}

export function signUp(body: RegisterRequest): Promise<AuthResponse> {
  return api<AuthResponse>('/auth/register', { method: 'POST', body })
}
