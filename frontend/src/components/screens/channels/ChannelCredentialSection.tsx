import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Eye, EyeOff, RefreshCcw, Trash2 } from "lucide-react";
import {
  type Dispatch,
  type KeyboardEvent,
  type SetStateAction,
  useState,
} from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
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
import { Textarea } from "@/components/ui/Textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { SiteCredential } from "@/lib/api/sites";
import { credentialLabel } from "@/lib/credentialLabels";
import { formatEndpointLabel } from "./channelDisplay";
import { addApiKeyDraft } from "./channelForm";
import { rebuildProtocolConfigs } from "./channelFormConversion";
import type { FormCredential, FormState, Locale } from "./channelTypes";

type Props = {
  locale: Locale;
  inputId: string;
  required?: boolean;
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  siteId: string | null;
  canSyncRates: boolean;
};

const CLEARED_RATE_STATUS = {
  rate_multiplier: null,
  rate_observed_at: null,
  rate_last_synced_at: null,
  rate_last_error: "",
} satisfies Partial<FormCredential>;

type CredentialKeyCellProps = {
  credential: FormCredential;
  locale: Locale;
  updateKey: (credentialId: string, patch: Partial<FormCredential>) => void;
  copyKey: (apiKey: string, id?: string) => Promise<void>;
  copiedId: string | null;
};

