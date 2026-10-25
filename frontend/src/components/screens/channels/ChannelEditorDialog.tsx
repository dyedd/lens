import { RefreshCcw } from "lucide-react";
import {
  type Dispatch,
  type FormEventHandler,
  type SetStateAction,
  useState,
} from "react";
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
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
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
  setIsDialogOpen,
  setEditingSiteId,
  setForm,
  submit,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
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
