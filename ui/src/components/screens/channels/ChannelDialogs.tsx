"use client";

import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Separator } from "@/components/ui/Separator";
import { ChannelBasicInfoSection } from "./ChannelBasicInfoSection";
import { ChannelModelOverviewSection } from "./ChannelModelOverviewSection";
import { ChannelProtocolSection } from "./ChannelProtocolSection";
import type { ChannelEditorDialogProps } from "./channelEditorTypes";

/** Renders the channel editor and coordinates its form actions. */
export function ChannelEditorDialog({
  isDialogOpen,
  hasUnsavedChanges,
  editingSiteId,
  locale,
  form,
  fetchingProtocolConfigIndex,
  duplicatedProtocolConfigKeys,
  batchTestOptions,
  isBatchModelTestRunning,
  testingModel,
  isEnsuringModelGroups,
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
  openModelGroupEnsureDialog,
  openBatchModelTestDialog,
  updateModelProtocols,
  openAggregateModelTest,
  removeAggregateModel,
  clearAggregateModels,
  closeEditor,
}: ChannelEditorDialogProps) {
  return (
    <Dialog
      open={isDialogOpen}
      onOpenChange={(open) => {
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
        <form className="grid gap-5" onSubmit={submit}>
          <div className="grid gap-4">
            <ChannelBasicInfoSection
              form={form}
              locale={locale}
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
                setAdvancedProtocolConfigIndex={setAdvancedProtocolConfigIndex}
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
                isEnsuringModelGroups={isEnsuringModelGroups}
                onEnsureModelGroups={openModelGroupEnsureDialog}
                onOpenBatchTest={openBatchModelTestDialog}
                onUpdateModelProtocols={updateModelProtocols}
                onOpenModelTest={openAggregateModelTest}
                onRemoveModel={removeAggregateModel}
                onClearModels={clearAggregateModels}
              />
            </section>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <Button type="button" variant="outline" onClick={closeEditor}>
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button type="submit">
              {editingSiteId
                ? locale === "zh-CN"
                  ? "保存渠道"
                  : "Save channel"
                : locale === "zh-CN"
                  ? "创建渠道"
                  : "Create channel"}
            </Button>
          </div>
        </form>
      </AppDialogContent>
    </Dialog>
  );
}
