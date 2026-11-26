import { cn } from "@/lib/classNames";

function LoadingMark({ className }: { className?: string }) {
  return (
    <div
      className={cn("flex flex-col items-center gap-3.5", className)}
      aria-hidden="true"
    >
      <img
        src="/logo.svg"
        alt=""
        width={36}
        height={36}
        className="size-9 rounded-xl object-contain"
        fetchPriority="high"
      />
      <div className="h-0.5 w-20 overflow-hidden rounded-full bg-border/65">
        <div className="animate-lens-progress h-full w-2/5 rounded-full bg-primary" />
      </div>
    </div>
  );
}

/** Render the full-screen application loading state. */
export function AppLoadingScreen({ label = "Loading..." }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-dvh items-center justify-center bg-background select-none"
    >
      <div className="animate-lens-reveal flex flex-col items-center text-center">
        <LoadingMark />
        <span className="sr-only">{label}</span>
      </div>
    </div>
  );
}
