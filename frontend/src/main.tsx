import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router/dom'
import { Toaster } from 'sonner'

import './index.css'

import { createQueryClient } from '@/lib/queryClient'
import { router } from '@/routes'

const queryClient = createQueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster
        toastOptions={{
          // A washi slip: the grain and a paper shadow (colours come from index.css).
          style: {
            backgroundImage: 'var(--grain-ground)',
            boxShadow: '0 2px 4px rgb(70 20 12 / 0.18), 0 14px 30px -12px rgb(70 20 12 / 0.45)',
            fontSize: '0.9375rem',
          },
        }}
      />
    </QueryClientProvider>
  </StrictMode>,
)
