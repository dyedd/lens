"use client";

import dynamic from "next/dynamic";
import type { Dispatch, SetStateAction } from "react";
import type { useAggregatedModels } from "./useAggregatedModels";
import type { useBatchModelTest } from "./useBatchModelTest";
import type { useChannelForm } from "./useChannelForm";
import type { useChannelModelPicker } from "./useChannelModelPicker";
import type { useChannelModelTest } from "./useChannelModelTest";
import type { useChannelPersistence } from "./useChannelPersistence";
import type { useChannelTransfer } from "./useChannelTransfer";
import type { useModelGroupEnsure } from "./useModelGroupEnsure";
import type { Locale } from "./channelShared";

const ChannelEditorDialog = dynamic(() =>
  import("./ChannelDialogs").then((module) => module.ChannelEditorDialog),
);
const DeleteChannelDialog = dynamic(() =>
  import("./DeleteChannelDialog").then((module) => module.DeleteChannelDialog),
);
const AdvancedProtocolConfigDialog = dynamic(() =>
  import("./AdvancedProtocolConfigDialog").then(
    (module) => module.AdvancedProtocolConfigDialog,
  ),
);
const BatchImportDialog = dynamic(() =>
  import("./BatchImportDialog").then((module) => module.BatchImportDialog),
);
const BatchModelTestDialog = dynamic(() =>
  import("./BatchModelTestDialog").then(
    (module) => module.BatchModelTestDialog,
  ),
);
const ModelGroupEnsureDialog = dynamic(() =>
  import("./ModelGroupEnsureDialog").then(
    (module) => module.ModelGroupEnsureDialog,
  ),
);
const ModelTestDialog = dynamic(() =>
  import("./ModelTestDialog").then((module) => module.ModelTestDialog),
);
const ModelPickerDialog = dynamic(() =>
  import("./ModelPickerDialog").then((module) => module.ModelPickerDialog),
);
const ChannelModelSyncDialog = dynamic(() =>
  import("./ChannelModelSyncDialog").then(
    (module) => module.ChannelModelSyncDialog,
  ),
);

type Props = {
  locale: Locale;
  editor: ReturnType<typeof useChannelForm>;
  persistence: ReturnType<typeof useChannelPersistence>;
  transfer: ReturnType<typeof useChannelTransfer>;
  picker: ReturnType<typeof useChannelModelPicker>;
  modelTest: ReturnType<typeof useChannelModelTest>;
  batchTest: ReturnType<typeof useBatchModelTest>;
  modelGroups: ReturnType<typeof useModelGroupEnsure>;
  overviewModels: ReturnType<typeof useAggregatedModels>;
  advancedConfigIndex: number | null;
  setAdvancedConfigIndex: Dispatch<SetStateAction<number | null>>;
};

