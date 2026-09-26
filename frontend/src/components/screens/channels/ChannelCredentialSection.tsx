import { useQueryClient } from "@tanstack/react-query";
import { RefreshCcw, Trash2 } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { SiteCredential } from "@/lib/api/sites";
import {
  credentialLabel,
  isPendingCredentialId,
  maskApiKey,
  replacePendingCredentials,
} from "./channelModels";
import type { FormCredential, FormState, Locale } from "./channelTypes";

type Props = {
  locale: Locale;
  inputId: string;
  required?: boolean;
  /** Empty for the keys shared by the primary URL and URLs reusing them. */
  baseUrlId: string;
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

/** Renders the saved keys of one URL scope and a textarea for new keys. */
export function ChannelCredentialSection({
  locale,
  inputId,
  required = false,
  baseUrlId,
  form,
  setForm,
  siteId,
  canSyncRates,
}: Props) {
  const isZh = locale === "zh-CN";
  const queryClient = useQueryClient();
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const newApiKeysLines = baseUrlId
    ? (form.base_urls.find((item) => item.id === baseUrlId)?.newApiKeysLines ??
      "")
    : form.newApiKeysLines;
  // Keep the site-wide index so fallback labels match the rest of the app.
  const savedKeys = form.credentials
    .map((credential, index) => ({ credential, index }))
    .filter(
      ({ credential }) =>
        credential.baseUrlId === baseUrlId &&
        !isPendingCredentialId(credential.id),
    );

  function changeNewKeys(value: string) {
    setForm((current) => ({
      ...current,
      newApiKeysLines: baseUrlId ? current.newApiKeysLines : value,
      base_urls: baseUrlId
        ? current.base_urls.map((item) =>
            item.id === baseUrlId ? { ...item, newApiKeysLines: value } : item,
          )
        : current.base_urls,
      credentials: replacePendingCredentials(
        current.credentials,
        value,
        baseUrlId,
      ),
    }));
  }

  function updateKey(credentialId: string, patch: Partial<FormCredential>) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.map((item) =>
        item.id === credentialId ? { ...item, ...patch } : item,
      ),
    }));
  }

  function removeKey(credentialId: string) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.filter(
        (item) => item.id !== credentialId,
      ),
    }));
  }

  async function copyKey(apiKey: string) {
    try {
      await navigator.clipboard.writeText(apiKey);
      toast.success(isZh ? "已复制 API Key" : "API key copied");
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
    <div className="min-w-0 space-y-1">
      <Label
        htmlFor={inputId}
        required={required}
        className="text-xs font-normal text-muted-foreground"
      >
        {savedKeys.length
          ? isZh
            ? "新增 API Key"
            : "Add API keys"
          : isZh
            ? "密钥（支持多密钥轮询）"
            : "API keys (rotated)"}
      </Label>
      <Textarea
        id={inputId}
        required={required && savedKeys.length === 0}
        spellCheck={false}
        wrap="off"
        className="h-24 resize-none overflow-auto whitespace-pre font-mono text-xs [field-sizing:fixed]"
        placeholder={
          savedKeys.length
            ? isZh
              ? "每行一个新增 API Key，留空则不新增"
              : "One new API key per line; leave empty to skip"
            : isZh
              ? "每行一个 API Key"
              : "One API key per line"
        }
        value={newApiKeysLines}
        onChange={(event) => changeNewKeys(event.target.value)}
      />
      {savedKeys.length > 0 ? (
        <div className="mt-2 space-y-1.5">
          <div className="text-[11px] leading-4 text-muted-foreground">
            {isZh
              ? `已有 ${savedKeys.length} 个 Key`
              : `${savedKeys.length} existing keys`}
          </div>
          <div className="overflow-hidden rounded-md bg-muted/35">
            {savedKeys.map(({ credential, index }) => {
              const isSyncing = syncingId === credential.id;
              const needsGroup =
                credential.rate_source === "newapi" &&
                !credential.rate_group.trim();
              return (
                <div
                  key={credential.id}
                  className="space-y-1.5 border-b border-border/40 px-2.5 py-1.5 text-xs last:border-b-0"
                >
                  <div className="flex h-7 items-center gap-2">
                    <span className="w-12 shrink-0 truncate text-[11px] text-muted-foreground tabular-nums">
                      {credentialLabel({ name: "" }, index, locale)}
                    </span>
                    <Input
                      className="h-7 min-w-0 flex-1"
                      value={credential.name}
                      placeholder={isZh ? "备注" : "Remark"}
                      aria-label={isZh ? "密钥备注" : "Key remark"}
                      onChange={(event) =>
                        updateKey(credential.id, { name: event.target.value })
                      }
                    />
                    <button
                      type="button"
                      className="w-[88px] shrink-0 truncate text-left font-mono text-[11px] text-muted-foreground hover:text-foreground"
                      title={isZh ? "复制完整 Key" : "Copy full key"}
                      onClick={() => void copyKey(credential.api_key)}
                    >
                      {maskApiKey(credential.api_key)}
                    </button>
                    <Select
                      value={credential.rate_source}
                      onValueChange={(value) =>
                        updateKey(credential.id, {
                          rate_source: value as FormCredential["rate_source"],
                          rate_group:
                            value === "newapi" ? credential.rate_group : "",
                          ...CLEARED_RATE_STATUS,
                        })
                      }
                    >
                      <SelectTrigger
                        className="h-7 w-[92px] shrink-0 px-2"
                        aria-label={isZh ? "倍率来源" : "Rate source"}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">
                          {isZh ? "不查倍率" : "No rate"}
                        </SelectItem>
                        <SelectItem value="sub2api">Sub2API</SelectItem>
                        <SelectItem value="newapi">NewAPI</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="size-6 shrink-0 text-muted-foreground hover:text-foreground"
                      aria-label={isZh ? "删除 API Key" : "Delete API key"}
                      title={isZh ? "删除" : "Delete"}
                      onClick={() => removeKey(credential.id)}
                    >
                      <Trash2 className="size-3.5 stroke-1" />
                    </Button>
                  </div>
                  {credential.rate_source !== "none" ? (
                    <div className="flex h-7 items-center gap-2 pl-14">
                      {credential.rate_source === "newapi" ? (
                        <Input
                          className="h-7 w-24 shrink-0"
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
                      ) : null}
                      <div className="flex min-w-0 flex-1 items-center gap-1.5">
                        {credential.rate_multiplier !== null ? (
                          <Badge
                            variant="secondary"
                            className="shrink-0 tabular-nums"
                            title={
                              credential.rate_last_synced_at
                                ? new Date(
                                    credential.rate_last_synced_at,
                                  ).toLocaleString(locale)
                                : undefined
                            }
                          >
                            {credential.rate_multiplier}x
                          </Badge>
                        ) : null}
                        {credential.rate_last_error ? (
                          <span
                            className="min-w-0 truncate text-[11px] text-destructive"
                            title={credential.rate_last_error}
                          >
                            {credential.rate_last_error}
                          </span>
                        ) : credential.rate_multiplier === null ? (
                          <span className="truncate text-[11px] text-muted-foreground">
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
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        className="shrink-0"
                        disabled={!canSyncRates || needsGroup || isSyncing}
                        title={
                          canSyncRates
                            ? undefined
                            : isZh
                              ? "先保存渠道"
                              : "Save the channel first"
                        }
                        onClick={() => void syncRate(credential.id)}
                      >
                        <RefreshCcw
                          className={isSyncing ? "animate-spin" : undefined}
                        />
                        {isZh ? "同步倍率" : "Sync rate"}
                      </Button>
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
