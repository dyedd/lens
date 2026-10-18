import { CloudDownload, RefreshCcw, Settings2 } from "lucide-react";
import {
  type Dispatch,
  type FormEventHandler,
  type SetStateAction,
  useState,
} from "react";
import { RegexRulePicker } from "@/components/ruleEditors/RegexRulePicker";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
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
  modelCounts: { enabled: number; total: number; pending: number };
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  onFetchModels: () => void;
  onManageModels: () => void;
};

function editorTitle(editingSiteId: string | null, locale: Locale) {
  if (editingSiteId) {
    return locale === "zh-CN" ? "编辑渠道" : "Edit channel";
  }
  return locale === "zh-CN" ? "新建渠道" : "Create channel";
}

/** Renders model shortcuts and the current model count. */
function ChannelModelSection({
  locale,
  form,
  setForm,
  modelCounts,
  onFetchModels,
  onManageModels,
}: Pick<
  ChannelEditorDialogProps,
  | "locale"
  | "form"
  | "setForm"
  | "modelCounts"
  | "onFetchModels"
  | "onManageModels"
>) {
  const isZh = locale === "zh-CN";
  return (
    <div className="min-w-0 space-y-2.5 rounded-md bg-muted/35 p-2.5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium">
            {isZh ? "模型同步" : "Model sync"}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {isZh
              ? "输入或获取的模型都会按上游列表持续同步；匹配自动接入规则的新模型会在同步时自动加入。"
              : "Entered and fetched models stay synchronized with the upstream catalog; new models matching the onboarding rules join on each sync."}
          </div>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-start gap-2">
          <span className="w-14 shrink-0 pt-1 text-xs leading-6 text-muted-foreground">
            {isZh ? "自动接入" : "Auto-onboard"}
          </span>
          <RegexRulePicker
            locale={locale}
            label={isZh ? "自动接入规则" : "Onboarding rules"}
            value={form.model_sync_include_rule_ids}
            onChange={(ruleIds) =>
              setForm((current) => ({
                ...current,
                model_sync_include_rule_ids: ruleIds,
              }))
            }
          />
        </div>
        <div className="flex items-start gap-2">
          <span className="w-14 shrink-0 pt-1 text-xs leading-6 text-muted-foreground">
            {isZh ? "排除" : "Exclude"}
          </span>
          <RegexRulePicker
            locale={locale}
            label={isZh ? "排除规则" : "Exclusion rules"}
            value={form.model_sync_exclude_rule_ids}
            onChange={(ruleIds) =>
              setForm((current) => ({
                ...current,
                model_sync_exclude_rule_ids: ruleIds,
              }))
            }
          />
        </div>
      </div>
      <div className="flex h-7 items-center justify-between gap-2">
        <span className="truncate text-xs text-muted-foreground tabular-nums">
          {isZh
            ? `${modelCounts.enabled} / ${modelCounts.total} 已启用`
            : `${modelCounts.enabled} / ${modelCounts.total} active`}
          {modelCounts.pending ? (
            <span className="text-destructive">
              {isZh
                ? ` · ${modelCounts.pending} 待处理`
                : ` · ${modelCounts.pending} needs review`}
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
            {isZh ? "获取模型列表" : "Fetch model list"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={onManageModels}
          >
            <Settings2 />
            {isZh ? "管理模型" : "Manage models"}
          </Button>
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
  onFetchModels,
  onManageModels,
}: ChannelEditorDialogProps) {
  const title = editorTitle(editingSiteId, locale);
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);

  function requestClose() {
    if (savingChannel) return;
    if (hasUnsavedChanges) {
      setDiscardConfirmOpen(true);
      return;
    }
    setIsDialogOpen(false);
    setEditingSiteId(null);
  }

  function handleOpenChange(open: boolean) {
    if (!open) {
      requestClose();
    } else {
      setIsDialogOpen(true);
    }
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
                locale={locale}
                form={form}
                setForm={setForm}
                modelCounts={modelCounts}
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
                onClick={requestClose}
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
      <Dialog open={discardConfirmOpen} onOpenChange={setDiscardConfirmOpen}>
        <AppDialogContent
          title={
            locale === "zh-CN"
              ? "放弃未保存的修改？"
              : "Discard unsaved changes?"
          }
          description={
            locale === "zh-CN"
              ? "未保存的修改将丢失。"
              : "Your unsaved changes will be lost."
          }
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setDiscardConfirmOpen(false)}
              >
                {locale === "zh-CN" ? "继续编辑" : "Keep editing"}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => {
                  setDiscardConfirmOpen(false);
                  setIsDialogOpen(false);
                  setEditingSiteId(null);
                }}
              >
                {locale === "zh-CN" ? "放弃修改" : "Discard changes"}
              </Button>
            </>
          }
        />
      </Dialog>
    </Sheet>
  );
}
