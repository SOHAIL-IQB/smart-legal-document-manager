import { z } from 'zod'

// The API's own limits (app/schemas/user.py), checked here first so mistakes show without a request.
const isEmail = (value: string) => z.email().safeParse(value).success
const email = z
  .string()
  .trim()
  .min(1, 'Enter your email address.')
  .refine((value) => value === '' || isEmail(value), 'Enter a valid email address, like name@example.com.')

export const signInSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password.').max(128, 'Use at most 128 characters.'),
})

export const signUpSchema = z.object({
  name: z.string().trim().min(1, 'Enter your name.').max(255, 'Use at most 255 characters.'),
  email,
  password: z.string().min(8, 'Use at least 8 characters.').max(128, 'Use at most 128 characters.'),
})

export type SignInValues = z.infer<typeof signInSchema>
export type SignUpValues = z.infer<typeof signUpSchema>
