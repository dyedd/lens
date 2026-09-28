import { useMemo, useState } from "react";

/** Tracks checkbox selection over a row list keyed by `getId`. */
export function useRowSelection<Row, Id extends string | number>(
  rows: Row[],
  getId: (row: Row) => Id,
) {
  const [selected, setSelected] = useState<Set<Id>>(() => new Set());
  const selectedRows = useMemo(
    () => rows.filter((row) => selected.has(getId(row))),
    [getId, rows, selected],
  );

  function toggleRows(targets: Row[], checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const row of targets) {
        if (checked) next.add(getId(row));
        else next.delete(getId(row));
      }
      return next;
    });
  }

  function toggleId(id: Id, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  return {
    selected,
    selectedRows,
    toggleRows,
    toggleId,
    clear: () => setSelected(new Set()),
  };
}
