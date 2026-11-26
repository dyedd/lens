import { useId, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
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
  placeholder,
  values,
  maxLength,
  onCommit,
  locale,
}: {
  name: string;
  label: string;
  placeholder: string;
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
      <Textarea
        key={JSON.stringify(values)}
        id={id}
        name={name}
        defaultValue={values.join("\n")}
        rows={3}
        maxLength={maxLength}
        placeholder={placeholder}
        spellCheck={false}
        autoCapitalize="none"
        autoCorrect="off"
        className="font-mono placeholder:font-sans"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
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
      {error ? (
        <p
          id={`${id}-error`}
          role="status"
          className="text-xs text-destructive"
        >
          {error}
        </p>
      ) : null}
    </Field>
  );
}

/** Render the privacy redaction, action, custom rules, and live preview tab. */
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

  return (
    <TabsContent value="privacy" className="mt-0">
      <form
        className="space-y-8"
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
        <SettingsSectionCard
          title={titleForLocale(locale, "规则与检测", "Rules & detection")}
        >
          <div className="space-y-8">
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

              <SettingsFieldRow
                title={titleForLocale(locale, "命中动作", "Action on match")}
                controlClassName="md:w-auto xl:w-auto"
              >
                <SegmentedControl
                  value={config.action}
                  onValueChange={(action) => {
                    if (settings.isSettingsReady && isPrivacyAction(action)) {
                      update({ action });
                    }
                  }}
                  options={[
                    {
                      value: "mask",
                      label: titleForLocale(
                        locale,
                        "替换并恢复",
                        "Mask & restore",
                      ),
                    },
                    {
                      value: "warn",
                      label: titleForLocale(locale, "仅记录", "Warn only"),
                    },
                    {
                      value: "block",
                      label: titleForLocale(locale, "阻止请求", "Block"),
                    },
                  ]}
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
            </SettingsFieldList>

            <FieldGroup className="gap-5">
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <PrivacyRuleField
                  name="words"
                  locale={locale}
                  label={titleForLocale(locale, "自定义词语", "Custom words")}
                  placeholder="internal-project"
                  values={config.words}
                  maxLength={25700}
                  onCommit={async (values) => {
                    const next = { ...config, words: values };
                    await previewPrivacy("", next);
                    update({ words: next.words });
                  }}
                />
                <PrivacyRuleField
                  name="exceptions"
                  locale={locale}
                  label={titleForLocale(locale, "例外词语", "Exceptions")}
                  placeholder="example@company.com"
                  values={config.exceptions}
                  maxLength={25700}
                  onCommit={async (values) => {
                    const next = { ...config, exceptions: values };
                    await previewPrivacy("", next);
                    update({ exceptions: next.exceptions });
                  }}
                />
              </div>

              <PrivacyRuleField
                name="regex_rules"
                locale={locale}
                label={titleForLocale(locale, "自定义正则", "Custom regex")}
                placeholder="^proj_[a-zA-Z0-9]{16,}$"
                values={config.regex_rules.map((rule) => rule.pattern)}
                maxLength={10260}
                onCommit={async (values) => {
                  const next = {
                    ...config,
                    regex_rules: values.map((pattern) => ({ pattern })),
                  };
                  await previewPrivacy("", next);
                  update({ regex_rules: next.regex_rules });
                }}
              />
            </FieldGroup>
          </div>
        </SettingsSectionCard>

        <SettingsSectionCard
          title={titleForLocale(locale, "规则预览", "Rule preview")}
          actions={
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={pending}
            >
              {pending
                ? titleForLocale(locale, "测试中...", "Testing...")
                : titleForLocale(locale, "运行预览", "Run preview")}
            </Button>
          }
        >
          <div className="space-y-4">
            <Textarea
              id="privacy-preview-text"
              name="text"
              rows={4}
              value={text}
              maxLength={100000}
              placeholder={titleForLocale(
                locale,
                "输入包含密钥、邮箱或自定义敏感词的示例文本...",
                "Paste sample text containing secrets, emails, or custom words...",
              )}
              aria-label={titleForLocale(locale, "规则预览", "Rule preview")}
              onChange={(event) => {
                setText(event.target.value);
                setPreview(null);
              }}
            />

            {error || preview ? (
              <div className="space-y-2.5">
                <div
                  role="status"
                  className="flex flex-wrap items-center gap-2"
                >
                  {error ? (
                    <span className="text-xs text-destructive">{error}</span>
                  ) : preview?.blocked ? (
                    <Badge variant="destructive">
                      {titleForLocale(
                        locale,
                        "请求将被阻止",
                        "Request will be blocked",
                      )}
                    </Badge>
                  ) : preview?.hits.length ? (
                    preview.hits.map((hit) => (
                      <Badge key={hit.category} variant="secondary">
                        {privacyCategoryLabel(locale, hit.category)} {hit.count}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {titleForLocale(locale, "未命中规则", "No rule hits")}
                    </span>
                  )}
                </div>
                {preview ? (
                  <pre className="whitespace-pre-wrap break-words border-l-2 border-border pl-3.5 py-1 font-mono text-[13px] leading-relaxed text-foreground">
                    {preview.text}
                  </pre>
                ) : null}
              </div>
            ) : null}
          </div>
        </SettingsSectionCard>
      </form>
    </TabsContent>
  );
}
