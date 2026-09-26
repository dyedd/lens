import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import type { Site } from "@/lib/api/sites";
import { useI18n } from "@/lib/I18nContext";
import type { ModelStatusFilter } from "./channels/ChannelModelsDialog";
import { ChannelsDialogs } from "./channels/ChannelsDialogs";
import { ChannelsOverview } from "./channels/ChannelsOverview";
import {
  useChannelPersistence,
  useChannelTransfer,
} from "./channels/useChannelCommands";
import { useChannelForm } from "./channels/useChannelForm";
import { useChannelModelPicker } from "./channels/useChannelModelPicker";
import { useChannelModelTest } from "./channels/useChannelModelTest";
import {
  useAggregatedModels,
  useChannelQueries,
} from "./channels/useChannelQueries";
import { useChannelSave } from "./channels/useChannelSave";

/** Coordinates channel management data, dialogs, and user actions. */
export function ChannelsScreen() {
  const { locale } = useI18n();
  const [editorMode, setEditorMode] = useState<"channel" | "models">("channel");
  const [isModelsNested, setIsModelsNested] = useState(false);
  const [modelsStatusFilter, setModelsStatusFilter] =
    useState<ModelStatusFilter>("all");
  const [fetchOnOpen, setFetchOnOpen] = useState(false);
  const queries = useChannelQueries(locale);
  const editor = useChannelForm(locale);
  const save = useChannelSave({
    locale,
    queryClient: queries.queryClient,
    invalidateChannelData: queries.invalidateChannelData,
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

  function openEditor(
    site: Site | null,
    mode: "channel" | "models",
    options: { statusFilter?: ModelStatusFilter; fetch?: boolean } = {},
  ) {
    if (!editor.confirmDiscardChanges()) return;
    setEditorMode(mode);
    setIsModelsNested(false);
    setModelsStatusFilter(options.statusFilter ?? "all");
    setFetchOnOpen(options.fetch ?? false);
    if (site) editor.openEdit(site);
    else editor.openCreate();
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
          onCreate={() => openEditor(null, "channel")}
          onImport={transfer.openBatchImport}
          onOpenEdit={(site) => openEditor(site, "channel")}
          onManageModels={(site) => openEditor(site, "models")}
          onReviewPendingModels={(site) =>
            openEditor(site, "models", { statusFilter: "missing" })
          }
          onFetchModels={(site) => openEditor(site, "models", { fetch: true })}
          syncingSiteId={save.syncingSiteId}
          onSyncModels={(site) => void save.syncSiteModels(site.id)}
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
          isModelsNested={isModelsNested}
          modelsStatusFilter={modelsStatusFilter}
          fetchOnOpen={fetchOnOpen}
          onFetchOnOpenHandled={() => setFetchOnOpen(false)}
          onManageModels={() => {
            setIsModelsNested(true);
            setModelsStatusFilter("all");
            setEditorMode("models");
          }}
          onCloseModels={() => {
            if (isModelsNested) setEditorMode("channel");
            else editor.closeEditor();
          }}
        />
      </section>
    </TooltipProvider>
  );
}
