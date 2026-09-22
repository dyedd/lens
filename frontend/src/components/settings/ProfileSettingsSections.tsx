import { ListChecks, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { AccountSettings } from "@/components/settings/AccountSettings";
import { AppearanceSettings } from "@/components/settings/AppearanceSettings";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { TabsContent } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { parseModelTestPrompts } from "@/lib/modelTestPrompts";
import { SettingsSectionCard } from "./SettingsSectionCard";
import { SettingsSectionSeparator } from "./settingsLayout";
import type { useAccountSettings } from "./useAccountSettings";
import type { useSettingsDraft } from "./useSettingsDraft";

type AccountSettingsController = ReturnType<typeof useAccountSettings>;
type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

interface SettingsSectionProps {
  locale: Locale;
  settings: SettingsDraftController;
}

/** Render the appearance settings tab content. */
export function GeneralSettingsSection({
  locale,
  settings,
  account,
}: SettingsSectionProps & { account: AccountSettingsController }) {
  return (
    <TabsContent value="general" className="mt-0">
      <SettingsSectionCard title={titleForLocale(locale, "站点", "Site")}>
        <AppearanceSettings
          siteName={settings.draft.siteName}
          siteLogoUrl={settings.draft.siteLogoUrl}
          onSiteNameChange={(value) =>
            settings.setDraftValue("siteName", value)
          }
          onSiteLogoUrlChange={(value) =>
            settings.setDraftValue("siteLogoUrl", value)
          }
          timeZone={settings.draft.timeZone}
          onTimeZoneChange={(value) =>
            settings.setDraftValue("timeZone", value)
          }
        />
        <SettingsSectionSeparator />
        <h3 className="mb-4 text-sm font-semibold">
          {titleForLocale(locale, "账号", "Account")}
        </h3>
        <AccountSettingsSection locale={locale} account={account} embedded />
      </SettingsSectionCard>
    </TabsContent>
  );
}

/** Render the administrator account settings tab content. */
export function AccountSettingsSection({
  account,
  locale,
  embedded = false,
}: {
  account: AccountSettingsController;
  locale: Locale;
  embedded?: boolean;
}) {
  const content = (
    <AccountSettings
      username={account.accountForm.username}
      newPassword={account.accountForm.newPassword}
      confirmPassword={account.accountForm.confirmPassword}
      updatingAccount={account.isUpdatingAccount}
      onUsernameChange={account.setUsername}
      onNewPasswordChange={account.setNewPassword}
      onConfirmPasswordChange={account.setConfirmPassword}
      onSubmit={account.submitAccount}
    />
  );
  return embedded ? (
    <div className="mt-3">{content}</div>
  ) : (
    <SettingsSectionCard title={titleForLocale(locale, "账号", "Account")}>
      {content}
    </SettingsSectionCard>
  );
}

/** Render the model test prompt settings tab content. */
export function ModelTestSettingsSection({
  locale,
  settings,
}: SettingsSectionProps) {
  const prompts = parseModelTestPrompts(settings.draft.modelTestPrompts);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [promptDraft, setPromptDraft] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const selectedCount = prompts.filter((_, index) =>
    selected.has(index),
  ).length;
  const allSelected =
    prompts.length > 0 && prompts.every((_, index) => selected.has(index));
  const someSelected = prompts.some((_, index) => selected.has(index));

  function updatePrompts(nextPrompts: string[]) {
    settings.setDraftValue("modelTestPrompts", nextPrompts.join("\n"));
    setSelected(new Set());
  }

  function handleSelectAll(checked: boolean) {
    setSelected(
      checked ? new Set(prompts.map((_, index) => index)) : new Set(),
    );
  }

  function handleSelectOne(index: number, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(index);
      else next.delete(index);
      return next;
    });
  }

  function removeSelectedPrompts() {
    updatePrompts(prompts.filter((_, index) => !selected.has(index)));
    setBulkDeleteOpen(false);
  }

  function openCreateDialog() {
    setEditingIndex(null);
    setPromptDraft("");
    setDialogOpen(true);
  }

  function openEditDialog(index: number) {
    setEditingIndex(index);
    setPromptDraft(prompts[index] ?? "");
    setDialogOpen(true);
  }

  function savePrompt() {
    const nextPrompt = promptDraft.trim();
    if (!nextPrompt) return;
    const nextPrompts =
      editingIndex === null
        ? [...prompts, nextPrompt]
        : prompts.map((prompt, index) =>
            index === editingIndex ? nextPrompt : prompt,
          );
    updatePrompts(nextPrompts);
    setDialogOpen(false);
  }

  return (
    <>
      <TabsContent value="model-test" className="mt-0">
        <SettingsSectionCard
          title={titleForLocale(locale, "模型测试", "Model test")}
          actions={
            <div className="flex items-center gap-1.5">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
                    disabled={selectedCount === 0}
                    aria-label={titleForLocale(locale, "批量", "Bulk")}
                  >
                    <ListChecks className="size-3.5" />
                    {titleForLocale(locale, "批量", "Bulk")}
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-[220px] p-2">
                  <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                    {titleForLocale(
                      locale,
                      `已选 ${selectedCount} 项`,
                      `${selectedCount} selected`,
                    )}
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-7 w-full justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted hover:text-foreground"
                    disabled={selectedCount === 0}
                    onClick={() => setBulkDeleteOpen(true)}
                  >
                    <Trash2 className="size-3.5" />
                    {titleForLocale(locale, "批量删除", "Delete selected")}
                  </Button>
                </PopoverContent>
              </Popover>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
                onClick={openCreateDialog}
                disabled={prompts.length >= 20}
              >
                <Plus className="size-3.5" />
                {titleForLocale(locale, "添加问题", "Add prompt")}
              </Button>
            </div>
          }
        >
          <div className="mb-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>{titleForLocale(locale, "预设问题", "Preset prompts")}</span>
            <span>{prompts.length} / 20</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[44px] text-center">
                  <div className="flex h-7 items-center justify-center">
                    <Checkbox
                      checked={
                        allSelected
                          ? true
                          : someSelected
                            ? "indeterminate"
                            : false
                      }
                      onCheckedChange={(checked) =>
                        handleSelectAll(checked === true)
                      }
                      aria-label={titleForLocale(
                        locale,
                        "全选问题",
                        "Select all prompts",
                      )}
                      disabled={prompts.length === 0}
                    />
                  </div>
                </TableHead>
                <TableHead className="w-12 text-center">#</TableHead>
                <TableHead>
                  {titleForLocale(locale, "问题", "Prompt")}
                </TableHead>
                <TableHead className="w-20 text-right">
                  {titleForLocale(locale, "操作", "Actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prompts.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={4}
                    className="h-32 text-center text-muted-foreground"
                  >
                    {titleForLocale(
                      locale,
                      "暂无预设问题",
                      "No preset prompts",
                    )}
                  </TableCell>
                </TableRow>
              ) : null}
              {prompts.map((prompt, index) => (
                <TableRow
                  key={`${index}-${prompt}`}
                  data-state={selected.has(index) ? "selected" : undefined}
                >
                  <TableCell
                    className="w-[44px] py-1.5 text-center"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <div className="flex h-7 items-center justify-center">
                      <Checkbox
                        checked={selected.has(index)}
                        onCheckedChange={(checked) =>
                          handleSelectOne(index, checked === true)
                        }
                        aria-label={titleForLocale(
                          locale,
                          "选择问题",
                          "Select prompt",
                        )}
                      />
                    </div>
                  </TableCell>
                  <TableCell className="w-12 text-center text-muted-foreground">
                    {index + 1}
                  </TableCell>
                  <TableCell className="whitespace-normal break-words">
                    {prompt}
                  </TableCell>
                  <TableCell className="w-20">
                    <div className="flex justify-end gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none"
                        aria-label={titleForLocale(
                          locale,
                          "编辑问题",
                          "Edit prompt",
                        )}
                        title={titleForLocale(
                          locale,
                          "编辑问题",
                          "Edit prompt",
                        )}
                        onClick={() => openEditDialog(index)}
                      >
                        <Pencil />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none hover:text-destructive"
                        aria-label={titleForLocale(
                          locale,
                          "删除问题",
                          "Remove prompt",
                        )}
                        title={titleForLocale(
                          locale,
                          "删除问题",
                          "Remove prompt",
                        )}
                        onClick={() =>
                          updatePrompts(prompts.filter((_, i) => i !== index))
                        }
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SettingsSectionCard>
      </TabsContent>

      {dialogOpen ? (
        <Dialog
          open={dialogOpen}
          onOpenChange={(open) => {
            if (!open) setDialogOpen(false);
          }}
        >
          <AppDialogContent
            className="sm:max-w-xl"
            title={titleForLocale(
              locale,
              editingIndex === null ? "添加测试问题" : "编辑测试问题",
              editingIndex === null ? "Add test prompt" : "Edit test prompt",
            )}
            footer={
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setDialogOpen(false)}
                >
                  {titleForLocale(locale, "取消", "Cancel")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!promptDraft.trim()}
                  onClick={savePrompt}
                >
                  {titleForLocale(locale, "保存", "Save")}
                </Button>
              </>
            }
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="model-test-prompt">
                  {titleForLocale(locale, "问题内容", "Prompt")}
                </FieldLabel>
                <Textarea
                  id="model-test-prompt"
                  className="min-h-28 resize-y"
                  value={promptDraft}
                  onChange={(event) => setPromptDraft(event.target.value)}
                  placeholder={titleForLocale(
                    locale,
                    "输入模型测试问题",
                    "Enter a model test prompt",
                  )}
                  autoFocus
                />
              </Field>
            </FieldGroup>
          </AppDialogContent>
        </Dialog>
      ) : null}

      <Dialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AppDialogContent
          className="max-w-lg"
          showCloseButton={false}
          title={titleForLocale(locale, "确认批量删除", "Delete prompts")}
          description={titleForLocale(
            locale,
            `将删除选中的 ${selectedCount} 个测试问题。`,
            `Delete ${selectedCount} selected prompts.`,
          )}
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setBulkDeleteOpen(false)}
              >
                {titleForLocale(locale, "取消", "Cancel")}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={selectedCount === 0}
                onClick={removeSelectedPrompts}
              >
                {titleForLocale(locale, "确认删除", "Delete")}
              </Button>
            </>
          }
        />
      </Dialog>
    </>
  );
}
