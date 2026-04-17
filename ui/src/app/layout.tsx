import type { Metadata } from 'next'
import { Geist, Geist_Mono, Noto_Serif } from 'next/font/google'
import './globals.css'
import { AppProviders } from '@/components/app-providers'
import { cn } from '@/lib/utils'

const notoSerif = Noto_Serif({subsets:['latin'],variable:'--font-serif'});

const notoSerifHeading = Noto_Serif({subsets:['latin'],variable:'--font-heading'});

const sans = Geist({ subsets: ['latin'], variable: '--font-sans', weight: ['400', '500', '600', '700'] })
const geistMono = Geist_Mono({subsets:['latin'],variable:'--font-mono'})

export const metadata: Metadata = {
  title: 'Lens',
  description: '渠道、模型组与系统配置管理后台',
  icons: {
    icon: '/logo.svg',
    shortcut: '/logo.svg',
    apple: '/logo.svg',
  },
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={cn(sans.variable, geistMono.variable, notoSerifHeading.variable, notoSerif.variable)}>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}
