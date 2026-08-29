import { useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCcw, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { SiteCredential } from "@/lib/api/sites";
import { emptyCredential } from "./channelDefaults";
import { credentialIndexLabel } from "./channelLabels";
import type {
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
  Locale,
} from "./channelTypes";

type Props = {
  baseUrls: FormBaseUrl[];
  credentials: FormCredential[];
  protocolConfigs: FormProtocolConfig[];
  siteId: string | null;
  canSyncRates: boolean;
  locale: Locale;
  onSyncingChange: (isSyncing: boolean) => void;
  onAdd: (credential: FormCredential) => void;
  onUpdate: (credentialId: string, patch: Partial<FormCredential>) => void;
  onRemove: (index: number) => void;
};

const CLEARED_RATE_STATUS = {
  rate_multiplier: null,
  rate_observed_at: null,
  rate_last_synced_at: null,
  rate_last_error: "",
};

/** Renders editable channel credentials. */
export function ChannelCredentialSection({
  baseUrls,
  credentials,
  protocolConfigs,
  siteId,
  canSyncRates,
  locale,
  onSyncingChange,
  onAdd,
  onUpdate,
  onRemove,
}: Props) {
  const queryClient = useQueryClient();
  const [syncingCredentialId, setSyncingCredentialId] = useState<string | null>(
    null,
  );

  async function syncRate(credential: FormCredential) {
    if (!siteId) return;
    setSyncingCredentialId(credential.id);
    onSyncingChange(true);
    try {
      const result = await apiRequest<SiteCredential>(
        `/admin/sites/${encodeURIComponent(siteId)}/credentials/${encodeURIComponent(credential.id)}/rate-sync`,
        { method: "POST" },
      );
      onUpdate(credential.id, {
        rate_multiplier: result.rate_multiplier,
        rate_observed_at: result.rate_observed_at,
        rate_last_synced_at: result.rate_last_synced_at,
        rate_last_error: result.rate_last_error,
      });
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
      toast.success(
        locale === "zh-CN" ? "凭据倍率已同步" : "Credential rate synced",
      );
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        locale === "zh-CN"
          ? "同步凭据倍率失败"
          : "Failed to sync credential rate",
      );
      onUpdate(credential.id, { rate_last_error: message });
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
      toast.error(message);
    } finally {
      setSyncingCredentialId(null);
      onSyncingChange(false);
    }
  }

  return (
    <section className="grid gap-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">
          {locale === "zh-CN" ? "密钥" : "API Keys"}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onAdd(emptyCredential())}
        >
          <Plus data-icon="inline-start" />
          {locale === "zh-CN" ? "添加" : "Add"}
        </Button>
      </div>
      <FieldGroup className="gap-3">
        {credentials.map((credential, index) => {
          const availableProtocolConfigs = protocolConfigs.filter(
            (config) =>
              config.enabled &&
              config.credential_ids.includes(credential.id) &&
              baseUrls.some(
                (baseUrl) =>
                  baseUrl.id === config.base_url_id && baseUrl.enabled,
              ),
          );
          const hasAvailableRateConfig = availableProtocolConfigs.some(
            (config) => config.id === credential.rate_protocol_config_id,
          );
          return (
            <div
              key={credential.id}
              className="grid min-w-0 gap-3 border-b pb-4 last:border-b-0 last:pb-0"
            >
              <FieldGroup className="grid min-w-0 gap-2 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_minmax(7rem,0.8fr)_32px_32px] md:items-end">
                <Field>
                  <FieldLabel>{credentialIndexLabel(index, locale)}</FieldLabel>
                  <Input
                    className="w-full min-w-0"
                    value={credential.api_key}
                    onChange={(event) =>
                      onUpdate(credential.id, { api_key: event.target.value })
                    }
                    placeholder="sk-..."
                  />
                </Field>
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "备注" : "Remark"}
                  </FieldLabel>
                  <Input
                    className="w-full min-w-0"
                    value={credential.name}
                    onChange={(event) =>
                      onUpdate(credential.id, { name: event.target.value })
                    }
                    placeholder={locale === "zh-CN" ? "备注" : "Remark"}
                  />
                </Field>
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "倍率来源" : "Rate source"}
                  </FieldLabel>
                  <Select
                    value={credential.rate_source}
                    onValueChange={(value) =>
                      onUpdate(credential.id, {
                        rate_source: value as FormCredential["rate_source"],
                        rate_protocol_config_id:
                          value === "none"
                            ? ""
                            : credential.rate_protocol_config_id,
                        rate_group:
                          value === "newapi" ? credential.rate_group : "",
                        ...CLEARED_RATE_STATUS,
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="none">
                          {locale === "zh-CN" ? "关闭" : "Disabled"}
                        </SelectItem>
                        <SelectItem value="sub2api">Sub2API</SelectItem>
                        <SelectItem value="newapi">NewAPI</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <div className="flex size-8 items-center justify-center">
                  <Switch
                    checked={credential.enabled}
                    onCheckedChange={(checked) =>
                      onUpdate(credential.id, { enabled: checked })
                    }
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="text-muted-foreground"
                  onClick={() => onRemove(index)}
                >
                  <X />
                </Button>
              </FieldGroup>
              {credential.rate_source !== "none" ? (
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求配置" : "Request config"}
                    </FieldLabel>
                    <Select
                      value={credential.rate_protocol_config_id}
                      onValueChange={(value) =>
                        onUpdate(credential.id, {
                          rate_protocol_config_id: value,
                          ...CLEARED_RATE_STATUS,
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            locale === "zh-CN" ? "选择配置" : "Select config"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {availableProtocolConfigs.map(
                            (config, configIndex) => (
                              <SelectItem key={config.id} value={config.id}>
                                {config.name ||
                                  (locale === "zh-CN"
                                    ? `配置 ${configIndex + 1}`
                                    : `Config ${configIndex + 1}`)}
                              </SelectItem>
                            ),
                          )}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                  {credential.rate_source === "newapi" ? (
                    <Field>
                      <FieldLabel>
                        {locale === "zh-CN" ? "NewAPI 分组" : "NewAPI group"}
                      </FieldLabel>
                      <Input
                        value={credential.rate_group}
                        onChange={(event) =>
                          onUpdate(credential.id, {
                            rate_group: event.target.value,
                            ...CLEARED_RATE_STATUS,
                          })
                        }
                        placeholder="default"
                      />
                    </Field>
                  ) : null}
                </div>
              ) : null}
              {credential.rate_source !== "none" ? (
                <div className="flex min-h-8 flex-wrap items-center gap-2">
                  {credential.rate_multiplier !== null ? (
                    <Badge variant="secondary">
                      {credential.rate_source === "newapi"
                        ? locale === "zh-CN"
                          ? "参考倍率"
                          : "Reference rate"
                        : locale === "zh-CN"
                          ? "有效倍率"
                          : "Effective rate"}
                      : {credential.rate_multiplier}x
                    </Badge>
                  ) : null}
                  {credential.rate_last_synced_at ? (
                    <span className="text-xs text-muted-foreground">
                      {new Date(credential.rate_last_synced_at).toLocaleString(
                        locale,
                      )}
                    </span>
                  ) : null}
                  {credential.rate_last_error ? (
                    <span
                      className="min-w-0 flex-1 truncate text-xs text-destructive"
                      title={credential.rate_last_error}
                    >
                      {credential.rate_last_error}
                    </span>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="ml-auto"
                    disabled={
                      !canSyncRates ||
                      !credential.enabled ||
                      !hasAvailableRateConfig ||
                      (credential.rate_source === "newapi" &&
                        !credential.rate_group.trim())
                    }
                    onClick={() => void syncRate(credential)}
                  >
                    <RefreshCcw
                      data-icon="inline-start"
                      className={
                        syncingCredentialId === credential.id
                          ? "animate-spin"
                          : undefined
                      }
                    />
                    {locale === "zh-CN" ? "同步倍率" : "Sync rate"}
                  </Button>
                </div>
              ) : null}
            </div>
          );
        })}
      </FieldGroup>
    </section>
  );
}
