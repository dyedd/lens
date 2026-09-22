import { RefreshCcw } from "lucide-react";
import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import { Button } from "@/components/ui/Button";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import { ChannelAdvancedSection } from "./ChannelAdvancedSection";
import { ChannelBasicInfoSection } from "./ChannelBasicInfoSection";
import type { FormBaseUrl, FormState, Locale } from "./channelTypes";

type ChannelEditorDialogProps = {
  isDialogOpen: boolean;
  hasUnsavedChanges: boolean;
  editingSiteId: string | null;
  locale: Locale;
  availableTags: string[];
  form: FormState;
  savingChannel: boolean;
  modelCounts: { enabled: number; total: number };
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  closeEditor: () => void;
  onManageModels?: () => void;
};

function editorTitle(editingSiteId: string | null, locale: Locale) {
  if (editingSiteId) {
    return locale === "zh-CN" ? "编辑渠道" : "Edit channel";
  }
  return locale === "zh-CN" ? "新建渠道" : "Create channel";
}

/** Renders the channel editor and coordinates its form actions. */
export function ChannelEditorDialog({
  isDialogOpen,
  hasUnsavedChanges,
  editingSiteId,
  locale,
  availableTags,
  form,
  savingChannel,
  modelCounts,
  setIsDialogOpen,
  setEditingSiteId,
  setForm,
  submit,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  closeEditor,
  onManageModels,
}: ChannelEditorDialogProps) {
  const title = editorTitle(editingSiteId, locale);

  function handleOpenChange(open: boolean) {
    if (!open && savingChannel) return;
    if (!open && hasUnsavedChanges) {
      const confirmed = window.confirm(
        locale === "zh-CN"
          ? "当前有未保存修改，确定关闭吗？"
          : "You have unsaved changes. Close anyway?",
      );
      if (!confirmed) return;
    }
    setIsDialogOpen(open);
    if (!open) setEditingSiteId(null);
  }

  const submitLabel = savingChannel
    ? locale === "zh-CN"
      ? "正在保存..."
      : "Saving..."
    : editingSiteId
      ? locale === "zh-CN"
        ? "保存"
        : "Save"
      : locale === "zh-CN"
        ? "创建"
        : "Create";

  return (
    <Sheet open={isDialogOpen} onOpenChange={handleOpenChange}>
      <SheetContent className="flex flex-col gap-0 sm:max-w-[460px]">
        <SheetHeader className="px-4 pb-4">
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          <fieldset className="flex min-h-0 flex-1 flex-col border-0 p-0">
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-2">
              <ChannelBasicInfoSection
                form={form}
                locale={locale}
                availableTags={availableTags}
                siteId={editingSiteId}
                setForm={setForm}
                addBaseUrl={addBaseUrl}
                updateBaseUrl={updateBaseUrl}
                removeBaseUrl={removeBaseUrl}
              />
              {editingSiteId && onManageModels ? (
                <div className="min-w-0 space-y-1">
                  <div className="text-xs font-normal text-muted-foreground">
                    {locale === "zh-CN" ? "模型" : "Models"}
                  </div>
                  <div className="flex h-8 items-center justify-between rounded-md bg-muted/35 px-2.5 text-xs">
                    <span className="text-muted-foreground">
                      {locale === "zh-CN"
                        ? `活跃 ${modelCounts.enabled} / 总数 ${modelCounts.total}`
                        : `${modelCounts.enabled} active / ${modelCounts.total} total`}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      onClick={onManageModels}
                    >
                      {locale === "zh-CN" ? "管理模型" : "Manage models"}
                    </Button>
                  </div>
                </div>
              ) : null}
              <ChannelAdvancedSection
                form={form}
                locale={locale}
                setForm={setForm}
              />
            </div>
            <SheetFooter className="flex flex-row justify-end gap-2 px-4 py-3">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={closeEditor}
                disabled={savingChannel}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button type="submit" size="sm" disabled={savingChannel}>
                {savingChannel ? (
                  <RefreshCcw
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                ) : null}
                {submitLabel}
              </Button>
            </SheetFooter>
          </fieldset>
        </form>
      </SheetContent>
    </Sheet>
  );
}
