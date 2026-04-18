"use client"

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { I18nProvider } from '@/lib/i18n'
import { ToastProvider } from '@/components/ui/toast'
import { Toaster as SonnerToaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60_000,
          gcTime: 15 * 60_000,
          refetchOnWindowFocus: false,
          refetchOnReconnect: false,
          refetchOnMount: false,
        retry: 1,
      },
    },
  }))
  return (
    <QueryClientProvider client={client}>
      <I18nProvider>
        <TooltipProvider>
          <ToastProvider>
            {children}
            <SonnerToaster />
          </ToastProvider>
        </TooltipProvider>
      </I18nProvider>
    </QueryClientProvider>
  )
}
