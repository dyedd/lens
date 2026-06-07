"use client";

import type {
  Dispatch,
  FormEvent,
  FormEventHandler,
  SetStateAction,
} from "react";
import { Plus, RefreshCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import type { ProtocolKind, Site } from "@/lib/api";
import { ProtocolConfigItem } from "./form-sections";
import { SiteModelAggregateView } from "./model-aggregate-view";
import type { AggregatedModel } from "./model-aggregation";
import {
  baseUrlIndexLabel,
  createLocalId,
  credentialIndexLabel,
  genericModelKey,
  siteSubtitle,
  SwitchButton,
  type BatchModelTestOption,
  type FormBaseUrl,
  type FormCredential,
  type FormProtocolConfig,
  type FormState,
  type Locale,
  type TestableModelOption,
} from "./shared";

export function ChannelEditorDialog({
  dialogOpen,
  hasUnsavedChanges,
  editingSiteId,
  locale,
  form,
  newProtocolConfigName,
  protocolConfigNameDialogOpen,
  fetchingProtocolConfigIndex,
  duplicatedProtocolConfigKeys,
  batchTestOptions,
  batchTestingModels,
  testingModel,
  overviewModels,
  modelTestOptionByKey,
  setDialogOpen,
  setEditingSiteId,
  setForm,
  setNewProtocolConfigName,
  setProtocolConfigNameDialogOpen,
  setAdvancedProtocolConfigIndex,
  submit,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  updateCredential,
  removeCredential,
  openAddProtocolConfigDialog,
  addProtocolConfigWithName,
  updateProtocolConfig,
  addManualProtocolConfigModel,
  fetchProtocolModels,
  openBatchModelTestDialog,
  updateModelProtocols,
  openAggregateModelTest,
  closeEditor,
}: {
  dialogOpen: boolean;
  hasUnsavedChanges: boolean;
  editingSiteId: string | null;
  locale: Locale;
  form: FormState;
  newProtocolConfigName: string;
  protocolConfigNameDialogOpen: boolean;
  fetchingProtocolConfigIndex: number | null;
  duplicatedProtocolConfigKeys: Set<string>;
  batchTestOptions: BatchModelTestOption[];
  batchTestingModels: boolean;
  testingModel: boolean;
  overviewModels: AggregatedModel[];
  modelTestOptionByKey: Map<string, TestableModelOption>;
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  setNewProtocolConfigName: Dispatch<SetStateAction<string>>;
  setProtocolConfigNameDialogOpen: Dispatch<SetStateAction<boolean>>;
  setAdvancedProtocolConfigIndex: Dispatch<SetStateAction<number | null>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (index: number, patch: Partial<FormCredential>) => void;
  removeCredential: (index: number) => void;
  openAddProtocolConfigDialog: () => void;
  addProtocolConfigWithName: (event: FormEvent<HTMLFormElement>) => void;
  updateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  addManualProtocolConfigModel: (
    protocolConfigIndex: number,
    credentialId: string,
  ) => void;
  fetchProtocolModels: (protocolConfigIndex: number) => void;
  openBatchModelTestDialog: () => void;
  updateModelProtocols: (
    credentialId: string,
    modelName: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  openAggregateModelTest: (credentialId: string, modelName: string) => void;
  closeEditor: () => void;
}) {
  return (
    <>
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!open && hasUnsavedChanges) {
            const confirmed = window.confirm(
              locale === "zh-CN"
                ? "当前有未保存修改，确定关闭吗？"
                : "You have unsaved changes. Close anyway?",
            );
            if (!confirmed) return;
          }
          setDialogOpen(open);
          if (!open) {
            setEditingSiteId(null);
          }
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
              <section className="grid gap-5">
                <div className="text-base font-semibold text-foreground">
                  {locale === "zh-CN" ? "基本信息" : "Channel and keys"}
                </div>
                <FieldGroup className="gap-4">
                  <Field>
                    <FieldLabel htmlFor="channel-name">
                      {locale === "zh-CN" ? "渠道名称" : "Channel name"}
                    </FieldLabel>
                    <Input
                      id="channel-name"
                      value={form.name}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                    />
                  </Field>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <section className="grid gap-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-foreground">
                          {locale === "zh-CN" ? "请求地址" : "Base URLs"}
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={addBaseUrl}
                        >
                          <Plus data-icon="inline-start" />
                          {locale === "zh-CN" ? "添加" : "Add"}
                        </Button>
                      </div>
                      <FieldGroup className="gap-3">
                        {form.base_urls.map((baseUrl, index) => (
                          <div
                            key={baseUrl.id}
                            className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0"
                          >
                            <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end">
                              <FieldGroup className="min-w-0 gap-3 md:contents">
                                <Field>
                                  <FieldLabel>
                                    {baseUrlIndexLabel(index, locale)}
                                  </FieldLabel>
                                  <Input
                                    className="w-full min-w-0"
                                    value={baseUrl.url}
                                    onChange={(event) =>
                                      updateBaseUrl(index, {
                                        url: event.target.value,
                                      })
                                    }
                                    placeholder="https://api.example.com"
                                  />
                                </Field>
                                <Field>
                                  <FieldLabel>
                                    {locale === "zh-CN" ? "备注" : "Remark"}
                                  </FieldLabel>
                                  <Input
                                    className="w-full min-w-0"
                                    value={baseUrl.name}
                                    onChange={(event) =>
                                      updateBaseUrl(index, {
                                        name: event.target.value,
                                      })
                                    }
                                    placeholder={
                                      locale === "zh-CN" ? "备注" : "Remark"
                                    }
                                  />
                                </Field>
                                <div className="flex h-8 w-8 items-center justify-center">
                                  <SwitchButton
                                    checked={baseUrl.enabled}
                                    onChange={(checked) =>
                                      updateBaseUrl(index, {
                                        enabled: checked,
                                      })
                                    }
                                  />
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="text-muted-foreground"
                                  onClick={() => removeBaseUrl(index)}
                                  disabled={form.base_urls.length <= 1}
                                >
                                  <X size={16} />
                                </Button>
                              </FieldGroup>
                            </div>
                          </div>
                        ))}
                      </FieldGroup>
                    </section>

                    <section className="grid gap-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-foreground">
                          {locale === "zh-CN" ? "密钥" : "API Keys"}
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setForm((current) => ({
                              ...current,
                              credentials: [
                                ...current.credentials,
                                {
                                  id: createLocalId("credential"),
                                  name: "",
                                  api_key: "",
                                  enabled: true,
                                },
                              ],
                            }))
                          }
                        >
                          <Plus data-icon="inline-start" />
                          {locale === "zh-CN" ? "添加" : "Add"}
                        </Button>
                      </div>
                      <FieldGroup className="gap-3">
                        {form.credentials.map((credential, index) => (
                          <div
                            key={credential.id}
                            className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end"
                          >
                            <FieldGroup className="min-w-0 gap-3 md:contents">
                              <Field>
                                <FieldLabel>
                                  {credentialIndexLabel(index, locale)}
                                </FieldLabel>
                                <Input
                                  className="w-full min-w-0"
                                  value={credential.api_key}
                                  onChange={(event) =>
                                    updateCredential(index, {
                                      api_key: event.target.value,
                                    })
                                  }
                                  placeholder="sk-..."
                                />
                              </Field>
                              <Field>
                                <FieldLabel>
                                  {locale === "zh-CN" ? "备注" : "Remark"}
                                </FieldLabel>
                                <Input
                                  className="w-full min-w-0"
                                  value={credential.name}
                                  onChange={(event) =>
                                    updateCredential(index, {
                                      name: event.target.value,
                                    })
                                  }
                                  placeholder={
                                    locale === "zh-CN" ? "备注" : "Remark"
                                  }
                                />
                              </Field>
                              <div className="flex h-8 w-8 items-center justify-center">
                                <SwitchButton
                                  checked={credential.enabled}
                                  onChange={(checked) =>
                                    updateCredential(index, {
                                      enabled: checked,
                                    })
                                  }
                                />
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="text-muted-foreground"
                                onClick={() => removeCredential(index)}
                              >
                                <X size={16} />
                              </Button>
                            </FieldGroup>
                          </div>
                        ))}
                      </FieldGroup>
                    </section>
                  </div>
                </FieldGroup>
              </section>

              <Separator />

              <section className="grid gap-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="text-base font-semibold text-foreground">
                    {locale === "zh-CN" ? "协议配置" : "Protocol configs"}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="justify-start border-dashed"
                    onClick={openAddProtocolConfigDialog}
                  >
                    <Plus data-icon="inline-start" />
                    {locale === "zh-CN"
                      ? "增加一个协议配置"
                      : "Add protocol config"}
                  </Button>
                </div>
                <div className="flex flex-col gap-4">
                  {form.protocolConfigs.map(
                    (protocolConfig, protocolConfigIndex) => (
                      <ProtocolConfigItem
                        key={protocolConfig.id || protocolConfigIndex}
                        form={form}
                        protocolConfig={protocolConfig}
                        protocolConfigIndex={protocolConfigIndex}
                        locale={locale}
                        fetchingProtocolConfigIndex={
                          fetchingProtocolConfigIndex
                        }
                        duplicatedProtocolConfigKeys={
                          duplicatedProtocolConfigKeys
                        }
                        onUpdateProtocolConfig={updateProtocolConfig}
                        onRemoveProtocolConfig={(index) =>
                          setForm((current) => ({
                            ...current,
                            protocolConfigs:
                              current.protocolConfigs.length > 1
                                ? current.protocolConfigs.filter(
                                    (_, currentIndex) => currentIndex !== index,
                                  )
                                : current.protocolConfigs,
                          }))
                        }
                        onAddManualModel={addManualProtocolConfigModel}
                        onFetchModels={fetchProtocolModels}
                        onOpenAdvanced={setAdvancedProtocolConfigIndex}
                      />
                    ),
                  )}
                </div>
                <div className="mt-4">
                  <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-sm font-medium text-foreground">
                      {locale === "zh-CN" ? "模型总览" : "Model Overview"}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={openBatchModelTestDialog}
                        disabled={
                          !batchTestOptions.length ||
                          batchTestingModels ||
                          testingModel
                        }
                      >
                        <RefreshCcw
                          data-icon="inline-start"
                          className={
                            batchTestingModels ? "animate-spin" : undefined
                          }
                        />
                        {locale === "zh-CN" ? "批量测试" : "Batch test"}
                      </Button>
                    </div>
                  </div>
                  <SiteModelAggregateView
                    models={overviewModels}
                    protocolConfigs={form.protocolConfigs}
                    locale={locale}
                    onChangeModelProtocols={updateModelProtocols}
                    onOpenModelTest={openAggregateModelTest}
                    canTestModel={(credentialId, modelName) =>
                      modelTestOptionByKey.has(
                        genericModelKey({
                          credential_id: credentialId,
                          model_name: modelName,
                        }),
                      )
                    }
                    testingDisabled={testingModel || batchTestingModels}
                  />
                </div>
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
      <Dialog
        open={protocolConfigNameDialogOpen}
        onOpenChange={setProtocolConfigNameDialogOpen}
      >
        <AppDialogContent
          className="max-w-md"
          title={locale === "zh-CN" ? "命名协议配置" : "Name protocol config"}
        >
          <form className="grid gap-4" onSubmit={addProtocolConfigWithName}>
            <Field>
              <FieldLabel htmlFor="new-protocol-config-name">
                {locale === "zh-CN" ? "协议配置名称" : "Protocol config name"}
              </FieldLabel>
              <Input
                id="new-protocol-config-name"
                value={newProtocolConfigName}
                autoFocus
                onChange={(event) =>
                  setNewProtocolConfigName(event.target.value)
                }
              />
            </Field>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => setProtocolConfigNameDialogOpen(false)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button type="submit">
                {locale === "zh-CN" ? "创建协议配置" : "Create protocol config"}
              </Button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog>
    </>
  );
}

