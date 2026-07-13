import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/Pagination";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { cn } from "@/lib/utils";

type RequestPaginationProps = {
  hasNextPage: boolean;
  locale: Locale;
  page: number;
  paginationItems: readonly (number | "ellipsis")[];
  totalPages: number;
  onPageChange: (page: number) => void;
};

/** Render request log pagination controls. */
export function RequestPagination(props: RequestPaginationProps) {
  const {
    hasNextPage,
    locale,
    page,
    paginationItems,
    totalPages,
    onPageChange,
  } = props;
  if (totalPages <= 1) return null;
  return (
    <Pagination id="requests-pagination" className="justify-center pt-1">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            href="#requests-pagination"
            text={titleForLocale(locale, "上一页", "Prev")}
            onClick={(event) => {
              event.preventDefault();
              if (page > 0) onPageChange(page - 1);
            }}
            className={cn(page === 0 && "pointer-events-none opacity-50")}
          />
        </PaginationItem>
        {paginationItems.map((item, index) => (
          <PaginationItem key={`${item}-${index}`}>
            {item === "ellipsis" ? (
              <PaginationEllipsis />
            ) : (
              <PaginationLink
                href="#requests-pagination"
                size="default"
                isActive={item === page + 1}
                onClick={(event) => {
                  event.preventDefault();
                  if (item !== page + 1) onPageChange(item - 1);
                }}
              >
                {item}
              </PaginationLink>
            )}
          </PaginationItem>
        ))}
        <PaginationItem>
          <PaginationNext
            href="#requests-pagination"
            text={titleForLocale(locale, "下一页", "Next")}
            onClick={(event) => {
              event.preventDefault();
              if (hasNextPage) onPageChange(page + 1);
            }}
            className={cn(!hasNextPage && "pointer-events-none opacity-50")}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}
