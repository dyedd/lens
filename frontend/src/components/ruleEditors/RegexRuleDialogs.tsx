import { type KeyboardEvent, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useRegexRules } from "@/hooks/useRegexRules";
import { getApiErrorMessage } from "@/lib/api/client";
import type { RegexRule, RegexRuleRequest } from "@/lib/api/regexRules";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import {
  compileRegexRulePattern,
  listRegexRuleUsageLines,
} from "@/lib/regexRules";

const NAME_MAX_LENGTH = 60;
const PATTERN_MAX_LENGTH = 500;
const DESCRIPTION_MAX_LENGTH = 200;

/** Create a library rule, or edit one everywhere it is used. */
export function RegexRuleEditorDialog({
  locale,
  rule,
  onClose,
  onSaved,
}: {
  locale: Locale;
  /** The rule to edit, or null to create one. */
  rule: RegexRule | null;
  onClose: () => void;
  onSaved?: (rule: RegexRule) => void;
}) {
  const library = useRegexRules();
  const [draft, setDraft] = useState<RegexRuleRequest>({
    name: rule?.name ?? "",
    pattern: rule?.pattern ?? "",
    description: rule?.description ?? "",
  });
  const [isSaving, setIsSaving] = useState(false);
  const name = draft.name.trim();
  const pattern = draft.pattern.trim();
  const isDuplicateName =
    Boolean(name) &&
    library.rules.some(
      (item) =>
        item.id !== rule?.id && item.name.toLowerCase() === name.toLowerCase(),
    );
  const isPatternInvalid =
    Boolean(pattern) && !compileRegexRulePattern(pattern);
  const canSave =
    Boolean(name && pattern) &&
    !isDuplicateName &&
    !isPatternInvalid &&
    !isSaving;

  async function handleSave() {
    if (!canSave) return;
    setIsSaving(true);
    const request = { name, pattern, description: draft.description.trim() };
    try {
      const savedRule = rule
        ? await library.updateRule(rule.id, request)
        : await library.createRule(request);
      toast.success(
        rule
          ? titleForLocale(locale, "规则已更新", "Rule updated")
          : titleForLocale(locale, "规则已创建", "Rule created"),
      );
      onSaved?.(savedRule);
      onClose();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "保存规则失败", "Failed to save rule"),
        ),
      );
      setIsSaving(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void handleSave();
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !isSaving) onClose();
      }}
    >
      <AppDialogContent
        title={
          rule
            ? titleForLocale(locale, "编辑规则", "Edit rule")
            : titleForLocale(locale, "新建规则", "New rule")
        }
        description={
          rule && (rule.sites.length || rule.groups.length)
            ? titleForLocale(
                locale,
                `修改会同步到使用此规则的 ${rule.sites.length} 个渠道、${rule.groups.length} 个模型组`,
                `Changes apply to the ${rule.sites.length} channels and ${rule.groups.length} groups that use this rule`,
              )
            : undefined
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isSaving}
              onClick={onClose}
            >
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!canSave}
              onClick={() => void handleSave()}
            >
              {isSaving
                ? titleForLocale(locale, "保存中...", "Saving...")
                : titleForLocale(locale, "保存", "Save")}
            </Button>
          </>
        }
      >
        <FieldGroup className="gap-4" onKeyDown={handleKeyDown}>
          <Field data-invalid={isDuplicateName}>
            <FieldLabel htmlFor="regex-rule-name" required>
              {titleForLocale(locale, "名称", "Name")}
            </FieldLabel>
            <Input
              id="regex-rule-name"
              value={draft.name}
              maxLength={NAME_MAX_LENGTH}
              aria-invalid={isDuplicateName}
              onChange={(event) =>
                setDraft({ ...draft, name: event.target.value })
              }
              autoFocus
            />
            {isDuplicateName ? (
              <p className="text-xs text-destructive">
                {titleForLocale(locale, "名称已存在", "Name already exists")}
              </p>
            ) : null}
          </Field>
          <Field data-invalid={isPatternInvalid}>
            <FieldLabel htmlFor="regex-rule-pattern" required>
              {titleForLocale(locale, "正则", "Pattern")}
            </FieldLabel>
            <Input
              id="regex-rule-pattern"
              value={draft.pattern}
              maxLength={PATTERN_MAX_LENGTH}
              aria-invalid={isPatternInvalid}
              onChange={(event) =>
                setDraft({ ...draft, pattern: event.target.value })
              }
              placeholder="^claude-(opus|sonnet)"
              className="font-mono"
            />
            <p
              className={
                isPatternInvalid
                  ? "text-xs text-destructive"
                  : "text-xs text-muted-foreground"
              }
            >
              {isPatternInvalid
                ? titleForLocale(locale, "正则表达式无效", "Invalid regex")
                : titleForLocale(
                    locale,
                    "不区分大小写，匹配模型名的任意位置",
                    "Case-insensitive; matches anywhere in the model name",
                  )}
            </p>
          </Field>
          <Field>
            <FieldLabel htmlFor="regex-rule-description">
              {titleForLocale(locale, "说明", "Description")}
            </FieldLabel>
            <Input
              id="regex-rule-description"
              value={draft.description}
              maxLength={DESCRIPTION_MAX_LENGTH}
              onChange={(event) =>
                setDraft({ ...draft, description: event.target.value })
              }
            />
          </Field>
        </FieldGroup>
      </AppDialogContent>
    </Dialog>
  );
}

/** Confirm deleting a rule from the library and from everything using it. */
export function DeleteRegexRuleDialog({
  locale,
  rule,
  onClose,
  onDeleted,
}: {
  locale: Locale;
  rule: RegexRule;
  onClose: () => void;
  onDeleted?: (ruleId: string) => void;
}) {
  const library = useRegexRules();
  const [isDeleting, setIsDeleting] = useState(false);
  const usageLines = listRegexRuleUsageLines(rule, locale);

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await library.deleteRule(rule.id);
      toast.success(titleForLocale(locale, "规则已删除", "Rule deleted"));
      onDeleted?.(rule.id);
      onClose();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "删除规则失败", "Failed to delete rule"),
        ),
      );
      setIsDeleting(false);
    }
  }

  return (
    <ConfirmDeleteDialog
      open
      locale={locale}
      title={titleForLocale(locale, "删除规则", "Delete rule")}
      description={
        usageLines.length
          ? titleForLocale(
              locale,
              `删除规则「${rule.name}」？将从 ${rule.sites.length} 个渠道、${rule.groups.length} 个模型组中移除。`,
              `Delete rule "${rule.name}"? It will be removed from ${rule.sites.length} channels and ${rule.groups.length} groups.`,
            )
          : titleForLocale(
              locale,
              `删除规则「${rule.name}」？没有渠道或模型组使用它。`,
              `Delete rule "${rule.name}"? No channel or group uses it.`,
            )
      }
      isBusy={isDeleting}
      onOpenChange={(open) => {
        if (!open && !isDeleting) onClose();
      }}
      onConfirm={() => void handleDelete()}
    >
      {usageLines.length ? (
        <div className="space-y-0.5 text-xs text-muted-foreground">
          {usageLines.map((line) => (
            <p key={line} className="break-words">
              {line}
            </p>
          ))}
        </div>
      ) : null}
    </ConfirmDeleteDialog>
  );
}
