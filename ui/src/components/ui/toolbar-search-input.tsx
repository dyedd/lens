"use client"

import { Search, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export function ToolbarSearchInput({
  value,
  onChange,
  onClear,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  onClear: () => void
  placeholder: string
  className?: string
}) {
  return (
    <div className={cn("relative w-full max-w-sm", className)}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-9 bg-background pl-9 pr-9"
      />
      {value ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="absolute top-1/2 right-1 -translate-y-1/2 rounded-full"
          onClick={onClear}
        >
          <X />
        </Button>
      ) : null}
    </div>
  )
}
