import type { Metadata } from 'next'
import { Noto_Sans_SC, IBM_Plex_Mono } from 'next/font/google'
import './globals.css'
import { AppProviders } from '@/components/app-providers'

const sans = Noto_Sans_SC({ subsets: ['latin'], variable: '--font-sans', weight: ['400', '500', '600', '700'] })
const mono = IBM_Plex_Mono({ subsets: ['latin'], variable: '--font-mono', weight: ['400', '500'] })

export const metadata: Metadata = {
  title: 'Lens',
  description: '渠道、模型组与系统配置管理后台'
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}
