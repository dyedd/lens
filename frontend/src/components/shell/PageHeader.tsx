import type { ReactNode } from "react";
import { cn } from "@/lib/classNames";

type PageHeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

/** Renders a clean page header with title and primary actions. */
export function PageHeader({ title, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-2 pb-1 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="page-title">{title}</h1>
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      ) : null}
    </header>
  );
}
