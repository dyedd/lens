import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/Item";

/** Render a compact backup preview metadata item. */
export function ConfigPreviewMeta({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <Item variant="muted" size="sm">
      <ItemContent>
        <ItemDescription className="text-[11px] uppercase tracking-[0.08em]">
          {label}
        </ItemDescription>
        <ItemTitle>{value}</ItemTitle>
      </ItemContent>
    </Item>
  );
}
