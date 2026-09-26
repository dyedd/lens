import { CloudDownload, RefreshCcw, Settings2 } from "lucide-react";
import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import { Switch } from "@/components/ui/Switch";
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
  modelCounts: { enabled: number; total: number; pending: number };
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  closeEditor: () => void;
  onFetchModels: () => void;
  onManageModels: () => void;
};

function editorTitle(editingSiteId: string | null, locale: Locale) {
  if (editingSiteId) {
    return locale === "zh-CN" ? "编辑渠道" : "Edit channel";
  }
  return locale === "zh-CN" ? "新建渠道" : "Create channel";
}

/** Renders the model sync switch, filters, and model shortcuts. */
function ChannelModelSection({
  form,
  locale,
  modelCounts,
  setForm,
  onFetchModels,
  onManageModels,
}: Pick<
  ChannelEditorDialogProps,
  | "form"
  | "locale"
  | "modelCounts"
  | "setForm"
  | "onFetchModels"
  | "onManageModels"
>) {
  const isZh = locale === "zh-CN";
  return (
    <div className="min-w-0 space-y-1">
      <div className="text-xs font-normal text-muted-foreground">
        {isZh ? "模型" : "Models"}
      </div>
      <div className="space-y-2.5 rounded-md bg-muted/35 p-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs font-medium">
              {isZh ? "自动同步上游模型" : "Auto-sync upstream models"}
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {isZh
                ? "新模型自动加入并放入模型组，上游下线的模型标记为待确认"
                : "New models join and are placed into model groups; models gone upstream wait for review"}
            </div>
          </div>
          <Switch
            size="sm"
            checked={form.model_sync_enabled}
            onCheckedChange={(checked) =>
              setForm((current) => ({
                ...current,
                model_sync_enabled: checked,
              }))
            }
            aria-label={isZh ? "自动同步上游模型" : "Auto-sync upstream models"}
          />
        </div>
        {form.model_sync_enabled ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              value={form.model_sync_include}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  model_sync_include: event.target.value,
                }))
              }
              placeholder={
                isZh ? "只同步匹配（正则，可留空）" : "Include regex"
              }
              aria-label={isZh ? "只同步匹配的模型" : "Include regex"}
              className="h-8 font-mono text-xs"
            />
            <Input
              value={form.model_sync_exclude}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  model_sync_exclude: event.target.value,
                }))
              }
              placeholder={isZh ? "排除匹配（正则，可留空）" : "Exclude regex"}
              aria-label={isZh ? "排除匹配的模型" : "Exclude regex"}
              className="h-8 font-mono text-xs"
            />
          </div>
        ) : null}
        <div className="flex h-7 items-center justify-between gap-2">
          <span className="truncate text-xs text-muted-foreground tabular-nums">
            {isZh
              ? `活跃 ${modelCounts.enabled} / 总数 ${modelCounts.total}`
              : `${modelCounts.enabled} active / ${modelCounts.total} total`}
            {modelCounts.pending ? (
              <span className="text-destructive">
                {isZh
                  ? ` · ${modelCounts.pending} 待确认`
                  : ` · ${modelCounts.pending} to review`}
              </span>
            ) : null}
          </span>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={onFetchModels}
            >
              <CloudDownload />
              {isZh ? "获取模型" : "Fetch models"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={onManageModels}
            >
              <Settings2 />
              {isZh ? "管理" : "Manage"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
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
  onFetchModels,
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
                canSyncRates={Boolean(editingSiteId) && !hasUnsavedChanges}
                setForm={setForm}
                addBaseUrl={addBaseUrl}
                updateBaseUrl={updateBaseUrl}
                removeBaseUrl={removeBaseUrl}
              />
              <ChannelModelSection
                form={form}
                locale={locale}
                modelCounts={modelCounts}
                setForm={setForm}
                onFetchModels={onFetchModels}
                onManageModels={onManageModels}
              />
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
