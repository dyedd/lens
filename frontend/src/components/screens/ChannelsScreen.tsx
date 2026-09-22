import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import type { Site } from "@/lib/api/sites";
import { useI18n } from "@/lib/I18nContext";
import { ChannelsDialogs } from "./channels/ChannelsDialogs";
import { ChannelsOverview } from "./channels/ChannelsOverview";
import {
  useChannelPersistence,
  useChannelTransfer,
} from "./channels/useChannelCommands";
import { useChannelForm } from "./channels/useChannelForm";
import { useChannelModelPicker } from "./channels/useChannelModelPicker";
import {
  useBatchModelTest,
  useChannelModelTest,
} from "./channels/useChannelModelTest";
import {
  useAggregatedModels,
  useChannelQueries,
} from "./channels/useChannelQueries";
import { useModelGroupEnsure } from "./channels/useModelGroupEnsure";

/** Coordinates channel management data, dialogs, and user actions. */
export function ChannelsScreen() {
  const { locale } = useI18n();
  const [editorMode, setEditorMode] = useState<"channel" | "models">("channel");
  const [syncOnOpen, setSyncOnOpen] = useState(false);
  const queries = useChannelQueries(locale);
  const editor = useChannelForm(locale);
  const modelGroups = useModelGroupEnsure({
    locale,
    queryClient: queries.queryClient,
    editor,
  });
  const persistence = useChannelPersistence({
    locale,
    queryClient: queries.queryClient,
    invalidateChannelData: queries.invalidateChannelData,
    editor,
  });
  const transfer = useChannelTransfer({
    locale,
    queryClient: queries.queryClient,
    invalidateChannelData: queries.invalidateChannelData,
  });
  const picker = useChannelModelPicker({
    form: editor.form,
    setForm: editor.setForm,
    locale,
  });
  const modelTest = useChannelModelTest(editor.form, locale);
  const batchTest = useBatchModelTest({
    locale,
    prompts: modelTest.modelTestPrompts,
    optionByKey: modelTest.modelTestOptionByKey,
    buildPayload: modelTest.buildModelTestPayload,
  });
  const overviewModels = useAggregatedModels(
    editor.form.protocolConfigs,
    editor.form.credentials,
    locale,
  );

  useEffect(() => {
    if (!queries.sitesIsError) return;
    toast.error(
      locale === "zh-CN" ? "渠道加载失败" : "Failed to load channels",
      {
        id: "channels-load-error",
        description:
          queries.sitesError instanceof Error
            ? queries.sitesError.message
            : locale === "zh-CN"
              ? "无法读取渠道"
              : "Unable to read channels",
      },
    );
  }, [locale, queries.sitesError, queries.sitesIsError]);

  function openCreate() {
    if (!editor.confirmDiscardChanges()) return;
    batchTest.clearBatchModelTestResults();
    setEditorMode("channel");
    setSyncOnOpen(false);
    editor.openCreate();
  }
  function openEdit(site: Site) {
    if (!editor.confirmDiscardChanges()) return;
    batchTest.clearBatchModelTestResults();
    setEditorMode("channel");
    setSyncOnOpen(false);
    editor.openEdit(site);
  }
  function openManageModels(site: Site) {
    if (!editor.confirmDiscardChanges()) return;
    batchTest.clearBatchModelTestResults();
    setEditorMode("models");
    setSyncOnOpen(false);
    editor.openEdit(site);
  }
  function openSyncRemoteModels(site: Site) {
    if (!editor.confirmDiscardChanges()) return;
    batchTest.clearBatchModelTestResults();
    setEditorMode("models");
    setSyncOnOpen(true);
    editor.openEdit(site);
  }

  return (
    <TooltipProvider>
      <section>
        <ChannelsOverview
          locale={locale}
          visibleSites={queries.visibleSites}
          isLoading={queries.isLoading}
          search={queries.search}
          statusFilter={queries.statusFilter}
          tags={queries.tags}
          tagFilter={queries.tagFilter}
          sortBy={queries.sortBy}
          activeFilterCount={queries.activeFilterCount}
          busyId={persistence.busyId}
          onSearchChange={queries.setSearch}
          onStatusChange={queries.setStatusFilter}
          onTagChange={queries.setTagFilter}
          onSortChange={queries.setSortBy}
          onReset={queries.resetFilters}
          onRefresh={() =>
            void queries.queryClient.invalidateQueries({ queryKey: ["sites"] })
          }
          onCreate={openCreate}
          onImport={transfer.openBatchImport}
          onOpenEdit={openEdit}
          onManageModels={openManageModels}
          onSyncRemoteModels={openSyncRemoteModels}
          onToggleSiteEnabled={persistence.toggleSiteEnabled}
          onDelete={persistence.setDeleteTarget}
          onBulkEnabled={persistence.applyEnabled}
          onBulkDelete={persistence.removeSites}
        />
        <ChannelsDialogs
          locale={locale}
          availableTags={queries.tags}
          editor={editor}
          persistence={persistence}
          transfer={transfer}
          picker={picker}
          modelTest={modelTest}
          batchTest={batchTest}
          modelGroups={modelGroups}
          overviewModels={overviewModels}
          editorMode={editorMode}
          syncOnOpen={syncOnOpen}
          onSyncOnOpenHandled={() => setSyncOnOpen(false)}
          onManageModels={() => {
            const site = queries.visibleSites.find(
              (item) => item.id === editor.editingSiteId,
            );
            if (site) openManageModels(site);
          }}
        />
      </section>
    </TooltipProvider>
  );
}
