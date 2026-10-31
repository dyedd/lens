import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import type { Site } from "@/lib/api/sites";
import { useI18n } from "@/lib/I18nContext";
import { ChannelsDialogs } from "./channels/ChannelsDialogs";
import { ChannelsOverview } from "./channels/ChannelsOverview";
import type { ModelStatusFilter } from "./channels/channelTypes";
import { useAggregatedModels } from "./channels/useAggregatedModels";
import {
  useChannelPersistence,
  useChannelTransfer,
} from "./channels/useChannelCommands";
import { useChannelForm } from "./channels/useChannelForm";
import { useChannelModelPicker } from "./channels/useChannelModelPicker";
import { useChannelModelTest } from "./channels/useChannelModelTest";
import { useChannelQueries } from "./channels/useChannelQueries";
import { useChannelSave } from "./channels/useChannelSave";

/** Coordinates channel management data, dialogs, and user actions. */
export function ChannelsScreen() {
  const { locale } = useI18n();
  const [editorMode, setEditorMode] = useState<"channel" | "models">("channel");
  const [modelsStatusFilter, setModelsStatusFilter] =
    useState<ModelStatusFilter>("all");
  const [remoteModelsOpen, setRemoteModelsOpen] = useState(false);
  const queries = useChannelQueries(locale);
  const editor = useChannelForm(locale);

  function openEditor(
    site: Site | null,
    mode: "channel" | "models",
    options: { statusFilter?: ModelStatusFilter } = {},
  ) {
    setRemoteModelsOpen(false);
    setEditorMode(mode);
    setModelsStatusFilter(options.statusFilter ?? "all");
    if (site) editor.openEdit(site);
    else editor.openCreate();
  }

  function handleCreated(site: Site) {
    openEditor(site, "models");
    setRemoteModelsOpen(true);
  }

  const save = useChannelSave({
    locale,
    queryClient: queries.queryClient,
    invalidateChannelData: queries.invalidateChannelData,
    editor,
    onCreated: handleCreated,
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
  const overviewModels = useAggregatedModels(editor.form, locale);

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
          onCreate={() => openEditor(null, "channel")}
          onImport={transfer.openBatchImport}
          onOpenEdit={(site) => openEditor(site, "channel")}
          onManageModels={(site) => openEditor(site, "models")}
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
          save={save}
          overviewModels={overviewModels}
          editorMode={editorMode}
          modelsStatusFilter={modelsStatusFilter}
          onCloseModels={() => {
            setRemoteModelsOpen(false);
            editor.closeEditor();
          }}
          remoteModelsOpen={remoteModelsOpen}
          onRemoteModelsOpenChange={setRemoteModelsOpen}
        />
      </section>
    </TooltipProvider>
  );
}
