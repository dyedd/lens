"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Check, Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ApiError,
  type GatewayApiKey,
  type GatewayApiKeyPayload,
  type ModelGroup,
  apiRequest,
} from "@/lib/api";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { type Locale } from "@/lib/i18n";

import {
  buildGatewayModelGroupOptions,
  formatDateOnly,
  formatDateTime,
  formatGatewayAmount,
  formatGatewayLimit,
  isGatewayKeyExpired,
  isGatewayKeyOutOfBalance,
  maskGatewayKey,
  titleForLocale,
} from "./gateway-api-key-manager/shared";

const GatewayApiKeyDialog = dynamic(() =>
  import("./gateway-api-key-manager/dialog").then(
    (module) => module.GatewayApiKeyDialog,
  ),
);

export function GatewayApiKeyManager({ locale }: { locale: Locale }) {
  const queryClient = useQueryClient();
  const timeZone = useAppTimeZone();
  const { data: gatewayKeys = [] } = useQuery({
    queryKey: ["gateway-api-keys"],
    queryFn: () => apiRequest<GatewayApiKey[]>("/admin/gateway-api-keys"),
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
  const { data: modelGroups = [] } = useQuery({
    queryKey: ["model-groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 5 * 60_000,
  });

  const modelGroupOptions = useMemo(
    () => buildGatewayModelGroupOptions(modelGroups),
    [modelGroups],
  );

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<GatewayApiKey | null>(null);
  const [removingKeyId, setRemovingKeyId] = useState("");
  const [togglingKeyId, setTogglingKeyId] = useState("");
  const [copiedKey, setCopiedKey] = useState("");

  function openCreateDialog() {
    setEditingKey(null);
    setDialogOpen(true);
  }

  function openEditDialog(item: GatewayApiKey) {
    setEditingKey(item);
    setDialogOpen(true);
  }

  async function copyGatewayKey(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(value);
      toast.success(titleForLocale(locale, "API Key 已复制", "API key copied"));
      window.setTimeout(() => {
        setCopiedKey((current) => (current === value ? "" : current));
      }, 1500);
    } catch {
      toast.error(titleForLocale(locale, "复制失败", "Failed to copy"));
    }
  }

  async function refreshKeys() {
    await queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] });
  }

  async function removeGatewayKey(keyId: string) {
    const confirmed = window.confirm(
      titleForLocale(locale, "确认删除此 API Key？", "Delete this API key?"),
    );
    if (!confirmed) {
      return;
    }

    setRemovingKeyId(keyId);
    try {
      await apiRequest<void>(`/admin/gateway-api-keys/${keyId}`, {
        method: "DELETE",
      });
      toast.success(
        titleForLocale(locale, "API Key 已删除", "API key deleted"),
      );
      await refreshKeys();
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              "删除 API Key 失败",
              "Failed to delete API key",
            );
      toast.error(message);
    } finally {
      setRemovingKeyId("");
    }
  }

  async function toggleGatewayKeyEnabled(
    item: GatewayApiKey,
    enabled: boolean,
  ) {
    if (
      togglingKeyId === item.id ||
      removingKeyId === item.id ||
      item.enabled === enabled
    ) {
      return;
    }

    setTogglingKeyId(item.id);
    try {
      const updated = await apiRequest<GatewayApiKey>(
        `/admin/gateway-api-keys/${item.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            remark: item.remark,
            enabled,
            allowed_models: item.allowed_models,
            max_cost_usd: item.max_cost_usd,
            expires_at: item.expires_at ?? null,
          } satisfies GatewayApiKeyPayload),
        },
      );
      queryClient.setQueryData<GatewayApiKey[]>(
        ["gateway-api-keys"],
        (current) =>
          (current ?? []).map((entry) =>
            entry.id === updated.id ? updated : entry,
          ),
      );
      toast.success(
        titleForLocale(
          locale,
          enabled ? "API Key 已启用" : "API Key 已停用",
          enabled ? "API key enabled" : "API key disabled",
        ),
      );
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              "更新 API Key 状态失败",
              "Failed to update API key status",
            );
      toast.error(message);
    } finally {
      setTogglingKeyId("");
    }
  }

  return (
    <>
      <Card className="min-w-0 py-0">
        <CardContent className="flex min-w-0 flex-col gap-4 px-3 py-3 sm:px-5 sm:py-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              {titleForLocale(
                locale,
                `共 ${gatewayKeys.length} 个密钥`,
                `${gatewayKeys.length} keys`,
              )}
            </div>
            <Button type="button" onClick={openCreateDialog}>
              <Plus data-icon="inline-start" />
              {titleForLocale(locale, "创建 Key", "Create key")}
            </Button>
          </div>

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
                  gatewayKeys.map((item) => {
                    const isBusy =
                      removingKeyId === item.id || togglingKeyId === item.id;
                    const expired = isGatewayKeyExpired(item);
                    const outOfBalance = isGatewayKeyOutOfBalance(item);
                    return (
                      <TableRow key={item.id}>
                        <TableCell className="min-w-0">
                          <div className="flex min-w-36 flex-col gap-2">
                            <div className="truncate text-sm text-foreground">
                              {item.remark ||
                                titleForLocale(locale, "未命名", "Unnamed")}
                            </div>
                            {expired || outOfBalance ? (
                              <div className="flex flex-wrap gap-1">
                                {expired ? (
                                  <Badge variant="destructive">
                                    {titleForLocale(
                                      locale,
                                      "已过期",
                                      "Expired",
                                    )}
                                  </Badge>
                                ) : null}
                                {outOfBalance ? (
                                  <Badge variant="destructive">
                                    {titleForLocale(
                                      locale,
                                      "已超额",
                                      "Limit reached",
                                    )}
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
                                {maskGatewayKey(item.api_key)}
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
                              onClick={() => void copyGatewayKey(item.api_key)}
                              title={titleForLocale(locale, "复制", "Copy")}
                            >
                              {copiedKey === item.api_key ? (
                                <Check />
                              ) : (
                                <Copy />
                              )}
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
                                : titleForLocale(
                                    locale,
                                    "永不过期",
                                    "No expiry",
                                  )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(locale, item.created_at, timeZone)}
                        </TableCell>
                        <TableCell className="min-w-0">
                          {item.allowed_models.length > 0 ? (
                            <div className="flex max-w-56 flex-wrap gap-1">
                              {item.allowed_models
                                .slice(0, 2)
                                .map((modelName) => (
                                  <Badge key={modelName} variant="outline">
                                    {modelName}
                                  </Badge>
                                ))}
                              {item.allowed_models.length > 2 ? (
                                <Badge variant="outline">
                                  +{item.allowed_models.length - 2}
                                </Badge>
                              ) : null}
                            </div>
                          ) : (
                            <div className="flex max-w-56 flex-wrap gap-1">
                              <Badge variant="outline">
                                {titleForLocale(
                                  locale,
                                  "全部模型组",
                                  "All model groups",
                                )}
                              </Badge>
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center justify-end gap-3">
                            <Switch
                              checked={item.enabled}
                              onCheckedChange={(checked) =>
                                void toggleGatewayKeyEnabled(
                                  item,
                                  Boolean(checked),
                                )
                              }
                              title={titleForLocale(
                                locale,
                                item.enabled ? "点击停用" : "点击启用",
                                item.enabled
                                  ? "Click to disable"
                                  : "Click to enable",
                              )}
                              aria-label={titleForLocale(
                                locale,
                                item.enabled ? "停用 API Key" : "启用 API Key",
                                item.enabled
                                  ? "Disable API key"
                                  : "Enable API key",
                              )}
                              disabled={isBusy}
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => openEditDialog(item)}
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
                              onClick={() => void removeGatewayKey(item.id)}
                              title={titleForLocale(locale, "删除", "Delete")}
                              disabled={isBusy}
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="py-10 text-center text-sm text-muted-foreground"
                    >
                      {titleForLocale(
                        locale,
                        "当前没有 API 密钥",
                        "No API keys",
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {dialogOpen ? (
        <GatewayApiKeyDialog
          locale={locale}
          open={dialogOpen}
          editingKey={editingKey}
          modelGroupOptions={modelGroupOptions}
          timeZone={timeZone}
          onClose={() => setDialogOpen(false)}
          onSaved={refreshKeys}
        />
      ) : null}
    </>
  );
}
