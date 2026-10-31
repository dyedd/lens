import { lazyComponent } from "@/lib/lazyComponent";
import { formatCredentialTitle } from "./channelModels";
import type {
  AggregatedModel,
  Locale,
  ModelStatusFilter,
} from "./channelTypes";
import type {
  useChannelPersistence,
  useChannelTransfer,
} from "./useChannelCommands";
import type { useChannelForm } from "./useChannelForm";
import type { useChannelModelPicker } from "./useChannelModelPicker";
import type { useChannelModelTest } from "./useChannelModelTest";
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
  save: ReturnType<typeof useChannelSave>;
  overviewModels: AggregatedModel[];
  editorMode: "channel" | "models";
  modelsStatusFilter: ModelStatusFilter;
  onCloseModels: () => void;
  remoteModelsOpen: boolean;
  onRemoteModelsOpenChange: (open: boolean) => void;
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
  save,
  overviewModels,
  editorMode,
  modelsStatusFilter,
  onCloseModels,
  remoteModelsOpen,
  onRemoteModelsOpenChange,
}: Props) {
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
          setIsDialogOpen={editor.setIsDialogOpen}
          setEditingSiteId={editor.setEditingSiteId}
          setForm={editor.setForm}
          submit={save.submit}
          addBaseUrl={editor.addBaseUrl}
          updateBaseUrl={editor.updateBaseUrl}
          removeBaseUrl={editor.removeBaseUrl}
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
          onUpdateContextWindow={editor.updateModelContextWindow}
          onDelete={editor.removeAggregateModel}
          onTest={modelTest.openAggregateModelTest}
          testing={modelTest.testingModel}
          onUpdateCredentialPattern={editor.setCredentialPattern}
          credentialOptions={editor.form.credentials.flatMap(
            (credential, index) =>
              credential.api_key.trim()
                ? [
                    {
                      id: credential.id,
                      label: formatCredentialTitle(credential, index, locale),
                      pattern: credential.model_pattern,
                    },
                  ]
                : [],
          )}
          onOpenRemote={() => onRemoteModelsOpenChange(true)}
          initialStatusFilter={modelsStatusFilter}
        />
      ) : null}
      {editor.isDialogOpen ? (
        <ChannelRemoteModelsDialog
          open={remoteModelsOpen}
          locale={locale}
          channelName={editor.form.name}
          loading={picker.fetching}
          onOpenChange={onRemoteModelsOpenChange}
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
          credentialOptions={modelTest.modelTestCredentialOptions}
          credentialValue={modelTest.modelTestDeleteKey ?? undefined}
          onCredentialChange={modelTest.changeModelTestCredential}
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
