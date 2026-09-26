import { useEffect, useState } from "react";
import { lazyComponent } from "@/lib/lazyComponent";
import type { ModelStatusFilter } from "./ChannelModelsDialog";
import type { Locale } from "./channelTypes";
import type {
  useChannelPersistence,
  useChannelTransfer,
} from "./useChannelCommands";
import type { useChannelForm } from "./useChannelForm";
import type { useChannelModelPicker } from "./useChannelModelPicker";
import type {
  useBatchModelTest,
  useChannelModelTest,
} from "./useChannelModelTest";
import type { useAggregatedModels } from "./useChannelQueries";
import type { useChannelSave } from "./useChannelSave";

const ChannelEditorDialog = lazyComponent(() =>
  import("./ChannelEditorDialog").then((module) => module.ChannelEditorDialog),
);
const DeleteChannelDialog = lazyComponent(() =>
  import("./DeleteChannelDialog").then((module) => module.DeleteChannelDialog),
);
const BatchImportDialog = lazyComponent(() =>
  import("./BatchImportDialog").then((module) => module.BatchImportDialog),
);
const BatchModelTestDialog = lazyComponent(() =>
  import("./BatchModelTestDialog").then(
    (module) => module.BatchModelTestDialog,
  ),
);
const ModelTestDialog = lazyComponent(() =>
  import("./ModelTestDialog").then((module) => module.ModelTestDialog),
);
const ChannelModelsDialog = lazyComponent(() =>
  import("./ChannelModelsDialog").then((module) => module.ChannelModelsDialog),
);
const ChannelRemoteModelsDialog = lazyComponent(() =>
  import("./ChannelRemoteModelsDialog").then(
    (module) => module.ChannelRemoteModelsDialog,
  ),
);

type Props = {
  locale: Locale;
  availableTags: string[];
  editor: ReturnType<typeof useChannelForm>;
  persistence: ReturnType<typeof useChannelPersistence>;
  transfer: ReturnType<typeof useChannelTransfer>;
  picker: ReturnType<typeof useChannelModelPicker>;
  modelTest: ReturnType<typeof useChannelModelTest>;
  batchTest: ReturnType<typeof useBatchModelTest>;
  save: ReturnType<typeof useChannelSave>;
  overviewModels: ReturnType<typeof useAggregatedModels>;
  editorMode: "channel" | "models";
  isModelsNested: boolean;
  modelsStatusFilter: ModelStatusFilter;
  fetchOnOpen: boolean;
  onFetchOnOpenHandled: () => void;
  onManageModels: () => void;
  onCloseModels: () => void;
};

