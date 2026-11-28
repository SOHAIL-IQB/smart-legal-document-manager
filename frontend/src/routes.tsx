import { createBrowserRouter, type RouteObject } from 'react-router'

import { RequireAuth } from '@/auth/RequireAuth'
import { Landing } from '@/pages/Landing'
import { NotFound } from '@/pages/NotFound'
import { Placeholder } from '@/pages/Placeholder'

// Data-mode routes: https://reactrouter.com/start/data/routing
export const routes: RouteObject[] = [
  { path: '/', element: <Landing /> },
  // The account pages carry the form libraries, so they load when visited, not with the landing page:
  // https://reactrouter.com/start/data/route-object#lazy
  { path: '/sign-in', lazy: async () => ({ Component: (await import('@/pages/SignIn')).SignIn }) },
  { path: '/sign-up', lazy: async () => ({ Component: (await import('@/pages/SignUp')).SignUp }) },
  {
    element: <RequireAuth />,
    children: [
      {
        // The signed-in app (header, palette, dialogs) loads once someone is signed in.
        lazy: async () => ({ Component: (await import('@/app/AppLayout')).AppLayout }),
        children: [
          {
            path: '/documents',
            lazy: async () => ({ Component: (await import('@/pages/Documents')).Documents }),
          },
          {
            path: '/documents/:documentId',
            lazy: async () => ({ Component: (await import('@/pages/DocumentPage')).DocumentPage }),
          },
          { path: '/notifications', element: <Placeholder title="Notifications" task="F8" /> },
          { path: '/account', element: <Placeholder title="Account" task="F8" /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFound /> },
]

// Created once, outside the React tree, as the docs require:
// https://reactrouter.com/start/data/installation
export const router = createBrowserRouter(routes)
