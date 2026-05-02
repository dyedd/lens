"use client"

import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useI18n } from '@/lib/i18n'
import { useTheme } from '@/lib/theme-context'

export function ThemeToggle() {
  const { locale } = useI18n()
  const { toggleTheme } = useTheme()
  const label = locale === 'zh-CN' ? '切换明暗模式' : 'Toggle theme'

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          onClick={toggleTheme}
        >
          <Moon className="dark:hidden" />
          <Sun className="hidden dark:block" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  )
}
