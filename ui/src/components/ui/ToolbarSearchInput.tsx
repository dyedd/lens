"use client";

import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils";

/** Dummy form owner so nested toolbar search never submits a parent <form>. */
const TOOLBAR_SEARCH_FORM_ID = "lens-toolbar-search-unbound";

/** Render a toolbar search field with an optional clear action. */
export function ToolbarSearchInput({
  value,
  onChange,
  onClear,
  placeholder,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  placeholder: string;
  className?: string;
}) {
  return (
    <div
      data-toolbar-search=""
      className={cn("relative w-full max-w-sm", className)}
    >
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        // Detach from ancestor forms so Enter cannot trigger channel/group submit.
        form={TOOLBAR_SEARCH_FORM_ID}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.nativeEvent.isComposing || event.key !== "Enter") return;
          event.preventDefault();
          event.stopPropagation();
        }}
        placeholder={placeholder}
        autoComplete="off"
        enterKeyHint="search"
        className="h-8 bg-background pl-9 pr-9"
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
  );
}
