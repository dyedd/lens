import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { isPendingCredentialId, maskApiKey } from "./channelModels";
import type { FormCredential, Locale } from "./channelTypes";

type Props = {
  locale: Locale;
  inputId: string;
  required?: boolean;
  newApiKeysLines: string;
  credentials: FormCredential[];
  onNewApiKeysChange: (value: string) => void;
  onRemove: (credentialId: string) => void;
};

/** Renders bulk API keys for the primary URL or an extra endpoint. */
export function ChannelCredentialSection({
  locale,
  inputId,
  required = false,
  newApiKeysLines,
  credentials,
  onNewApiKeysChange,
  onRemove,
}: Props) {
  const existingKeys = credentials.filter(
    (item) => !isPendingCredentialId(item.id),
  );

  return (
    <div className="min-w-0 space-y-1">
      <Label
        htmlFor={inputId}
        required={required}
        className="text-xs font-normal text-muted-foreground"
      >
        {existingKeys.length
          ? locale === "zh-CN"
            ? "新增 API Key"
            : "Add API keys"
          : locale === "zh-CN"
            ? "密钥（支持多密钥轮询）"
            : "API keys (rotated)"}
      </Label>
      <Textarea
        id={inputId}
        required={required && existingKeys.length === 0}
        spellCheck={false}
        wrap="off"
        className="h-24 resize-none overflow-auto whitespace-pre font-mono text-xs [field-sizing:fixed]"
        placeholder={
          existingKeys.length
            ? locale === "zh-CN"
              ? "每行一个新增 API Key，留空则不新增"
              : "One new API key per line; leave empty to skip"
            : locale === "zh-CN"
              ? "每行一个 API Key"
              : "One API key per line"
        }
        value={newApiKeysLines}
        onChange={(event) => onNewApiKeysChange(event.target.value)}
      />
      {existingKeys.length > 0 ? (
        <div className="mt-2 space-y-1.5">
          <div className="text-[11px] leading-4 text-muted-foreground">
            {locale === "zh-CN"
              ? `已有 ${existingKeys.length} 个 Key`
              : `${existingKeys.length} existing keys`}
          </div>
          <div className="overflow-hidden rounded-md bg-muted/35">
            {existingKeys.map((item) => (
              <div
                key={item.id}
                className="group/key flex h-8 items-center gap-3 border-b border-border/40 px-2.5 text-xs last:border-b-0"
              >
                <span className="min-w-0 flex-1 truncate font-mono">
                  {maskApiKey(item.api_key)}
                </span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="size-6 text-muted-foreground opacity-70 hover:text-foreground group-hover/key:opacity-100"
                      aria-label={
                        locale === "zh-CN" ? "删除 API Key" : "Delete API key"
                      }
                      onClick={() => onRemove(item.id)}
                    >
                      <Trash2 className="size-3.5 stroke-1" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    {locale === "zh-CN" ? "删除" : "Delete"}
                  </TooltipContent>
                </Tooltip>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
