import { createBrowserRouter, type RouteObject } from 'react-router'

import { RequireAuth } from '@/auth/RequireAuth'
import { Landing } from '@/pages/Landing'
import { NotFound } from '@/pages/NotFound'
import { Placeholder } from '@/pages/Placeholder'

// Data-mode routes: https://reactrouter.com/start/data/routing
export const routes: RouteObject[] = [
  { path: '/', element: <Landing /> },
  { path: '/sign-in', element: <Placeholder title="Sign in" task="F5" /> },
  { path: '/sign-up', element: <Placeholder title="Create an account" task="F5" /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/documents', element: <Placeholder title="Documents" task="F6" /> },
      { path: '/documents/:documentId', element: <Placeholder title="Document" task="F7" /> },
      { path: '/notifications', element: <Placeholder title="Notifications" task="F8" /> },
      { path: '/account', element: <Placeholder title="Account" task="F8" /> },
    ],
  },
  { path: '*', element: <NotFound /> },
]

// Created once, outside the React tree, as the docs require:
// https://reactrouter.com/start/data/installation
export const router = createBrowserRouter(routes)