/** Renders channel dialogs while keeping the screen component declarative. */
export function ChannelsDialogs({
  locale,
  availableTags,
  editor,
  persistence,
  transfer,
  picker,
  modelTest,
  batchTest,
  save,
  overviewModels,
  editorMode,
  isModelsNested,
  modelsStatusFilter,
  fetchOnOpen,
  onFetchOnOpenHandled,
  onManageModels,
  onCloseModels,
}: Props) {
  const isDialogOpen = editor.isDialogOpen;
  const [remoteOpen, setRemoteOpen] = useState(false);

  useEffect(() => {
    if (!isDialogOpen || !fetchOnOpen) return;
    setRemoteOpen(true);
    onFetchOnOpenHandled();
  }, [fetchOnOpen, isDialogOpen, onFetchOnOpenHandled]);

  return (
    <>
      {editor.isDialogOpen && editorMode === "channel" ? (
        <ChannelEditorDialog
          isDialogOpen={editor.isDialogOpen}
          hasUnsavedChanges={editor.hasUnsavedChanges}
          editingSiteId={editor.editingSiteId}
          locale={locale}
          availableTags={availableTags}
          form={editor.form}
          savingChannel={save.isSaving}
          modelCounts={{
            enabled: overviewModels.filter((item) => item.enabled).length,
            total: overviewModels.length,
            pending: overviewModels.filter((item) => item.upstreamMissing)
              .length,
          }}
          setIsDialogOpen={editor.setIsDialogOpen}
          setEditingSiteId={editor.setEditingSiteId}
          setForm={editor.setForm}
          submit={save.submit}
          addBaseUrl={editor.addBaseUrl}
          updateBaseUrl={editor.updateBaseUrl}
          removeBaseUrl={editor.removeBaseUrl}
          closeEditor={editor.closeEditor}
          onFetchModels={() => setRemoteOpen(true)}
          onManageModels={onManageModels}
        />
      ) : null}
      {editor.isDialogOpen && editorMode === "models" ? (
        <ChannelModelsDialog
          open
          locale={locale}
          channelName={editor.form.name}
          models={overviewModels}
          saving={save.isSaving}
          fetching={picker.fetching}
          onOpenChange={(open) => {
            if (!open) onCloseModels();
          }}
          onSave={save.submit}
          onToggleEnabled={editor.toggleAggregateEnabled}
          onUpdateProtocols={editor.updateModelProtocols}
          onDelete={editor.removeAggregateModel}
          onTest={modelTest.openAggregateModelTest}
          testing={modelTest.testingModel}
          onAddBinding={editor.addBinding}
          onOpenRemote={() => setRemoteOpen(true)}
          onKeep={editor.keepAggregateModels}
          syncEnabled={editor.form.model_sync_enabled}
          syncing={save.syncingSiteId !== null}
          onSyncNow={() => void save.syncEditorModels()}
          initialStatusFilter={modelsStatusFilter}
          isNested={isModelsNested}
        />
      ) : null}
      {editor.isDialogOpen ? (
        <ChannelRemoteModelsDialog
          open={remoteOpen}
          locale={locale}
          channelName={editor.form.name}
          loading={picker.fetching}
          onOpenChange={setRemoteOpen}
          onLoad={picker.discoverRemoteCatalog}
          onImport={picker.importRemoteModels}
        />
      ) : null}
      {transfer.batchImportOpen ? (
        <BatchImportDialog
          open
          onOpenChange={transfer.setBatchImportOpen}
          locale={locale}
          importText={transfer.batchImportText}
          importError={transfer.batchImportError}
          importResult={transfer.batchImportResult}
          importing={transfer.batchImporting}
          onTextChange={transfer.updateBatchImportText}
          onFileChange={(event) => void transfer.handleBatchImportFile(event)}
          onDownloadTemplate={transfer.downloadBatchImportTemplate}
          onImport={() => void transfer.importBatchSites()}
        />
      ) : null}
      {batchTest.batchModelTestOpen ? (
        <BatchModelTestDialog
          locale={locale}
          targetName={editor.form.name}
          rows={batchTest.batchTestRows}
          testing={batchTest.isBatchModelTestRunning}
          prompts={batchTest.prompts}
          promptMode={batchTest.batchTestPromptMode}
          prompt={batchTest.batchTestPrompt}
          onPromptModeChange={batchTest.changeBatchTestPromptMode}
          onPromptChange={batchTest.changeBatchTestPrompt}
          onProtocolChange={batchTest.changeBatchTestProtocol}
          onRun={() => void batchTest.runBatchModelTests()}
          onClose={() => batchTest.changeBatchModelTestOpen(false)}
        />
      ) : null}
      {persistence.deleteTarget ? (
        <DeleteChannelDialog
          deleteTarget={persistence.deleteTarget}
          locale={locale}
          busyId={persistence.busyId}
          setDeleteTarget={persistence.setDeleteTarget}
          removeSite={persistence.removeSite}
        />
      ) : null}
      {modelTest.modelTestDialogTarget ? (
        <ModelTestDialog
          locale={locale}
          prompts={modelTest.modelTestPrompts}
          promptMode={modelTest.modelTestPromptMode}
          prompt={modelTest.modelTestPrompt}
          onPromptModeChange={modelTest.changeModelTestPromptMode}
          onPromptChange={modelTest.changeModelTestPrompt}
          onRun={() => void modelTest.runModelTest()}
          items={[
            {
              target: modelTest.modelTestDialogTarget,
              result: modelTest.modelTestResult,
              protocol: modelTest.modelTestProtocol,
              protocols: modelTest.modelTestProtocols,
              onProtocolChange: modelTest.changeModelTestProtocol,
              onDelete: modelTest.modelTestDeleteKey
                ? () => {
                    if (modelTest.modelTestDeleteKey)
                      editor.removeAggregateModel(modelTest.modelTestDeleteKey);
                  }
                : undefined,
            },
          ]}
          testing={modelTest.testingModel}
          onClose={modelTest.closeModelTest}
        />
      ) : null}
    </>
  );
}
