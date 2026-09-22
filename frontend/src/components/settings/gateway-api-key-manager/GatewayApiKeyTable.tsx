import { Check, Copy, Eye, EyeOff, Pencil } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { GatewayApiKey } from "@/lib/api/settings";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import {
  formatGatewayLimit,
  isGatewayKeyExpired,
  isGatewayKeyOutOfBalance,
  maskGatewayKey,
} from "./gatewayApiKeyModel";
import { formatDateOnly } from "./gatewayDateTime";

type GatewayApiKeyTableProps = {
  locale: Locale;
  gatewayKeys: GatewayApiKey[];
  timeZone: string;
  selected: Set<string>;
  busyId: string;
  copiedKey: string;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (keyId: string, checked: boolean) => void;
  onCopy: (value: string) => Promise<void>;
  onEdit: (item: GatewayApiKey) => void;
  onToggle: (item: GatewayApiKey, enabled: boolean) => Promise<void>;
};

function permissionLabel(item: GatewayApiKey, locale: Locale) {
  if (item.allowed_models.length === 0) {
    return titleForLocale(locale, "全部模型组", "All model groups");
  }
  return item.allowed_models.join(", ");
}

function statusHint(item: GatewayApiKey, locale: Locale) {
  if (isGatewayKeyExpired(item)) {
    return titleForLocale(locale, "已过期", "Expired");
  }
  if (isGatewayKeyOutOfBalance(item)) {
    return titleForLocale(locale, "已超额", "Limit reached");
  }
  return null;
}

/** Renders the gateway API key list and empty state. */
export function GatewayApiKeyTable({
  locale,
  gatewayKeys,
  timeZone,
  selected,
  busyId,
  copiedKey,
  onSelectAll,
  onSelectOne,
  onCopy,
  onEdit,
  onToggle,
}: GatewayApiKeyTableProps) {
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const allSelected =
    gatewayKeys.length > 0 &&
    gatewayKeys.every((item) => selected.has(item.id));
  const someSelected = gatewayKeys.some((item) => selected.has(item.id));
  const bulkBusy = busyId === "bulk";

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[44px] text-center">
            <div className="flex h-7 items-center justify-center">
              <Checkbox
                checked={
                  allSelected ? true : someSelected ? "indeterminate" : false
                }
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={titleForLocale(
                  locale,
                  "全选密钥",
                  "Select all keys",
                )}
                disabled={bulkBusy}
              />
            </div>
          </TableHead>
          <TableHead>{titleForLocale(locale, "名称", "Name")}</TableHead>
          <TableHead>{titleForLocale(locale, "限额", "Limit")}</TableHead>
          <TableHead>{titleForLocale(locale, "权限", "Permissions")}</TableHead>
          <TableHead className="w-[72px] text-center">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead className="w-[56px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {gatewayKeys.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={6}
              className="h-32 text-center text-sm text-muted-foreground"
            >
              {titleForLocale(locale, "当前没有 API 密钥", "No API keys")}
            </TableCell>
          </TableRow>
        ) : (
          gatewayKeys.map((item) => {
            const isBusy = busyId === item.id || bulkBusy;
            const hint = statusHint(item, locale);
            const copied = copiedKey === item.api_key;
            const isVisible = visibleKeys.has(item.id);
            return (
              <TableRow
                key={item.id}
                data-state={selected.has(item.id) ? "selected" : undefined}
              >
                <TableCell className="w-[44px] py-1 text-center">
                  <div className="flex h-7 items-center justify-center">
                    <Checkbox
                      checked={selected.has(item.id)}
                      onCheckedChange={(checked) =>
                        onSelectOne(item.id, checked === true)
                      }
                      aria-label={titleForLocale(
                        locale,
                        "选择密钥",
                        "Select key",
                      )}
                      disabled={isBusy}
                    />
                  </div>
                </TableCell>
                <TableCell className="min-w-0 max-w-[16rem] py-1">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {item.remark ||
                        titleForLocale(locale, "未命名", "Unnamed")}
                    </p>
                    <div className="flex min-w-0 items-center gap-0.5">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="min-w-0 truncate font-mono text-xs text-muted-foreground">
                            {isVisible
                              ? item.api_key
                              : maskGatewayKey(item.api_key)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          className="max-w-none font-mono"
                        >
                          {item.api_key}
                        </TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="shrink-0 text-muted-foreground shadow-none"
                            onClick={() => {
                              setVisibleKeys((current) => {
                                const next = new Set(current);
                                if (next.has(item.id)) next.delete(item.id);
                                else next.add(item.id);
                                return next;
                              });
                            }}
                            aria-label={titleForLocale(
                              locale,
                              isVisible ? "隐藏完整 Key" : "显示完整 Key",
                              isVisible ? "Hide full key" : "Show full key",
                            )}
                          >
                            {isVisible ? <EyeOff /> : <Eye />}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          {titleForLocale(
                            locale,
                            isVisible ? "隐藏 Key" : "显示完整 Key",
                            isVisible ? "Hide key" : "Show full key",
                          )}
                        </TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="shrink-0 text-muted-foreground shadow-none"
                            onClick={() => void onCopy(item.api_key)}
                            aria-label={titleForLocale(
                              locale,
                              "复制密钥",
                              "Copy key",
                            )}
                          >
                            {copied ? <Check /> : <Copy />}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          {titleForLocale(locale, "复制密钥", "Copy key")}
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="min-w-0 py-1">
                  <p className="text-xs">{formatGatewayLimit(locale, item)}</p>
                  <p className="text-xs text-muted-foreground">
                    {hint ??
                      (item.expires_at
                        ? titleForLocale(
                            locale,
                            `到期 ${formatDateOnly(locale, item.expires_at, timeZone)}`,
                            `Expires ${formatDateOnly(locale, item.expires_at, timeZone)}`,
                          )
                        : titleForLocale(locale, "永不过期", "No expiry"))}
                  </p>
                </TableCell>
                <TableCell className="min-w-0 max-w-[14rem] py-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="block truncate text-xs text-muted-foreground">
                        {permissionLabel(item, locale)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {permissionLabel(item, locale)}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="w-[72px] py-1">
                  <div className="flex h-7 items-center justify-center">
                    <Switch
                      checked={item.enabled}
                      disabled={isBusy}
                      onCheckedChange={(checked) =>
                        void onToggle(item, Boolean(checked))
                      }
                      aria-label={titleForLocale(
                        locale,
                        item.enabled ? "停用 API Key" : "启用 API Key",
                        item.enabled ? "Disable API key" : "Enable API key",
                      )}
                    />
                  </div>
                </TableCell>
                <TableCell className="w-[56px] py-1">
                  <div className="flex h-7 items-center justify-end">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="text-muted-foreground shadow-none"
                          onClick={() => onEdit(item)}
                          disabled={isBusy}
                          aria-label={titleForLocale(
                            locale,
                            "编辑 API Key",
                            "Edit API key",
                          )}
                        >
                          <Pencil />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        {titleForLocale(locale, "编辑 API Key", "Edit API key")}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
