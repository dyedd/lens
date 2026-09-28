import { useMemo, useState } from "react";

/** Slices an in-memory row list into pages for `TablePagination`. */
export function useClientPagination<Row>(rows: Row[], initialPageSize = 25) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pageRows = useMemo(
    () => rows.slice((safePage - 1) * pageSize, safePage * pageSize),
    [pageSize, rows, safePage],
  );

  return {
    pageRows,
    resetPage: () => setPage(1),
    paginationProps: {
      total: rows.length,
      page: safePage,
      pageCount,
      pageSize,
      onPageChange: setPage,
      onPageSizeChange: (size: number) => {
        setPageSize(size);
        setPage(1);
      },
    },
  };
}