function CredentialKeyCell({
  credential,
  locale,
  updateKey,
  copyKey,
  copiedId,
}: CredentialKeyCellProps) {
  const isZh = locale === "zh-CN";
  const [showKey, setShowKey] = useState(false);

  return (
    <div className="relative flex w-full min-w-0 items-center">
      <Input
        type={showKey ? "text" : "password"}
        value={credential.api_key}
        onChange={(e) =>
          updateKey(credential.id, {
            api_key: e.target.value,
            ...CLEARED_RATE_STATUS,
          })
        }
        onBlur={(e) => {
          const trimmed = e.target.value.trim();
          if (trimmed !== credential.api_key) {
            updateKey(credential.id, { api_key: trimmed });
          }
        }}
        placeholder="sk-..."
        aria-label={isZh ? "API Key" : "API key"}
        className="h-7 w-full min-w-0 pl-2 pr-12 font-mono text-xs"
        spellCheck={false}
      />
      <div className="absolute right-1 flex items-center gap-0.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="size-5 text-muted-foreground shadow-none hover:text-foreground"
              onClick={() => setShowKey(!showKey)}
              aria-label={
                showKey
                  ? isZh
                    ? "隐藏明文"
                    : "Hide key"
                  : isZh
                    ? "显示明文"
                    : "Show key"
              }
            >
              {showKey ? (
                <EyeOff className="size-3.5" />
              ) : (
                <Eye className="size-3.5" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">
            {showKey
              ? isZh
                ? "隐藏明文"
                : "Hide key"
              : isZh
                ? "显示明文"
                : "Show key"}
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="size-5 text-muted-foreground shadow-none hover:text-foreground"
              aria-label={isZh ? "复制完整 API Key" : "Copy full key"}
              onClick={() => void copyKey(credential.api_key, credential.id)}
            >
              {copiedId === credential.id ? (
                <Check className="size-3.5 stroke-1 text-muted-foreground" />
              ) : (
                <Copy className="size-3.5 stroke-1" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">
            {isZh ? "复制完整 API Key" : "Copy full key"}
          </TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}

export function ChannelCredentialSection({
  locale,
  inputId,
  required = false,
  form,
  setForm,
  siteId,
  canSyncRates,
}: Props) {
  const isZh = locale === "zh-CN";
  const queryClient = useQueryClient();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const scopedKeys = form.credentials.map((credential, index) => ({
    credential,
    index,
  }));
  const configs = rebuildProtocolConfigs(form);

  function changeDraft(value: string) {
    setForm((current) => ({ ...current, newApiKeysLines: value }));
  }

  function addDraftKeys() {
    const result = addApiKeyDraft(form);
    if (result.form === form) return;
    setForm(result.form);
    if (result.added === 0) {
      toast.info(
        isZh ? "这些 Key 已在列表中" : "These keys are already in the list",
      );
    }
  }

  function handleDraftKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.nativeEvent.isComposing ||
      event.key !== "Enter" ||
      event.shiftKey
    ) {
      return;
    }
    event.preventDefault();
    addDraftKeys();
  }

  function updateKey(credentialId: string, patch: Partial<FormCredential>) {
    const next = {
      ...form,
      credentials: form.credentials.map((item) =>
        item.id === credentialId ? { ...item, ...patch } : item,
      ),
    };
    const protocolConfigs = rebuildProtocolConfigs(next);
    const removedCount = form.protocolConfigs.reduce(
      (count, config) =>
        count +
        config.models
          .filter(
            (model) =>
              model.credential_id === credentialId &&
              !protocolConfigs
                .find((item) => item.id === config.id)
                ?.credential_ids.includes(credentialId),
          )
          .reduce((total, model) => total + model.protocols.length, 0),
      0,
    );
    if (removedCount)
      toast.info(
        isZh
          ? `保存后将移除 ${removedCount} 个模型出口`
          : `${removedCount} model outlets will be removed on save`,
      );
    setForm({ ...next, protocolConfigs });
  }

  function removeKey(credentialId: string) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.filter(
        (item) => item.id !== credentialId,
      ),
    }));
  }

  async function copyKey(apiKey: string, id?: string) {
    try {
      await navigator.clipboard.writeText(apiKey);
      if (id) {
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
      }
      toast.success(isZh ? "API Key 已复制" : "API key copied");
    } catch {
      toast.error(isZh ? "复制失败" : "Copy failed");
    }
  }

  async function syncRate(credentialId: string) {
    if (!siteId) return;
    setSyncingId(credentialId);
    try {
      const result = await apiRequest<SiteCredential>(
        `/admin/sites/${encodeURIComponent(siteId)}/credentials/${encodeURIComponent(credentialId)}/rate-sync`,
        { method: "POST" },
      );
      updateKey(credentialId, {
        rate_multiplier: result.rate_multiplier,
        rate_observed_at: result.rate_observed_at,
        rate_last_synced_at: result.rate_last_synced_at,
        rate_last_error: result.rate_last_error,
      });
      toast.success(isZh ? "倍率已同步" : "Rate synced");
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        isZh ? "同步倍率失败" : "Failed to sync rate",
      );
      updateKey(credentialId, { rate_last_error: message });
      toast.error(message);
    } finally {
      setSyncingId(null);
      void queryClient.invalidateQueries({ queryKey: ["sites"] });
    }
  }

  return (
    <div className="min-w-0 max-w-full space-y-1">
      <Label
        htmlFor={inputId}
        required={required}
        className="text-sm font-normal text-muted-foreground"
      >
        {scopedKeys.length
          ? isZh
            ? "添加 API Key"
            : "Add API keys"
          : isZh
            ? "API Key（支持多个）"
            : "API keys (rotated)"}
      </Label>
      <Textarea
        id={inputId}
        required={required && scopedKeys.length === 0}
        spellCheck={false}
        className="h-24 w-full min-w-0 max-w-full resize-none overflow-y-auto font-mono text-xs break-all placeholder:font-sans"
        placeholder={
          isZh
            ? "每行输入一个 API Key，按 Enter 添加；Shift+Enter 换行"
            : "One API key per line. Enter adds it; Shift+Enter inserts a new line"
        }
        value={form.newApiKeysLines}
        onChange={(event) => changeDraft(event.target.value)}
        onKeyDown={handleDraftKeyDown}
      />
      {scopedKeys.length > 0 ? (
        <div className="mt-2 space-y-1.5">
          <div className="text-xs leading-4 text-muted-foreground">
            {isZh
              ? `${scopedKeys.length} 个 API Key`
              : `${scopedKeys.length} keys`}
          </div>
          <div className="overflow-hidden rounded-md bg-muted/35">
            {scopedKeys.map(({ credential, index }) => {
              const isSyncing = syncingId === credential.id;
              const needsGroup =
                credential.rate_source === "newapi" &&
                !credential.rate_group.trim();
              return (
                <div
                  key={credential.id}
                  className="space-y-1.5 border-b border-border/40 px-2.5 py-1.5 text-xs last:border-b-0"
                >
                  <div className="grid min-w-0 grid-cols-[5rem_minmax(0,1fr)_6.25rem_1.5rem] items-center gap-2">
                    <Input
                      className="h-7 w-full min-w-0 px-2 text-xs"
                      value={credential.name}
                      placeholder={isZh ? "备注" : "Remark"}
                      aria-label={credentialLabel(credential, index, locale)}
                      onChange={(event) =>
                        updateKey(credential.id, { name: event.target.value })
                      }
                    />
                    <CredentialKeyCell
                      credential={credential}
                      locale={locale}
                      updateKey={updateKey}
                      copyKey={copyKey}
                      copiedId={copiedId}
                    />
                    <Select
                      value={credential.rate_source}
                      onValueChange={(value) =>
                        updateKey(credential.id, {
                          rate_source: value as FormCredential["rate_source"],
                          rate_protocol_config_id:
                            value === "none"
                              ? ""
                              : credential.rate_protocol_config_id ||
                                configs.find((config) =>
                                  config.credential_ids.includes(credential.id),
                                )?.id ||
                                "",
                          rate_group:
                            value === "newapi" ? credential.rate_group : "",
                          ...CLEARED_RATE_STATUS,
                        })
                      }
                    >
                      <SelectTrigger
                        className="h-7 w-full min-w-0 px-2 text-xs"
                        aria-label={isZh ? "倍率来源" : "Rate source"}
                      >
                        <SelectValue className="min-w-0 flex-1 truncate" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">
                          {isZh ? "不查询倍率" : "No rate"}
                        </SelectItem>
                        <SelectItem value="sub2api">Sub2API</SelectItem>
                        <SelectItem value="newapi">NewAPI</SelectItem>
                      </SelectContent>
                    </Select>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="size-6 justify-self-end text-muted-foreground hover:text-foreground"
                          aria-label={isZh ? "删除 API Key" : "Delete API key"}
                          onClick={() => removeKey(credential.id)}
                        >
                          <Trash2 className="size-3.5 stroke-1" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {isZh ? "删除" : "Delete"}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 max-w-full justify-start px-0 text-xs font-normal text-muted-foreground"
                        aria-label={
                          credentialLabel(credential, index, locale) +
                          (isZh ? " 适用地址" : " allowed endpoints")
                        }
                      >
                        <span className="truncate">
                          {credential.base_url_ids === null
                            ? isZh
                              ? "任意地址"
                              : "Any endpoint"
                            : credential.base_url_ids.length === 0
                              ? isZh
                                ? "未选择地址"
                                : "No endpoints selected"
                              : form.base_urls
                                  .filter((url) =>
                                    credential.base_url_ids?.includes(url.id),
                                  )
                                  .map((url) =>
                                    formatEndpointLabel(url, locale),
                                  )
                                  .join(" · ")}
                        </span>
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent
                      align="start"
                      className="w-80 max-w-[calc(100vw-2rem)] p-2"
                    >
                      <div className="flex max-h-64 flex-col gap-1 overflow-y-auto">
                        <label
                          htmlFor={`scope-any-${credential.id}`}
                          className="flex cursor-pointer items-center gap-2 rounded-md p-1.5 text-xs"
                        >
                          <Checkbox
                            id={`scope-any-${credential.id}`}
                            checked={credential.base_url_ids === null}
                            onCheckedChange={(checked) =>
                              updateKey(credential.id, {
                                base_url_ids: checked === true ? null : [],
                              })
                            }
                          />
                          {isZh ? "任意地址" : "Any endpoint"}
                        </label>
                        {form.base_urls.map((url) => (
                          <label
                            key={url.id}
                            htmlFor={`scope-${credential.id}-${url.id}`}
                            className="flex cursor-pointer items-start gap-2 rounded-md p-1.5 text-xs"
                          >
                            <Checkbox
                              id={`scope-${credential.id}-${url.id}`}
                              checked={
                                credential.base_url_ids?.includes(url.id) ??
                                false
                              }
                              onCheckedChange={(checked) =>
                                updateKey(credential.id, {
                                  base_url_ids:
                                    checked === true
                                      ? [
                                          ...(credential.base_url_ids ?? []),
                                          url.id,
                                        ]
                                      : (credential.base_url_ids ?? []).filter(
                                          (id) => id !== url.id,
                                        ),
                                })
                              }
                            />
                            <span className="min-w-0 break-all">
                              {formatEndpointLabel(url, locale)}
                            </span>
                          </label>
                        ))}
                      </div>
                    </PopoverContent>
                  </Popover>
                  {credential.rate_source !== "none" ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Select
                        value={
                          configs.some(
                            (config) =>
                              config.id ===
                                credential.rate_protocol_config_id &&
                              config.credential_ids.includes(credential.id),
                          )
                            ? credential.rate_protocol_config_id
                            : ""
                        }
                        onValueChange={(value) =>
                          updateKey(credential.id, {
                            rate_protocol_config_id: value,
                            ...CLEARED_RATE_STATUS,
                          })
                        }
                      >
                        <SelectTrigger
                          className="h-7 min-w-0 flex-1 px-2 text-xs"
                          aria-label={isZh ? "倍率查询地址" : "Rate endpoint"}
                        >
                          <SelectValue
                            placeholder={
                              isZh ? "选择倍率查询地址" : "Choose rate endpoint"
                            }
                          />
                        </SelectTrigger>
                        <SelectContent>
                          {configs
                            .filter((config) =>
                              config.credential_ids.includes(credential.id),
                            )
                            .map((config) => (
                              <SelectItem key={config.id} value={config.id}>
                                {formatEndpointLabel(
                                  form.base_urls.find(
                                    (url) => url.id === config.base_url_id,
                                  )!,
                                  locale,
                                )}
                              </SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                      {credential.rate_source === "newapi" ? (
                        <Input
                          className="h-7 w-20 shrink-0 px-2 text-xs"
                          value={credential.rate_group}
                          placeholder={isZh ? "分组" : "Group"}
                          aria-label={isZh ? "NewAPI 分组" : "NewAPI group"}
                          onChange={(event) =>
                            updateKey(credential.id, {
                              rate_group: event.target.value,
                              ...CLEARED_RATE_STATUS,
                            })
                          }
                        />
                      ) : (
                        <div className="w-20 shrink-0" aria-hidden="true" />
                      )}
                      <div className="flex min-w-0 flex-1 items-center gap-1.5">
                        {credential.rate_multiplier !== null ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge
                                variant="secondary"
                                className="shrink-0 tabular-nums"
                              >
                                {credential.rate_multiplier}x
                              </Badge>
                            </TooltipTrigger>
                            {credential.rate_last_synced_at ? (
                              <TooltipContent>
                                {new Date(
                                  credential.rate_last_synced_at,
                                ).toLocaleString(locale)}
                              </TooltipContent>
                            ) : null}
                          </Tooltip>
                        ) : null}
                        {credential.rate_last_error ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="min-w-0 truncate text-xs text-destructive">
                                {credential.rate_last_error}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-sm">
                              {credential.rate_last_error}
                            </TooltipContent>
                          </Tooltip>
                        ) : credential.rate_multiplier === null ? (
                          <span className="truncate text-xs text-muted-foreground">
                            {canSyncRates
                              ? isZh
                                ? "未同步"
                                : "Not synced"
                              : isZh
                                ? "保存后可同步"
                                : "Save to sync"}
                          </span>
                        ) : null}
                      </div>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex shrink-0">
                            <Button
                              type="button"
                              variant="ghost"
                              size="xs"
                              disabled={
                                !canSyncRates || needsGroup || isSyncing
                              }
                              onClick={() => void syncRate(credential.id)}
                            >
                              <RefreshCcw
                                className={
                                  isSyncing ? "animate-spin" : undefined
                                }
                              />
                              {isZh ? "查询倍率" : "Sync rate"}
                            </Button>
                          </span>
                        </TooltipTrigger>
                        {canSyncRates ? null : (
                          <TooltipContent>
                            {isZh
                              ? "先保存渠道后再查询"
                              : "Save the channel first"}
                          </TooltipContent>
                        )}
                      </Tooltip>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
