import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { BulkActionsPopover } from "@/components/ui/BulkActionsPopover";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { useModelGroupsQuery } from "@/hooks/useModelGroupsQuery";
import { useRowSelection } from "@/hooks/useRowSelection";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { GatewayApiKey, GatewayApiKeyPayload } from "@/lib/api/settings";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { lazyComponent } from "@/lib/lazyComponent";
import { GatewayApiKeyTable } from "./gateway-api-key-manager/GatewayApiKeyTable";
import { buildGatewayModelGroupOptions } from "./gateway-api-key-manager/gatewayApiKeyModel";
import { SettingsSection } from "./settingsLayout";

const gatewayKeyId = (item: GatewayApiKey) => item.id;

const GatewayApiKeyDialog = lazyComponent(() =>
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
  const { data: modelGroups = [] } = useModelGroupsQuery();

  const modelGroupOptions = useMemo(
    () => buildGatewayModelGroupOptions(modelGroups),
    [modelGroups],
  );

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<GatewayApiKey | null>(null);
  const [busyId, setBusyId] = useState("");
  const [copiedKey, setCopiedKey] = useState("");
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const selection = useRowSelection(gatewayKeys, gatewayKeyId);
  const selectedKeys = selection.selectedRows;

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
      toast.success(
        titleForLocale(locale, "网关密钥已复制", "Gateway key copied"),
      );
      window.setTimeout(() => {
        setCopiedKey((current) => (current === value ? "" : current));
      }, 1500);
    } catch {
      toast.error(
        titleForLocale(
          locale,
          "复制失败，请在 HTTPS 环境下重试",
          "Copy failed. Try again over HTTPS.",
        ),
      );
    }
  }

  async function refreshKeys() {
    await queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] });
  }

  async function toggleGatewayKeyEnabled(
    item: GatewayApiKey,
    enabled: boolean,
  ) {
    if (busyId || item.enabled === enabled) {
      return;
    }

    setBusyId(item.id);
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
          enabled ? "网关密钥已启用" : "网关密钥已停用",
          enabled ? "Gateway key enabled" : "Gateway key disabled",
        ),
      );
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "更新网关密钥状态失败",
          "Failed to update gateway key status",
        ),
      );
      toast.error(message);
    } finally {
      setBusyId("");
    }
  }

  async function bulkSetEnabled(enabled: boolean) {
    const items = selectedKeys.filter((item) => item.enabled !== enabled);
    if (!items.length) {
      selection.clear();
      return;
    }
    setBusyId("bulk");
    try {
      for (const item of items) {
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
      }
      toast.success(
        titleForLocale(
          locale,
          enabled
            ? `已启用 ${items.length} 个网关密钥`
            : `已停用 ${items.length} 个网关密钥`,
          enabled
            ? `Enabled ${items.length} gateway keys`
            : `Disabled ${items.length} gateway keys`,
        ),
      );
      selection.clear();
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "批量更新网关密钥失败",
          "Failed to update gateway keys",
        ),
      );
      toast.error(message);
      await refreshKeys();
    } finally {
      setBusyId("");
    }
  }

  async function bulkRemove() {
    if (!selectedKeys.length) return;
    setBusyId("bulk");
    try {
      for (const item of selectedKeys) {
        await apiRequest<void>(`/admin/gateway-api-keys/${item.id}`, {
          method: "DELETE",
        });
      }
      toast.success(
        titleForLocale(
          locale,
          `已删除 ${selectedKeys.length} 个网关密钥`,
          `Deleted ${selectedKeys.length} gateway keys`,
        ),
      );
      selection.clear();
      await refreshKeys();
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "批量删除网关密钥失败",
          "Failed to delete gateway keys",
        ),
      );
      toast.error(message);
      await refreshKeys();
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <SettingsSection
        title={titleForLocale(locale, "网关密钥", "Gateway Keys")}
        actions={
          <>
            <BulkActionsPopover
              locale={locale}
              count={selectedKeys.length}
              isBusy={Boolean(busyId)}
              placement="section"
              onSetEnabled={(enabled) => void bulkSetEnabled(enabled)}
              onDelete={() => setBulkDeleteOpen(true)}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 px-2 text-sm text-muted-foreground shadow-none"
              onClick={openCreateDialog}
            >
              <Plus className="size-3.5" />
              {titleForLocale(locale, "创建网关密钥", "Create gateway key")}
            </Button>
          </>
        }
      >
        <GatewayApiKeyTable
          locale={locale}
          gatewayKeys={gatewayKeys}
          timeZone={timeZone}
          selected={selection.selected}
          busyId={busyId}
          copiedKey={copiedKey}
          onSelectAll={(checked) => selection.toggleRows(gatewayKeys, checked)}
          onSelectOne={selection.toggleId}
          onCopy={copyGatewayKey}
          onEdit={openEditDialog}
          onToggle={toggleGatewayKeyEnabled}
        />
      </SettingsSection>

      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        locale={locale}
        title={titleForLocale(
          locale,
          "批量删除网关密钥",
          "Delete gateway keys",
        )}
        description={titleForLocale(
          locale,
          `删除 ${selectedKeys.length} 个网关密钥？此操作不可撤销。`,
          `Delete ${selectedKeys.length} gateway keys? This cannot be undone.`,
        )}
        isBusy={busyId === "bulk"}
        onOpenChange={setBulkDeleteOpen}
        onConfirm={async () => {
          await bulkRemove();
          setBulkDeleteOpen(false);
        }}
      />

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
