"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import dynamic from "next/dynamic";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import {
  apiRequest,
  type GatewayApiKey,
  type GatewayApiKeyPayload,
  getApiErrorMessage,
  type ModelGroup,
} from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { GatewayApiKeyTable } from "./gateway-api-key-manager/GatewayApiKeyTable";
import { buildGatewayModelGroupOptions } from "./gateway-api-key-manager/gatewayApiKeyUtils";

const GatewayApiKeyDialog = dynamic(() =>
  import("./gateway-api-key-manager/GatewayApiKeyDialog").then(
    (module) => module.GatewayApiKeyDialog,
  ),
);

/** Renders gateway API key management controls and status. */
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
  const [visibleKey, setVisibleKey] = useState("");

  function openCreateDialog() {
    setEditingKey(null);
    setDialogOpen(true);
  }

  function openEditDialog(item: GatewayApiKey) {
    setEditingKey(item);
    setDialogOpen(true);
  }

  async function copyGatewayKey(value: string, itemId: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(value);
      toast.success(titleForLocale(locale, "API Key 已复制", "API key copied"));
      window.setTimeout(() => {
        setCopiedKey((current) => (current === value ? "" : current));
      }, 1500);
    } catch {
      setVisibleKey(itemId);
      toast.info(
        titleForLocale(
          locale,
          "非 HTTPS 环境，无法自动复制，已显示完整 Key 请手动复制",
          "Non-HTTPS environment. Key revealed for manual copy.",
        ),
      );
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
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(locale, "删除 API Key 失败", "Failed to delete API key"),
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
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "更新 API Key 状态失败",
          "Failed to update API key status",
        ),
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
          <GatewayApiKeyTable
            locale={locale}
            gatewayKeys={gatewayKeys}
            timeZone={timeZone}
            removingKeyId={removingKeyId}
            togglingKeyId={togglingKeyId}
            copiedKey={copiedKey}
            visibleKey={visibleKey}
            onVisibleKeyChange={setVisibleKey}
            onCopy={copyGatewayKey}
            onEdit={openEditDialog}
            onRemove={removeGatewayKey}
            onToggle={toggleGatewayKeyEnabled}
          />
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
