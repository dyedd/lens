import { Database } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import {
  Item,
  ItemContent,
  ItemGroup,
  ItemHeader,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/Item";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

export type ConfigImportResultRow = {
  key: string;
  label: string;
  value: number;
};

/** Render affected row counts from a completed backup import. */
export function ConfigImportResultSummary({
  rows,
  locale,
}: {
  rows: ConfigImportResultRow[];
  locale: Locale;
}) {
  if (!rows.length) {
    return null;
  }

  return (
    <Card className="py-0">
      <CardContent className="flex flex-col gap-3 p-4">
        <Item variant="muted" size="sm">
          <ItemMedia variant="icon">
            <Database />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>
              {titleForLocale(locale, "导入结果", "Import result")}
            </ItemTitle>
          </ItemContent>
        </Item>
        <ItemGroup className="gap-2">
          {rows.map((item) => (
            <Item key={item.key} variant="outline" size="sm">
              <ItemContent>
                <ItemHeader>
                  <ItemTitle className="font-medium">{item.label}</ItemTitle>
                  <Badge variant="secondary">{item.value}</Badge>
                </ItemHeader>
              </ItemContent>
            </Item>
          ))}
        </ItemGroup>
      </CardContent>
    </Card>
  );
}