export function DeleteChannelDialog({
  deleteTarget,
  locale,
  busyId,
  setDeleteTarget,
  removeSite,
}: {
  deleteTarget: Site | null;
  locale: Locale;
  busyId: string | null;
  setDeleteTarget: Dispatch<SetStateAction<Site | null>>;
  removeSite: (site: Site) => void;
}) {
  return (
    <Dialog
      open={Boolean(deleteTarget)}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
    >
      <AppDialogContent
        className="max-w-lg"
        title={locale === "zh-CN" ? "确认删除渠道" : "Delete channel"}
        description={
          locale === "zh-CN"
            ? "删除后该渠道下的协议、模型和模型组成员会一起移除。"
            : "Protocol configs, models, and group members under this channel will be removed together."
        }
      >
        <div className="grid gap-5">
          <div className="rounded-md border bg-muted/30 p-4">
            <strong className="text-foreground">{deleteTarget?.name}</strong>
            <p className="mt-2 text-xs text-muted-foreground">
              {deleteTarget ? siteSubtitle(deleteTarget) : ""}
            </p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => deleteTarget && void removeSite(deleteTarget)}
              disabled={busyId === deleteTarget?.id}
            >
              {busyId === deleteTarget?.id
                ? locale === "zh-CN"
                  ? "删除中..."
                  : "Deleting..."
                : locale === "zh-CN"
                  ? "确认删除"
                  : "Delete"}
            </Button>
          </div>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
