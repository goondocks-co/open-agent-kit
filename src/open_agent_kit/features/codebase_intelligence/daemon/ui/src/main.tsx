import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/components/theme-provider'
import { PowerProvider } from '@/hooks/use-power-state'
import { router } from '@/router'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="oak-ui-theme">
      <QueryClientProvider client={queryClient}>
        <PowerProvider>
          <RouterProvider router={router} />
        </PowerProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
