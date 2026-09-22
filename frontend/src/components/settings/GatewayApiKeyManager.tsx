import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Plus, ToggleLeft, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ModelGroup } from "@/lib/api/groups";
import type { GatewayApiKey, GatewayApiKeyPayload } from "@/lib/api/settings";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { lazyComponent } from "@/lib/lazyComponent";

import { GatewayApiKeyTable } from "./gateway-api-key-manager/GatewayApiKeyTable";
import { buildGatewayModelGroupOptions } from "./gateway-api-key-manager/gatewayApiKeyModel";
import { SettingsSection } from "./settingsLayout";

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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busyId, setBusyId] = useState("");
  const [copiedKey, setCopiedKey] = useState("");
  const [bulkEnabled, setBulkEnabled] = useState<"enabled" | "disabled" | "">(
    "",
  );
  const selectedKeys = gatewayKeys.filter((item) => selected.has(item.id));

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

  function handleSelectAll(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const item of gatewayKeys) {
        if (checked) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  }

  function handleSelectOne(keyId: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(keyId);
      else next.delete(keyId);
      return next;
    });
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
      setBusyId("");
    }
  }

  async function bulkSetEnabled(enabled: boolean) {
    const items = selectedKeys.filter((item) => item.enabled !== enabled);
    if (!items.length) {
      setSelected(new Set());
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
            ? `已启用 ${items.length} 个 API Key`
            : `已停用 ${items.length} 个 API Key`,
          enabled
            ? `Enabled ${items.length} API keys`
            : `Disabled ${items.length} API keys`,
        ),
      );
      setSelected(new Set());
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "批量更新 API Key 失败",
          "Failed to update API keys",
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
    const confirmed = window.confirm(
      titleForLocale(
        locale,
        `确认删除选中的 ${selectedKeys.length} 个 API Key？`,
        `Delete ${selectedKeys.length} selected API keys?`,
      ),
    );
    if (!confirmed) return;
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
          `已删除 ${selectedKeys.length} 个 API Key`,
          `Deleted ${selectedKeys.length} API keys`,
        ),
      );
      setSelected(new Set());
      await refreshKeys();
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          "批量删除 API Key 失败",
          "Failed to delete API keys",
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
        title={titleForLocale(locale, "API 密钥", "API keys")}
        actions={
          <>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground"
                  disabled={selectedKeys.length === 0 || Boolean(busyId)}
                  aria-label={titleForLocale(locale, "批量", "Bulk")}
                >
                  <ListChecks className="size-3.5" />
                  {titleForLocale(locale, "批量", "Bulk")}
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-[240px] p-2">
                <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                  {titleForLocale(
                    locale,
                    `已选 ${selectedKeys.length} 项`,
                    `${selectedKeys.length} selected`,
                  )}
                </p>
                <div className="flex h-7 w-full items-center gap-1.5">
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                    disabled={!bulkEnabled || Boolean(busyId)}
                    onClick={() => {
                      void bulkSetEnabled(bulkEnabled === "enabled");
                    }}
                  >
                    <ToggleLeft className="size-3" />
                    {titleForLocale(locale, "应用", "Apply")}
                  </Button>
                  <Select
                    value={bulkEnabled || undefined}
                    onValueChange={(value) =>
                      setBulkEnabled(value as "enabled" | "disabled")
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue
                        placeholder={titleForLocale(locale, "状态", "Status")}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="enabled">
                        {titleForLocale(locale, "启用", "Enable")}
                      </SelectItem>
                      <SelectItem value="disabled">
                        {titleForLocale(locale, "停用", "Disable")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <button
                  type="button"
                  disabled={Boolean(busyId)}
                  onClick={() => void bulkRemove()}
                  className="mt-1 flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[11px] text-foreground/70 hover:bg-muted hover:text-foreground disabled:opacity-50"
                >
                  <Trash2 className="size-3.5" />
                  {titleForLocale(locale, "批量删除", "Delete selected")}
                </button>
              </PopoverContent>
            </Popover>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
              onClick={openCreateDialog}
            >
              <Plus className="size-3.5" />
              {titleForLocale(locale, "创建 Key", "Create key")}
            </Button>
          </>
        }
      >
        <GatewayApiKeyTable
          locale={locale}
          gatewayKeys={gatewayKeys}
          timeZone={timeZone}
          selected={selected}
          busyId={busyId}
          copiedKey={copiedKey}
          onSelectAll={handleSelectAll}
          onSelectOne={handleSelectOne}
          onCopy={copyGatewayKey}
          onEdit={openEditDialog}
          onToggle={toggleGatewayKeyEnabled}
        />
      </SettingsSection>

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
