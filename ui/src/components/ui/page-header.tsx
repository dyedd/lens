import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <Card className="py-0">
      <CardContent className="p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium uppercase tracking-[0.18em] text-primary">
              {eyebrow}
            </Badge>
            <h2 className="mt-3 text-2xl font-semibold leading-tight text-foreground sm:text-3xl">{title}</h2>
            {description ? <p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className={cn('flex w-full flex-wrap items-center gap-2 sm:w-auto sm:gap-3')}>{actions}</div> : null}
        </div>
      </CardContent>
    </Card>
  )
}
