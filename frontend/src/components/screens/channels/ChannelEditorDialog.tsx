import { RefreshCcw } from "lucide-react";
import {
  type Dispatch,
  type FormEventHandler,
  type SetStateAction,
  useState,
} from "react";
import type { BatchModelTestOption } from "@/components/model-test/batchModelTestSession";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Separator } from "@/components/ui/Separator";
import type { ProtocolKind } from "@/lib/api/protocols";
import { ChannelBasicInfoSection } from "./ChannelBasicInfoSection";
import { ChannelModelOverviewSection } from "./ChannelModelOverviewSection";
import { ChannelProtocolSection } from "./ChannelProtocolSection";
import type {
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
  FormState,
  Locale,
  TestableModelOption,
} from "./channelTypes";
import type { AggregatedModel } from "./useAggregatedModels";

type ChannelEditorDialogProps = {
  isDialogOpen: boolean;
  hasUnsavedChanges: boolean;
  editingSiteId: string | null;
  locale: Locale;
  availableTags: string[];
  form: FormState;
  fetchingProtocolConfigIndex: number | null;
  duplicatedProtocolConfigKeys: Set<string>;
  batchTestOptions: BatchModelTestOption[];
  isBatchModelTestRunning: boolean;
  testingModel: boolean;
  savingChannel: boolean;
  overviewModels: AggregatedModel[];
  modelTestOptionByKey: Map<string, TestableModelOption>;
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  setAdvancedProtocolConfigIndex: Dispatch<SetStateAction<number | null>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (
    credentialId: string,
    patch: Partial<FormCredential>,
  ) => void;
  removeCredential: (index: number) => void;
  addProtocolConfig: () => void;
  updateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  addManualProtocolConfigModel: (protocolConfigIndex: number) => void;
  fetchProtocolModels: (protocolConfigIndex: number) => void;
  openBatchModelTestDialog: () => void;
  updateModelProtocols: (
    modelKey: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  updateModelSource: (
    modelKey: string,
    source: AggregatedModel["source"],
  ) => void;
  updateAllModelSources: (source: AggregatedModel["source"]) => void;
  openAggregateModelTest: (modelKey: string) => void;
  removeAggregateModel: (modelKey: string) => void;
  clearModels: () => void;
  closeEditor: () => void;
};

/** Renders the channel editor and coordinates its form actions. */
export function ChannelEditorDialog({
  isDialogOpen,
  hasUnsavedChanges,
  editingSiteId,
  locale,
  availableTags,
  form,
  fetchingProtocolConfigIndex,
  duplicatedProtocolConfigKeys,
  batchTestOptions,
  isBatchModelTestRunning,
  testingModel,
  savingChannel,
  overviewModels,
  modelTestOptionByKey,
  setIsDialogOpen,
  setEditingSiteId,
  setForm,
  setAdvancedProtocolConfigIndex,
  submit,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  updateCredential,
  removeCredential,
  addProtocolConfig,
  updateProtocolConfig,
  addManualProtocolConfigModel,
  fetchProtocolModels,
  openBatchModelTestDialog,
  updateModelProtocols,
  updateModelSource,
  updateAllModelSources,
  openAggregateModelTest,
  removeAggregateModel,
  clearModels,
  closeEditor,
}: ChannelEditorDialogProps) {
  const [isRateSyncing, setIsRateSyncing] = useState(false);

  return (
    <Dialog
      open={isDialogOpen}
      onOpenChange={(open) => {
        if (!open && (savingChannel || isRateSyncing)) return;
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
      }}
    >
      <AppDialogContent
        className="max-w-4xl"
        title={
          editingSiteId
            ? locale === "zh-CN"
              ? "编辑渠道"
              : "Edit channel"
            : locale === "zh-CN"
              ? "新建渠道"
              : "Create channel"
        }
      >
        <form
          className="grid gap-5"
          onSubmit={submit}
          onKeyDown={(event) => {
            // Toolbar search is live-filter; Enter must not save/close the channel dialog.
            if (
              event.key === "Enter" &&
              !event.nativeEvent.isComposing &&
              event.target instanceof HTMLElement &&
              event.target.closest("[data-toolbar-search]")
            ) {
              event.preventDefault();
            }
          }}
        >
          <fieldset
            className="grid min-w-0 gap-5 border-0 p-0"
            disabled={isRateSyncing}
          >
            <div className="grid gap-4">
              <ChannelBasicInfoSection
                form={form}
                locale={locale}
                availableTags={availableTags}
                siteId={editingSiteId}
                canSyncRates={Boolean(editingSiteId) && !hasUnsavedChanges}
                onRateSyncingChange={setIsRateSyncing}
                setForm={setForm}
                addBaseUrl={addBaseUrl}
                updateBaseUrl={updateBaseUrl}
                removeBaseUrl={removeBaseUrl}
                updateCredential={updateCredential}
                removeCredential={removeCredential}
              />
              <Separator />
              <section className="grid gap-4">
                <ChannelProtocolSection
                  form={form}
                  locale={locale}
                  fetchingProtocolConfigIndex={fetchingProtocolConfigIndex}
                  duplicatedProtocolConfigKeys={duplicatedProtocolConfigKeys}
                  setForm={setForm}
                  setAdvancedProtocolConfigIndex={
                    setAdvancedProtocolConfigIndex
                  }
                  addProtocolConfig={addProtocolConfig}
                  updateProtocolConfig={updateProtocolConfig}
                  addManualProtocolConfigModel={addManualProtocolConfigModel}
                  fetchProtocolModels={fetchProtocolModels}
                />
                <ChannelModelOverviewSection
                  locale={locale}
                  overviewModels={overviewModels}
                  modelTestOptionByKey={modelTestOptionByKey}
                  batchTestOptions={batchTestOptions}
                  isBatchModelTestRunning={isBatchModelTestRunning}
                  testingModel={testingModel}
                  onOpenBatchTest={openBatchModelTestDialog}
                  onUpdateModelProtocols={updateModelProtocols}
                  onUpdateModelSource={updateModelSource}
                  onUpdateAllModelSources={updateAllModelSources}
                  onOpenModelTest={openAggregateModelTest}
                  onRemoveModel={removeAggregateModel}
                  onClearModels={clearModels}
                />
              </section>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={closeEditor}
                disabled={savingChannel}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button type="submit" disabled={savingChannel}>
                {savingChannel ? (
                  <RefreshCcw
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                ) : null}
                {savingChannel
                  ? locale === "zh-CN"
                    ? "正在保存..."
                    : "Saving..."
                  : editingSiteId
                    ? locale === "zh-CN"
                      ? "保存渠道"
                      : "Save channel"
                    : locale === "zh-CN"
                      ? "创建渠道"
                      : "Create channel"}
              </Button>
            </div>
          </fieldset>
        </form>
      </AppDialogContent>
    </Dialog>
  );
}
