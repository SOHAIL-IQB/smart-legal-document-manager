import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation } from 'react-router'

import { signIn } from '@/api/auth'
import { signInSchema } from '@/auth/forms'
import { sessionKey } from '@/auth/session'

import { AccountPage, FormAlert } from './account/AccountPage'
import { Field } from '@/components/Field'
import { applyServerError, type FormProblem } from './account/serverErrors'

export function SignIn() {
  const location = useLocation()
  const queryClient = useQueryClient()
  const [problem, setProblem] = useState<FormProblem | null>(null)
  const form = useForm({
    resolver: zodResolver(signInSchema),
    defaultValues: { email: '', password: '' },
  })
  const { errors } = form.formState

  const submit = useMutation({
    mutationFn: signIn,
    meta: { silent: true }, // shown in the form, not as a toast
    // Signed in: the account page sends the visitor on to where they were going.
    onSuccess: ({ user }) => queryClient.setQueryData(sessionKey, user),
    onError: (error) => {
      form.resetField('password')
      const formProblem = applyServerError(error, form.setError, ['email', 'password'])
      setProblem(formProblem)
      if (formProblem) form.setFocus('password') // a field error already took focus to its field
    },
  })

  const onSubmit = form.handleSubmit((values) => {
    setProblem(null)
    submit.mutate(values)
  })

  return (
    <AccountPage title="Sign in.">
      <form className="account__form" noValidate onSubmit={onSubmit}>
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
          autoComplete="current-password"
          error={errors.password?.message}
          {...form.register('password')}
        />
        <FormAlert problem={problem} />
        <button
          type="submit"
          className="button-primary"
          aria-disabled={submit.isPending || undefined}
          disabled={submit.isPending}
        >
          {submit.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="account__switch">
        New here?{' '}
        <Link to="/sign-up" state={location.state}>
          Create an account
        </Link>
      </p>
    </AccountPage>
  )
}
