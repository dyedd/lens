import { useEffect, useState } from "react";
import { lazyComponent } from "@/lib/lazyComponent";
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
import type { useModelGroupEnsure } from "./useModelGroupEnsure";

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
const ModelGroupEnsureDialog = lazyComponent(() =>
  import("./ModelGroupEnsureDialog").then(
    (module) => module.ModelGroupEnsureDialog,
  ),
);
const ModelTestDialog = lazyComponent(() =>
  import("./ModelTestDialog").then((module) => module.ModelTestDialog),
);
const ChannelModelSyncDialog = lazyComponent(() =>
  import("./ChannelModelSyncDialog").then(
    (module) => module.ChannelModelSyncDialog,
  ),
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
  modelGroups: ReturnType<typeof useModelGroupEnsure>;
  overviewModels: ReturnType<typeof useAggregatedModels>;
  editorMode: "channel" | "models";
  syncOnOpen: boolean;
  onSyncOnOpenHandled: () => void;
  onManageModels?: () => void;
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
  modelGroups,
  overviewModels,
  editorMode,
  syncOnOpen,
  onSyncOnOpenHandled,
  onManageModels,
}: Props) {
  const isDialogOpen = editor.isDialogOpen;
  const [remoteOpen, setRemoteOpen] = useState(false);

  useEffect(() => {
    if (!isDialogOpen || editorMode !== "models" || !syncOnOpen) {
      return;
    }
    setRemoteOpen(true);
    onSyncOnOpenHandled();
  }, [editorMode, isDialogOpen, onSyncOnOpenHandled, syncOnOpen]);

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
          savingChannel={modelGroups.isEnsuringModelGroups}
          modelCounts={{
            enabled: overviewModels.filter((item) => item.enabled).length,
            total: overviewModels.length,
          }}
          setIsDialogOpen={editor.setIsDialogOpen}
          setEditingSiteId={editor.setEditingSiteId}
          setForm={editor.setForm}
          submit={modelGroups.submit}
          addBaseUrl={editor.addBaseUrl}
          updateBaseUrl={editor.updateBaseUrl}
          removeBaseUrl={editor.removeBaseUrl}
          closeEditor={editor.closeEditor}
          onManageModels={onManageModels}
        />
      ) : null}
      {editor.isDialogOpen && editorMode === "models" ? (
        <>
          <ChannelModelsDialog
            open
            locale={locale}
            channelName={editor.form.name}
            models={overviewModels}
            saving={modelGroups.isEnsuringModelGroups}
            fetching={picker.fetching}
            onOpenChange={(open) => {
              if (!open) editor.closeEditor();
            }}
            onSave={modelGroups.submit}
            onToggleEnabled={editor.toggleAggregateEnabled}
            onUpdateProtocols={editor.updateModelProtocols}
            onDelete={editor.removeAggregateModel}
            onTest={modelTest.openAggregateModelTest}
            testing={modelTest.testingModel}
            onAddBinding={editor.addBinding}
            onOpenRemote={() => setRemoteOpen(true)}
          />
          <ChannelRemoteModelsDialog
            open={remoteOpen}
            locale={locale}
            channelName={editor.form.name}
            loading={picker.fetching}
            onOpenChange={setRemoteOpen}
            onLoad={() => picker.discoverRemoteCatalog(0)}
            onImport={(items) => picker.importRemoteModels(items)}
          />
        </>
      ) : null}
      {modelGroups.modelGroupEnsureOpen ? (
        <ModelGroupEnsureDialog
          open
          locale={locale}
          result={modelGroups.result}
          modelGroups={modelGroups.groups}
          selectedItemKeys={modelGroups.selectedKeys}
          isConfirming={modelGroups.isEnsuringModelGroups}
          onOpenChange={modelGroups.setModelGroupEnsureOpen}
          onToggleItem={modelGroups.toggleItem}
          onTargetGroupChange={(item, name) =>
            void modelGroups.updateTarget(item, name)
          }
          onConfirm={(overrides) => void modelGroups.confirm(overrides)}
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
      {transfer.channelSyncOpen ? (
        <ChannelModelSyncDialog
          open
          onOpenChange={transfer.setChannelSyncOpen}
          locale={locale}
          result={transfer.channelSyncResult}
          syncing={transfer.channelSyncing}
          onConfirm={() => void transfer.confirmChannelModelSync()}
        />
      ) : null}
      {batchTest.batchModelTestOpen ? (
        <BatchModelTestDialog
          open
          locale={locale}
          modelTestPrompts={modelTest.modelTestPrompts}
          batchTestPromptMode={batchTest.batchTestPromptMode}
          batchTestPrompt={batchTest.batchTestPrompt}
          batchTestConcurrency={batchTest.batchTestConcurrency}
          batchTestOptions={batchTest.batchTestOptions}
          batchTestRows={batchTest.batchTestRows}
          isBatchModelTestRunning={batchTest.isBatchModelTestRunning}
          onOpenChange={batchTest.changeBatchModelTestOpen}
          onPromptModeChange={batchTest.changeBatchTestPromptMode}
          onPromptChange={batchTest.changeBatchTestPrompt}
          onConcurrencyChange={batchTest.setBatchTestConcurrency}
          onProtocolChange={batchTest.changeBatchTestProtocol}
          onRun={() => void batchTest.runBatchModelTests()}
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
          target={modelTest.modelTestDialogTarget}
          locale={locale}
          modelTestPrompts={modelTest.modelTestPrompts}
          modelTestPromptMode={modelTest.modelTestPromptMode}
          modelTestPrompt={modelTest.modelTestPrompt}
          modelTestProtocol={modelTest.modelTestProtocol}
          modelTestResult={modelTest.modelTestResult}
          testingModel={modelTest.testingModel}
          onClose={modelTest.closeModelTest}
          onPromptModeChange={modelTest.changeModelTestPromptMode}
          onPromptChange={modelTest.changeModelTestPrompt}
          onProtocolChange={modelTest.setModelTestProtocol}
          onRun={() => void modelTest.runModelTest()}
        />
      ) : null}
    </>
  );
}
