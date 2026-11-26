import { useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  SettingsFieldList,
  SettingsFieldRow,
} from "@/components/ui/SettingsLayout";
import { Switch } from "@/components/ui/Switch";
import { TabsContent } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import {
  isPrivacyAction,
  type PrivacyCategory,
  type PrivacyPreview,
  previewPrivacy,
} from "@/lib/api/privacy";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { SettingsSectionCard } from "./SettingsSectionCard";
import type { useSettingsDraft } from "./useSettingsDraft";

export function privacyCategoryLabel(
  locale: Locale,
  category: PrivacyCategory,
) {
  return {
    secrets: titleForLocale(locale, "密钥与密码", "Secrets"),
    personal: titleForLocale(locale, "个人信息", "Personal data"),
    custom: titleForLocale(locale, "自定义", "Custom"),
  }[category];
}

function PrivacyRuleField({
  name,
  label,
  description,
  values,
  maxLength,
  onCommit,
  locale,
}: {
  name: string;
  label: string;
  description: string;
  values: string[];
  maxLength: number;
  onCommit: (values: string[]) => Promise<void>;
  locale: Locale;
}) {
  const id = useId();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  return (
    <Field data-invalid={Boolean(error)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <FieldDescription id={`${id}-hint`}>{description}</FieldDescription>
      <Textarea
        key={JSON.stringify(values)}
        id={id}
        name={name}
        defaultValue={values.join("\n")}
        rows={3}
        maxLength={maxLength}
        spellCheck={false}
        autoCapitalize="none"
        autoCorrect="off"
        aria-invalid={Boolean(error)}
        aria-describedby={`${id}-hint${error ? ` ${id}-error` : ""}`}
        readOnly={pending}
        onChange={() => setError("")}
        onBlur={async (event) => {
          const next = event.currentTarget.value
            .split("\n")
            .filter((line) => line.trim());
          if (JSON.stringify(next) === JSON.stringify(values)) return;
          setPending(true);
          try {
            await onCommit(next);
          } catch {
            setError(
              titleForLocale(
                locale,
                "规则无效，请检查格式、长度和空匹配。",
                "Invalid rules. Check syntax, length, and empty matches.",
              ),
            );
          } finally {
            setPending(false);
          }
        }}
      />
      <p id={`${id}-error`} role="status" className="text-xs text-destructive">
        {error}
      </p>
    </Field>
  );
}

export function PrivacySettingsSection({
  locale,
  settings,
}: {
  locale: Locale;
  settings: ReturnType<typeof useSettingsDraft>;
}) {
  const config = settings.draft.privacyConfig;
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<PrivacyPreview | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const update = settings.updatePrivacyConfig;
  const actionLabels = {
    mask: titleForLocale(locale, "替换并恢复", "Mask and restore"),
    warn: titleForLocale(locale, "仅记录命中", "Warn only"),
    block: titleForLocale(locale, "阻止请求", "Block request"),
  };

  return (
    <TabsContent value="privacy" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "规则隐私", "Rule privacy")}
      >
        <form
          className="flex flex-col gap-6"
          aria-label={titleForLocale(locale, "规则隐私", "Rule privacy")}
          onSubmit={async (event) => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            const entries = (name: string) =>
              String(fields.get(name) ?? "")
                .split("\n")
                .filter((line) => line.trim());
            const previewConfig = {
              ...config,
              words: entries("words"),
              regex_rules: entries("regex_rules").map((pattern) => ({
                pattern,
              })),
              exceptions: entries("exceptions"),
            };
            setPending(true);
            setError("");
            try {
              setPreview(await previewPrivacy(text, previewConfig));
            } catch {
              setError(
                titleForLocale(
                  locale,
                  "预览失败，请检查规则。",
                  "Preview failed. Check the rules.",
                ),
              );
            } finally {
              setPending(false);
            }
          }}
        >
          <p className="text-xs text-muted-foreground">
            {titleForLocale(
              locale,
              "处理对话正文、工具参数与结果、Embeddings、Rerank 和图片提示词。图片、二进制及附件内容不扫描。",
              "Processes conversation text, tool arguments and results, embeddings, rerank text, and image prompts. Images, binary data, and attachments are not scanned.",
            )}
          </p>
          <SettingsFieldList>
            <SettingsFieldRow
              title={titleForLocale(
                locale,
                "启用隐私规则",
                "Enable privacy rules",
              )}
              htmlFor="privacy-enabled"
            >
              <Switch
                id="privacy-enabled"
                checked={config.enabled}
                onCheckedChange={(enabled) => update({ enabled })}
                disabled={!settings.isSettingsReady}
              />
            </SettingsFieldRow>
            {(["secrets", "personal"] as const).map((category) => (
              <SettingsFieldRow
                key={category}
                htmlFor={`privacy-${category}`}
                title={privacyCategoryLabel(locale, category)}
              >
                <Switch
                  id={`privacy-${category}`}
                  checked={config.categories.includes(category)}
                  onCheckedChange={(enabled) =>
                    update({
                      categories: enabled
                        ? [...config.categories, category]
                        : config.categories.filter(
                            (entry) => entry !== category,
                          ),
                    })
                  }
                  disabled={!settings.isSettingsReady}
                />
              </SettingsFieldRow>
            ))}
            <SettingsFieldRow
              title={titleForLocale(locale, "命中动作", "Action on match")}
              htmlFor="privacy-action"
            >
              <Select
                value={config.action}
                onValueChange={(action) => {
                  if (isPrivacyAction(action)) update({ action });
                }}
                disabled={!settings.isSettingsReady}
              >
                <SelectTrigger id="privacy-action">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {(["mask", "warn", "block"] as const).map((action) => (
                      <SelectItem key={action} value={action}>
                        {actionLabels[action]}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </SettingsFieldRow>
          </SettingsFieldList>
          {config.action === "warn" && (
            <p className="text-xs text-muted-foreground">
              {titleForLocale(
                locale,
                "仅记录命中会把原文发送到上游，日志仍会脱敏。",
                "Warn only sends the original text upstream. Logs are still redacted.",
              )}
            </p>
          )}
          <FieldGroup>
            {(["words", "regex_rules", "exceptions"] as const).map((field) => (
              <PrivacyRuleField
                name={field}
                key={field}
                locale={locale}
                label={
                  {
                    words: titleForLocale(locale, "自定义词语", "Custom words"),
                    regex_rules: titleForLocale(
                      locale,
                      "自定义正则",
                      "Custom regex",
                    ),
                    exceptions: titleForLocale(
                      locale,
                      "例外词语",
                      "Exceptions",
                    ),
                  }[field]
                }
                description={
                  field === "regex_rules"
                    ? titleForLocale(
                        locale,
                        "每行一条，最多 20 条，每条 512 个字符。不允许空匹配。",
                        "One per line, up to 20 patterns of 512 characters. Empty matches are rejected.",
                      )
                    : titleForLocale(
                        locale,
                        "每行一项，最多 100 项，每项 256 个字符。",
                        "One per line, up to 100 entries of 256 characters.",
                      )
                }
                values={
                  field === "regex_rules"
                    ? config.regex_rules.map((rule) => rule.pattern)
                    : config[field]
                }
                maxLength={field === "regex_rules" ? 10260 : 25700}
                onCommit={async (values) => {
                  const next = {
                    ...config,
                    [field]:
                      field === "regex_rules"
                        ? values.map((pattern) => ({ pattern }))
                        : values,
                  };
                  await previewPrivacy("", next);
                  update({ [field]: next[field] });
                }}
              />
            ))}
          </FieldGroup>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="privacy-preview-text">
                {titleForLocale(locale, "规则预览", "Rule preview")}
              </FieldLabel>
              <FieldDescription id="privacy-preview-hint">
                {titleForLocale(
                  locale,
                  "在 Lens 服务端运行规则，不调用上游，也不保存预览文本。",
                  "Runs rules on the Lens server without upstream calls or saving preview text.",
                )}
              </FieldDescription>
              <Textarea
                id="privacy-preview-text"
                name="text"
                rows={4}
                value={text}
                maxLength={100000}
                aria-describedby="privacy-preview-hint"
                onChange={(event) => {
                  setText(event.target.value);
                  setPreview(null);
                }}
              />
            </Field>
            <Button
              type="submit"
              variant="outline"
              disabled={pending}
              className="self-start"
            >
              {titleForLocale(locale, "预览", "Preview")}
            </Button>
            <div role="status" className="text-xs">
              {error ||
                (preview &&
                  (preview.blocked
                    ? titleForLocale(
                        locale,
                        "请求将被阻止",
                        "Request will be blocked",
                      )
                    : preview.hits
                        .map(
                          (hit) =>
                            `${privacyCategoryLabel(locale, hit.category)} ${hit.count}`,
                        )
                        .join(" · ")))}
            </div>
            {preview && (
              <pre className="whitespace-pre-wrap break-words rounded-md bg-muted/35 p-3 text-xs">
                {preview.text}
              </pre>
            )}
          </FieldGroup>
          <p className="text-xs text-muted-foreground">
            {titleForLocale(
              locale,
              "规则检测可能遗漏信息。替换文本会影响模型理解、向量与排序结果。已有日志保持原样，备份中的日志按隐私设置清理。",
              "Rules can miss sensitive data. Masking changes model interpretation, embeddings, and ranking. Existing logs remain unchanged; backup logs are cleaned using privacy settings.",
            )}
          </p>
        </form>
      </SettingsSectionCard>
    </TabsContent>
  );
}
