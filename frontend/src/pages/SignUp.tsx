import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation } from 'react-router'

import { signUp } from '@/api/auth'
import { signUpSchema } from '@/auth/forms'
import { sessionKey } from '@/auth/session'

import { AccountPage, FormAlert } from './account/AccountPage'
import { Field } from './account/Field'
import { applyServerError, type FormProblem } from './account/serverErrors'

export function SignUp() {
  const location = useLocation()
  const queryClient = useQueryClient()
  const [problem, setProblem] = useState<FormProblem | null>(null)
  const form = useForm({
    resolver: zodResolver(signUpSchema),
    defaultValues: { name: '', email: '', password: '' },
  })
  const { errors } = form.formState

  const submit = useMutation({
    mutationFn: signUp,
    meta: { silent: true }, // shown in the form, not as a toast
    // Signed in: the account page sends the visitor on to where they were going.
    onSuccess: ({ user }) => queryClient.setQueryData(sessionKey, user),
    onError: (error) => {
      setProblem(
        applyServerError(error, form.setError, ['name', 'email', 'password'], (e) =>
          e.status === 409 ? 'email' : null,
        ),
      )
    },
  })

  const onSubmit = form.handleSubmit((values) => {
    setProblem(null)
    submit.mutate(values)
  })

  return (
    <AccountPage title="Create an account.">
      <form className="account__form" noValidate onSubmit={onSubmit}>
        <Field label="Name" autoComplete="name" error={errors.name?.message} {...form.register('name')} />
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          inputMode="email"
          spellCheck={false}
          error={errors.email?.message}
          {...form.register('email')}
        />
        <Field
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="8 to 128 characters."
          error={errors.password?.message}
          {...form.register('password')}
        />
        <FormAlert problem={problem} />
        <button
          type="submit"
          className="account__submit"
          aria-disabled={submit.isPending || undefined}
          disabled={submit.isPending}
        >
          {submit.isPending ? 'Creating your account…' : 'Create account'}
        </button>
      </form>
      <p className="account__switch">
        Already have an account?{' '}
        <Link to="/sign-in" state={location.state}>
          Sign in
        </Link>
      </p>
    </AccountPage>
  )
}
