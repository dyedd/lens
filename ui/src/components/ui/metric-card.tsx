import { LucideIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function MetricCard({
  icon: Icon,
  label,
  value,
  tone = 'default',
  className,
}: {
  icon: LucideIcon
  label: string
  value: React.ReactNode
  tone?: 'default' | 'accent' | 'danger'
  className?: string
}) {
  return (
    <Card className={cn("py-0", className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-4 px-5 pt-5 pb-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <span
          className={cn(
            'flex size-9 items-center justify-center rounded-md border bg-muted',
            tone === 'accent' ? 'bg-primary/10 text-primary' :
            tone === 'danger' ? 'bg-destructive/10 text-destructive' :
            'text-foreground'
          )}
        >
          <Icon className="size-4.5" strokeWidth={2.25} />
        </span>
      </CardHeader>
      <CardContent className="px-5 pt-4 pb-5">
        <div
          className={cn(
            'text-2xl font-semibold tracking-tight',
            tone === 'accent' ? 'text-primary' :
            tone === 'danger' ? 'text-destructive' :
            'text-foreground'
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  )
}
