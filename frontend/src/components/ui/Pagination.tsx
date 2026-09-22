import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MoreHorizontalIcon,
} from "lucide-react";
import type * as React from "react";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { cn } from "@/lib/classNames";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

function Pagination({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="pagination"
      data-slot="pagination"
      className={cn(
        "mx-auto flex w-full min-w-0 justify-center overflow-x-auto",
        className,
      )}
      {...props}
    />
  );
}

function PaginationContent({
  className,
  ...props
}: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="pagination-content"
      className={cn("flex min-w-max items-center gap-0.5", className)}
      {...props}
    />
  );
}

function PaginationItem({ ...props }: React.ComponentProps<"li">) {
  return <li data-slot="pagination-item" {...props} />;
}

type PaginationLinkProps = {
  isActive?: boolean;
} & Pick<React.ComponentProps<typeof Button>, "size"> &
  React.ComponentProps<"a">;

function PaginationLink({
  className,
  isActive,
  size = "icon",
  ...props
}: PaginationLinkProps) {
  return (
    <Button
      asChild
      variant={isActive ? "outline" : "ghost"}
      size={size}
      className={cn(className)}
    >
      <a
        aria-current={isActive ? "page" : undefined}
        data-slot="pagination-link"
        data-active={isActive}
        {...props}
      />
    </Button>
  );
}

function PaginationPrevious({
  className,
  text = "Previous",
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  return (
    <PaginationLink
      aria-label="Go to previous page"
      size="default"
      className={cn("pl-1.5!", className)}
      {...props}
    >
      <ChevronLeftIcon data-icon="inline-start" />
      <span className="hidden sm:block">{text}</span>
    </PaginationLink>
  );
}

function PaginationNext({
  className,
  text = "Next",
  ...props
}: React.ComponentProps<typeof PaginationLink> & { text?: string }) {
  return (
    <PaginationLink
      aria-label="Go to next page"
      size="default"
      className={cn("pr-1.5!", className)}
      {...props}
    >
      <span className="hidden sm:block">{text}</span>
      <ChevronRightIcon data-icon="inline-end" />
    </PaginationLink>
  );
}

function PaginationEllipsis({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden
      data-slot="pagination-ellipsis"
      className={cn(
        "flex size-8 items-center justify-center [&_svg:not([class*='size-'])]:size-4",
        className,
      )}
      {...props}
    >
      <MoreHorizontalIcon />
      <span className="sr-only">More pages</span>
    </span>
  );
}

export type TablePaginationProps = {
  total: number;
  page: number;
  pageCount: number;
  pageSize: number;
  pageSizeOptions?: readonly number[];
  showPageSize?: boolean;
  summary?: React.ReactNode;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  loading?: boolean;
  className?: string;
  locale: Locale;
};

/** Compact list pagination: summary, prev/next, and a ghost page-size menu. */
export function TablePagination({
  total,
  page,
  pageCount,
  pageSize,
  pageSizeOptions = [25, 50, 100],
  showPageSize = true,
  summary,
  onPageChange,
  onPageSizeChange,
  loading = false,
  className,
  locale,
}: TablePaginationProps) {
  const normalizedPageCount = Math.max(1, pageCount);
  const currentPage = Math.min(Math.max(1, page), normalizedPageCount);
  const pageSizeLabel = (size: number) =>
    titleForLocale(locale, `${size} 条 / 页`, `${size} / page`);

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-1.5 px-0.5 text-xs font-normal text-muted-foreground",
        className,
      )}
    >
      <p>
        {summary ??
          titleForLocale(
            locale,
            `共 ${total} 条，第 ${currentPage} / ${normalizedPageCount} 页`,
            `${total} items, page ${currentPage} / ${normalizedPageCount}`,
          )}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          className="h-5 w-5 text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={loading || page <= 1}
          aria-label={titleForLocale(locale, "上一页", "Previous page")}
          title={titleForLocale(locale, "上一页", "Previous page")}
        >
          <ChevronLeftIcon className="size-4 stroke-1" />
        </Button>
        {showPageSize ? (
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-5 px-1.5 text-xs font-normal text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
                disabled={loading}
              >
                <span>{pageSizeLabel(pageSize)}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-[88px] min-w-[88px] space-y-0.5 p-1"
            >
              {pageSizeOptions.map((value) => (
                <DropdownMenuItem
                  key={value}
                  disabled={loading}
                  onSelect={() => onPageSizeChange(value)}
                  className={cn(
                    "h-6 justify-end px-2 py-0 text-xs font-normal text-muted-foreground focus:bg-muted focus:text-foreground",
                    value === pageSize && "bg-muted/60 text-foreground",
                  )}
                >
                  <span className="inline-flex w-full items-center justify-end tabular-nums">
                    <span>{pageSizeLabel(value)}</span>
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          className="h-5 w-5 text-muted-foreground shadow-none hover:bg-muted hover:text-foreground"
          onClick={() => onPageChange(Math.min(normalizedPageCount, page + 1))}
          disabled={loading || page >= normalizedPageCount}
          aria-label={titleForLocale(locale, "下一页", "Next page")}
          title={titleForLocale(locale, "下一页", "Next page")}
        >
          <ChevronRightIcon className="size-4 stroke-1" />
        </Button>
      </div>
    </div>
  );
}

export {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
};
