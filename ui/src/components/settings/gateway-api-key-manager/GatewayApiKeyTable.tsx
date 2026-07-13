import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { GatewayApiKey } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { GatewayApiKeyTableRow } from "./GatewayApiKeyTableRow";

type GatewayApiKeyTableProps = {
  locale: Locale;
  gatewayKeys: GatewayApiKey[];
  timeZone: string;
  removingKeyId: string;
  togglingKeyId: string;
  copiedKey: string;
  visibleKey: string;
  onVisibleKeyChange: (keyId: string) => void;
  onCopy: (value: string, itemId: string) => Promise<void>;
  onEdit: (item: GatewayApiKey) => void;
  onRemove: (keyId: string) => Promise<void>;
  onToggle: (item: GatewayApiKey, enabled: boolean) => Promise<void>;
};

/** Renders the gateway API key list and empty state. */
export function GatewayApiKeyTable({
  locale,
  gatewayKeys,
  timeZone,
  removingKeyId,
  togglingKeyId,
  copiedKey,
  visibleKey,
  onVisibleKeyChange,
  onCopy,
  onEdit,
  onRemove,
  onToggle,
}: GatewayApiKeyTableProps) {
  return (
    <div className="min-w-0 rounded-lg border">
      <Table className="min-w-[1120px] table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-40">
              {titleForLocale(locale, "密钥名称", "Key name")}
            </TableHead>
            <TableHead className="w-[420px]">
              {titleForLocale(locale, "密钥", "Key")}
            </TableHead>
            <TableHead className="w-44">
              {titleForLocale(locale, "限额", "Limit")}
            </TableHead>
            <TableHead className="w-44">
              {titleForLocale(locale, "创建时间", "Created")}
            </TableHead>
            <TableHead className="w-56">
              {titleForLocale(locale, "权限", "Permissions")}
            </TableHead>
            <TableHead className="w-36 text-right">
              {titleForLocale(locale, "操作", "Actions")}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {gatewayKeys.length > 0 ? (
            gatewayKeys.map((item) => (
              <GatewayApiKeyTableRow
                key={item.id}
                locale={locale}
                item={item}
                timeZone={timeZone}
                isBusy={removingKeyId === item.id || togglingKeyId === item.id}
                copiedKey={copiedKey}
                visibleKey={visibleKey}
                onVisibleKeyChange={onVisibleKeyChange}
                onCopy={onCopy}
                onEdit={onEdit}
                onRemove={onRemove}
                onToggle={onToggle}
              />
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={6}
                className="py-10 text-center text-sm text-muted-foreground"
              >
                {titleForLocale(locale, "当前没有 API 密钥", "No API keys")}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
