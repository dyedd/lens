import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { Locale } from "./channelTypes";

/** Edits the model filter one API key uses for its upstream sync. */
export function ChannelModelPatternDialog({
  open,
  locale,
  onOpenChange,
  onSubmit,
  credentialOptions,
}: {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onSubmit: (credentialId: string, pattern: string) => void;
  credentialOptions: Array<{ id: string; label: string; pattern: string }>;
}) {
  const [credentialId, setCredentialId] = useState(
    credentialOptions[0]?.id ?? "",
  );
  const [pattern, setPattern] = useState(credentialOptions[0]?.pattern ?? "");
  const wasOpen = useRef(false);

  // Seed only on the open transition so typing is never overwritten.
  useEffect(() => {
    if (open && !wasOpen.current) {
      const active = credentialOptions[0];
      if (active) {
        setCredentialId(active.id);
        setPattern(active.pattern);
      }
    }
    wasOpen.current = open;
  }, [open, credentialOptions]);

  const patternError = pattern.trim() !== "" && !isValidPattern(pattern);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-md"
        title={locale === "zh-CN" ? "模型规则" : "Model rule"}
        description={
          locale === "zh-CN"
            ? "同步时按整名匹配筛选上游模型；留空不自动同步，填 * 才同步该 Key 能看到的全部模型。"
            : "Sync keeps whole-name matches. Leave empty to keep manual models; use * to keep the full catalog."
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
              disabled={patternError || !credentialId}
              onClick={() => {
                onSubmit(credentialId, pattern);
                onOpenChange(false);
              }}
            >
              {locale === "zh-CN" ? "保存" : "Save"}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          {credentialOptions.length > 1 ? (
            <Field>
              <FieldLabel>
                {locale === "zh-CN" ? "API Key" : "API Key"}
              </FieldLabel>
              <Select
                value={credentialId}
                onValueChange={(value) => {
                  setCredentialId(value);
                  setPattern(
                    credentialOptions.find((item) => item.id === value)
                      ?.pattern ?? "",
                  );
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
          <div className="flex min-w-0 flex-col gap-1">
            <Label
              className="text-xs font-normal text-muted-foreground"
              htmlFor="channel-model-pattern"
            >
              {locale === "zh-CN" ? "过滤规则" : "Filter"}
            </Label>
            <Textarea
              id="channel-model-pattern"
              value={pattern}
              onChange={(event) => setPattern(event.target.value)}
              placeholder={"(?i)^gpt-4.*|.*claude-3.*"}
              aria-invalid={patternError || undefined}
              className="max-h-48 font-mono placeholder:font-sans"
            />
            <p className="text-xs leading-5 text-muted-foreground">
              {locale === "zh-CN"
                ? "整名匹配：填 gpt-4 只匹配 gpt-4，要用 gpt-4.* 才能匹配整个系列。"
                : "Whole-name match: gpt-4 keeps only gpt-4; use gpt-4.* for the family."}
            </p>
            {patternError ? (
              <p className="text-xs text-destructive">
                {locale === "zh-CN" ? "正则表达式无效" : "Invalid regex"}
              </p>
            ) : null}
          </div>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}

/** Mirrors the backend check so an unusable rule is caught before saving. */
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
