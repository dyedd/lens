"use client"

import { Globe2 } from 'lucide-react'
import Image from 'next/image'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { FormEvent, useState } from 'react'
import { ApiError, apiRequest, type PublicBranding } from '@/lib/api'
import { setStoredToken } from '@/lib/auth'
import { useI18n } from '@/lib/i18n'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

type LoginResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export function LoginScreen() {
  const router = useRouter()
  const { locale, setLocale, t } = useI18n()
  const { data: branding } = useQuery({ queryKey: ['public-branding'], queryFn: () => apiRequest<PublicBranding>('/public/branding') })
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const siteName = branding?.site_name?.trim() || 'Lens'
  const logoUrl = branding?.logo_url?.trim() || '/logo.svg'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const data = await apiRequest<LoginResponse>('/admin/session', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      })
      setStoredToken(data.access_token)
      router.push('/dashboard')
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="absolute right-6 top-6">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={() => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN')}
        >
          <Globe2 data-icon="inline-start" />
          <span>{locale === 'zh-CN' ? 'English' : '中文'}</span>
        </Button>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-6">
        <header className="flex flex-col items-center gap-3 text-center">
          <div className="relative size-20 overflow-hidden">
            <Image src={logoUrl} alt={siteName} fill className="object-contain" unoptimized={logoUrl !== '/logo.svg'} />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{siteName}</h1>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>{locale === 'zh-CN' ? '登录你的账户' : 'Login to your account'}</CardTitle>
            <CardDescription>
              {locale === 'zh-CN' ? '输入用户名和密码继续' : 'Enter your username and password to continue'}
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={submit} className="grid gap-5">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-foreground">{t.username}</span>
                <Input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder={t.username}
                  autoComplete="username"
                />
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-foreground">{t.password}</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={t.password}
                  autoComplete="current-password"
                />
              </label>

              {error ? <p className="text-sm text-destructive">{error}</p> : null}

              <Button className="h-10 w-full" type="submit" disabled={submitting}>
                {submitting ? t.signingIn : t.signIn}
              </Button>
            </form>
          </CardContent>
        </Card>

        <footer className="text-center text-xs text-muted-foreground">
          <a
            href="https://github.com/dyedd/lens"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-foreground hover:underline"
          >
            powered by lens
          </a>
        </footer>
      </div>
    </div>
  )
}
