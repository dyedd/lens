import Image from "next/image";

import { cn } from "@/lib/utils";

function LoadingMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative flex size-14 items-center justify-center",
        className,
      )}
      aria-hidden="true"
    >
      <span className="absolute inset-0 rounded-full border-2 border-primary/[0.18]" />
      <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary border-r-primary animate-spin" />
      <span className="absolute inset-1 rounded-full border border-border/60 bg-background shadow-sm" />
      <Image
        src="/logo.svg"
        alt=""
        width={30}
        height={30}
        className="relative z-10"
        priority
      />
    </span>
  );
}

/** Render the full-screen application loading state. */
export function AppLoadingScreen({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3 text-center">
        <LoadingMark />
        <div className="text-base font-medium text-primary">{label}</div>
      </div>
    </div>
  );
}
