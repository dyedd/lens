import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { Locale } from "./channelTypes";

export function ChannelModelPatternDialog({
  open,
  locale,
  onOpenChange,
  onSubmit,
  credentialOptions,
  supportsModelListing,
}: {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    credentialId: string,
    pattern: string,
    signal: AbortSignal,
  ) => Promise<boolean>;
  credentialOptions: Array<{ id: string; label: string }>;
  supportsModelListing: boolean;
}) {
  const [credentialId, setCredentialId] = useState(
    credentialOptions[0]?.id ?? "",
  );
  const [pattern, setPattern] = useState("");
  const wasOpen = useRef(false);
  const [isApplying, setIsApplying] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    if (open && !wasOpen.current) {
      setCredentialId(credentialOptions[0]?.id ?? "");
      setPattern("");
    }
    wasOpen.current = open;
  }, [open, credentialOptions]);

  useEffect(() => {
    if (!open) return;
    return () => {
      controller.current?.abort();
      controller.current = null;
      setIsApplying(false);
    };
  }, [open]);

  const patternError = pattern
    .split(/\r?\n/)
    .some((line) => !isValidPattern(line));

  async function applyPattern() {
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setIsApplying(true);
    try {
      const applied = await onSubmit(credentialId, pattern, request.signal);
      if (applied && !request.signal.aborted) onOpenChange(false);
    } finally {
      if (controller.current === request) {
        controller.current = null;
        setIsApplying(false);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-md"
        title={locale === "zh-CN" ? "模型规则" : "Model rule"}
        description={
          supportsModelListing
            ? locale === "zh-CN"
              ? "每行一个模型名或正则，正则从上游目录匹配。"
              : "One model name or regex per line. Regex matches the upstream catalog."
            : locale === "zh-CN"
              ? "每行一个模型名。"
              : "One model name per line."
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={
                patternError || !pattern.trim() || !credentialId || isApplying
              }
              onClick={() => void applyPattern()}
            >
              {isApplying
                ? locale === "zh-CN"
                  ? "应用中..."
                  : "Applying..."
                : locale === "zh-CN"
                  ? "应用到列表"
                  : "Apply to list"}
            </Button>
          </>
        }
      >
        <FieldGroup className="gap-3">
          {credentialOptions.length > 1 ? (
            <Field>
              <FieldLabel>API Key</FieldLabel>
              <Select
                value={credentialId}
                disabled={isApplying}
                onValueChange={(value) => {
                  setCredentialId(value);
                  setPattern("");
                }}
              >
                <SelectTrigger aria-label="API Key">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {credentialOptions.map((credential) => (
                    <SelectItem key={credential.id} value={credential.id}>
                      {credential.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          <Field data-invalid={patternError || undefined}>
            <FieldLabel htmlFor="channel-model-pattern">
              {supportsModelListing
                ? locale === "zh-CN"
                  ? "模型名 / 正则"
                  : "Model names / regex"
                : locale === "zh-CN"
                  ? "模型名"
                  : "Model names"}
            </FieldLabel>
            <Textarea
              id="channel-model-pattern"
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
              placeholder={
                supportsModelListing
                  ? "gpt-4o\nclaude-3.5-sonnet\n^gemini-.*"
                  : "gpt-4o\nclaude-3.5-sonnet"
              }
              disabled={isApplying}
              aria-invalid={patternError || undefined}
              className="max-h-48 font-mono placeholder:font-sans"
            />
            <FieldDescription>
              {locale === "zh-CN"
                ? "一次性添加到列表，保存后生效。"
                : "Add to this list once; save to persist."}
            </FieldDescription>
            {patternError ? (
              <p className="text-xs text-destructive">
                {locale === "zh-CN" ? "正则表达式无效" : "Invalid regex"}
              </p>
            ) : null}
          </Field>
        </FieldGroup>
      </AppDialogContent>
    </Dialog>
  );
}

function isValidPattern(pattern: string) {
  const trimmed = pattern.trim();
  if (!trimmed || trimmed === "*") return true;
  if (!/[*?+[\]{}()^$|\\]/.test(trimmed)) return true;
  try {
    new RegExp(
      `^(?:${trimmed
        .replace(/^\(\?[aiLmsux]+\)/, "")
        .replace(/^\^/, "")
        .replace(/\$$/, "")})$`,
      "i",
    );
    return true;
  } catch {
    return false;
  }
}
