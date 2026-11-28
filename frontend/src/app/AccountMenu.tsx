import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DropdownMenu } from 'radix-ui'
import { toast } from 'sonner'
import { useNavigate } from 'react-router'

import { api } from '@/api/client'
import { currentWorkspace, switchAccount } from '@/api/demo'
import { sessionKey, useSession } from '@/auth/session'
import { timeAgo } from '@/lib/time'

/** Who is signed in; a demo visitor can become the workspace's other people; Sign out. */
export function AccountMenu() {
  const session = useSession()
  const user = session.data
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // 404 for a real account: then there is simply no switch to offer.
  const workspace = useQuery({
    queryKey: ['demo-workspace', user?.id],
    queryFn: ({ signal }) => currentWorkspace(signal),
    enabled: Boolean(user),
    retry: false,
    staleTime: 5 * 60_000,
    meta: { silent: true },
  })

  const switchTo = useMutation({
    mutationFn: switchAccount,
    onSuccess: ({ user: next }) => {
      queryClient.setQueryData(sessionKey, next)
      // Everything else was seen as the previous person.
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'session' })
      toast.success(`You are now ${next.name}.`)
    },
  })

  const signOut = useMutation({
    mutationFn: () => api('/auth/logout', { method: 'POST' }),
    onSuccess: () => {
      navigate('/', { replace: true })
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' })
      queryClient.setQueryData(sessionKey, null)
    },
  })

  if (!user) return null
  const others = workspace.data?.accounts.filter((a) => a.user_id !== user.id) ?? []

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className="tag app-header__account" aria-label={`Account menu: ${user.name}`}>
        <span className="app-header__initial" aria-hidden="true">
          {user.name.slice(0, 1)}
        </span>
        {user.name}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className="menu" align="end" sideOffset={8}>
          <DropdownMenu.Label className="menu__label">
            Signed in as <strong>{user.name}</strong>
            {workspace.data && (
              <span className="menu__note">
                Demo workspace, deleted {timeAgo(workspace.data.workspace.expires_at)}
              </span>
            )}
          </DropdownMenu.Label>
          {others.length > 0 && (
            <>
              <DropdownMenu.Separator className="menu__separator" />
              <DropdownMenu.Group>
                {others.map((account) => (
                  <DropdownMenu.Item
                    key={account.user_id}
                    className="menu__item"
                    disabled={switchTo.isPending}
                    onSelect={() => switchTo.mutate(account.user_id)}
                  >
                    Switch to {account.name}
                  </DropdownMenu.Item>
                ))}
              </DropdownMenu.Group>
            </>
          )}
          <DropdownMenu.Separator className="menu__separator" />
          <DropdownMenu.Item className="menu__item" onSelect={() => navigate('/account')}>
            Account
          </DropdownMenu.Item>
          <DropdownMenu.Item className="menu__item" onSelect={() => signOut.mutate()}>
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
