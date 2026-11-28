import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import { openDemoWorkspace } from '@/api/demo'

import { sessionKey } from './session'

/** Creates the visitor's private demo workspace, signs them in and opens `to`. */
export function useOpenDemo(to = '/documents') {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: openDemoWorkspace,
    onSuccess: (workspace) => {
      queryClient.setQueryData(sessionKey, workspace.user)
      navigate(to)
    },
  })
}
