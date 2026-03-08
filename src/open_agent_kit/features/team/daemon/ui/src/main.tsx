import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@oak/ui/components/theme-provider'
import { FontProvider } from '@oak/ui/components/font-provider'
import { DensityProvider } from '@oak/ui/components/density-provider'
import { PowerProvider } from '@oak/ui/hooks/use-power-state'
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
      <FontProvider storageKey="oak-ui-font">
        <DensityProvider storageKey="oak-ui-density">
          <QueryClientProvider client={queryClient}>
            <PowerProvider>
              <RouterProvider router={router} />
            </PowerProvider>
          </QueryClientProvider>
        </DensityProvider>
      </FontProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
