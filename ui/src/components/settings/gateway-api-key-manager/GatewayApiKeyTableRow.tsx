import { Check, Copy, Eye, EyeOff, Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import { TableCell, TableRow } from "@/components/ui/Table";
import type { GatewayApiKey } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  formatDateOnly,
  formatDateTime,
  formatGatewayAmount,
  formatGatewayLimit,
  isGatewayKeyExpired,
  isGatewayKeyOutOfBalance,
  maskGatewayKey,
} from "./gatewayApiKeyUtils";

type GatewayApiKeyTableRowProps = {
  locale: Locale;
  item: GatewayApiKey;
  timeZone: string;
  isBusy: boolean;
  copiedKey: string;
  visibleKey: string;
  onVisibleKeyChange: (keyId: string) => void;
  onCopy: (value: string, itemId: string) => Promise<void>;
  onEdit: (item: GatewayApiKey) => void;
  onRemove: (keyId: string) => Promise<void>;
  onToggle: (item: GatewayApiKey, enabled: boolean) => Promise<void>;
};

/** Renders one gateway API key with its status, permissions, and actions. */
export function GatewayApiKeyTableRow({
  locale,
  item,
  timeZone,
  isBusy,
  copiedKey,
  visibleKey,
  onVisibleKeyChange,
  onCopy,
  onEdit,
  onRemove,
  onToggle,
}: GatewayApiKeyTableRowProps) {
  const isExpired = isGatewayKeyExpired(item);
  const isOutOfBalance = isGatewayKeyOutOfBalance(item);
  const isVisible = visibleKey === item.id;

  return (
    <TableRow>
      <TableCell className="min-w-0">
        <div className="flex min-w-36 flex-col gap-2">
          <div className="truncate text-sm text-foreground">
            {item.remark || titleForLocale(locale, "未命名", "Unnamed")}
          </div>
          {isExpired || isOutOfBalance ? (
            <div className="flex flex-wrap gap-1">
              {isExpired ? (
                <Badge variant="destructive">
                  {titleForLocale(locale, "已过期", "Expired")}
                </Badge>
              ) : null}
              {isOutOfBalance ? (
                <Badge variant="destructive">
                  {titleForLocale(locale, "已超额", "Limit reached")}
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>
      </TableCell>
      <TableCell className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <div className="min-w-0 flex-1">
            <div className="truncate font-mono text-sm text-foreground">
              {isVisible ? item.api_key : maskGatewayKey(item.api_key)}
            </div>
            <div className="text-xs text-muted-foreground">
              {titleForLocale(
                locale,
                `已用 ${formatGatewayAmount(locale, item.spent_cost_usd)} USD`,
                `Used ${formatGatewayAmount(locale, item.spent_cost_usd)} USD`,
              )}
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => onVisibleKeyChange(isVisible ? "" : item.id)}
            title={
              isVisible
                ? titleForLocale(locale, "隐藏", "Hide")
                : titleForLocale(locale, "显示", "Show")
            }
          >
            {isVisible ? <EyeOff /> : <Eye />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => void onCopy(item.api_key, item.id)}
            title={titleForLocale(locale, "复制", "Copy")}
          >
            {copiedKey === item.api_key ? <Check /> : <Copy />}
          </Button>
        </div>
      </TableCell>
      <TableCell className="min-w-0">
        <div className="flex min-w-0 flex-col gap-1">
          <div>{formatGatewayLimit(locale, item)}</div>
          <div className="text-xs text-muted-foreground">
            {item.expires_at
              ? titleForLocale(
                  locale,
                  `到期 ${formatDateOnly(locale, item.expires_at, timeZone)}`,
                  `Expires ${formatDateOnly(locale, item.expires_at, timeZone)}`,
                )
              : titleForLocale(locale, "永不过期", "No expiry")}
          </div>
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">
        {formatDateTime(locale, item.created_at, timeZone)}
      </TableCell>
      <TableCell className="min-w-0">
        {item.allowed_models.length > 0 ? (
          <div className="flex max-w-56 flex-wrap gap-1">
            {item.allowed_models.slice(0, 2).map((modelName) => (
              <Badge key={modelName} variant="outline">
                {modelName}
              </Badge>
            ))}
            {item.allowed_models.length > 2 ? (
              <Badge variant="outline">+{item.allowed_models.length - 2}</Badge>
            ) : null}
          </div>
        ) : (
          <div className="flex max-w-56 flex-wrap gap-1">
            <Badge variant="outline">
              {titleForLocale(locale, "全部模型组", "All model groups")}
            </Badge>
          </div>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-3">
          <Switch
            checked={item.enabled}
            onCheckedChange={(checked) => void onToggle(item, Boolean(checked))}
            title={titleForLocale(
              locale,
              item.enabled ? "点击停用" : "点击启用",
              item.enabled ? "Click to disable" : "Click to enable",
            )}
            aria-label={titleForLocale(
              locale,
              item.enabled ? "停用 API Key" : "启用 API Key",
              item.enabled ? "Disable API key" : "Enable API key",
            )}
            disabled={isBusy}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => onEdit(item)}
            title={titleForLocale(locale, "编辑", "Edit")}
            disabled={isBusy}
          >
            <Pencil />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => void onRemove(item.id)}
            title={titleForLocale(locale, "删除", "Delete")}
            disabled={isBusy}
          >
            <Trash2 />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}