/** Renders channel dialogs while keeping the screen component declarative. */
export function ChannelsDialogs({
  locale,
  editor,
  persistence,
  transfer,
  picker,
  modelTest,
  batchTest,
  modelGroups,
  overviewModels,
  advancedConfigIndex,
  setAdvancedConfigIndex,
}: Props) {
  return (
    <>
      {editor.isDialogOpen ? (
        <ChannelEditorDialog
          isDialogOpen={editor.isDialogOpen}
          hasUnsavedChanges={editor.hasUnsavedChanges}
          editingSiteId={editor.editingSiteId}
          locale={locale}
          form={editor.form}
          fetchingProtocolConfigIndex={picker.fetchingProtocolConfigIndex}
          duplicatedProtocolConfigKeys={editor.duplicatedProtocolConfigKeys}
          batchTestOptions={batchTest.batchTestOptions}
          isBatchModelTestRunning={batchTest.isBatchModelTestRunning}
          testingModel={modelTest.testingModel}
          isEnsuringModelGroups={modelGroups.isEnsuringModelGroups}
          overviewModels={overviewModels}
          modelTestOptionByKey={modelTest.modelTestOptionByKey}
          setIsDialogOpen={editor.setIsDialogOpen}
          setEditingSiteId={editor.setEditingSiteId}
          setForm={editor.setForm}
          setAdvancedProtocolConfigIndex={setAdvancedConfigIndex}
          submit={persistence.submit}
          addBaseUrl={editor.addBaseUrl}
          updateBaseUrl={editor.updateBaseUrl}
          removeBaseUrl={editor.removeBaseUrl}
          updateCredential={editor.updateCredential}
          removeCredential={editor.removeCredential}
          addProtocolConfig={editor.addProtocolConfig}
          updateProtocolConfig={editor.updateProtocolConfig}
          addManualProtocolConfigModel={picker.addManualProtocolConfigModel}
          fetchProtocolModels={picker.fetchProtocolModels}
          openModelGroupEnsureDialog={modelGroups.openModelGroupEnsureDialog}
          openBatchModelTestDialog={batchTest.openBatchModelTestDialog}
          updateModelProtocols={editor.updateModelProtocols}
          openAggregateModelTest={modelTest.openAggregateModelTest}
          removeAggregateModel={editor.removeAggregateModel}
          clearAggregateModels={editor.clearAggregateModels}
          closeEditor={editor.closeEditor}
        />
      ) : null}
      {modelGroups.modelGroupEnsureOpen ? (
        <ModelGroupEnsureDialog
          open
          locale={locale}
          result={modelGroups.result}
          modelGroups={modelGroups.groups}
          selectedItemKeys={modelGroups.selectedKeys}
          isProtocolExtensionAllowed={modelGroups.allowProtocolExtension}
          isConfirming={modelGroups.isEnsuringModelGroups}
          onOpenChange={modelGroups.setModelGroupEnsureOpen}
          onToggleItem={modelGroups.toggleItem}
          onAllowProtocolExtensionChange={(allowed) =>
            void modelGroups.updateProtocolExtension(allowed)
          }
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
          onOpenChange={batchTest.setBatchModelTestOpen}
          onPromptModeChange={batchTest.changeBatchTestPromptMode}
          onPromptChange={batchTest.changeBatchTestPrompt}
          onConcurrencyChange={batchTest.setBatchTestConcurrency}
          onProtocolChange={batchTest.changeBatchTestProtocol}
          onRun={() => void batchTest.runBatchModelTests()}
        />
      ) : null}
      {advancedConfigIndex !== null ? (
        <AdvancedProtocolConfigDialog
          open
          protocolConfig={editor.form.protocolConfigs[advancedConfigIndex]}
          protocolConfigIndex={advancedConfigIndex}
          locale={locale}
          onOpenChange={(open) => {
            if (!open) setAdvancedConfigIndex(null);
          }}
          onUpdateProtocolConfig={editor.updateProtocolConfig}
          onUpdateProtocolConfigHeader={editor.updateProtocolConfigHeader}
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
      {modelTest.modelTestTarget ? (
        <ModelTestDialog
          target={modelTest.modelTestTarget}
          form={editor.form}
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
      {picker.modelPickerProtocolConfigIndex !== null ? (
        <ModelPickerDialog
          open
          availableModels={picker.availableModels}
          pickerSelectedModelKeys={picker.pickerSelectedModelKeys}
          pickerImportProtocols={picker.pickerImportProtocols}
          pickerModelProtocols={picker.pickerModelProtocols}
          locale={locale}
          onOpenChange={(open) => {
            if (!open) picker.closeModelPicker();
          }}
          onToggleModel={(key) =>
            picker.setPickerSelectedModelKeys((current) =>
              current.includes(key)
                ? current.filter((item) => item !== key)
                : [...current, key],
            )
          }
          onImportProtocolsChange={picker.setPickerImportProtocols}
          onFilteredModelProtocolsChange={(keys, protocols) =>
            picker.setPickerModelProtocols((current) => {
              const next = { ...current };
              for (const key of keys) {
                if (protocols.length) next[key] = protocols;
                else delete next[key];
              }
              return next;
            })
          }
          onConfirm={() =>
            picker.applyModelSelection(picker.pickerSelectedModelKeys)
          }
          onConfirmAll={picker.applyModelSelection}
          onCancel={picker.closeModelPicker}
        />
      ) : null}
    </>
  );
}
