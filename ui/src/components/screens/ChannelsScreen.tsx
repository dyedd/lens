"use client";

import { useEffect, useState } from "react";
import { FileInput, Plus, RefreshCcw } from "lucide-react";
import { toast } from "sonner";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { useI18n } from "@/lib/I18nContext";
import type { Site } from "@/lib/api";
import { ChannelsDialogs } from "./channels/ChannelsDialogs";
import { ChannelsOverview } from "./channels/ChannelsOverview";
import { useAggregatedModels } from "./channels/useAggregatedModels";
import { useBatchModelTest } from "./channels/useBatchModelTest";
import { useChannelForm } from "./channels/useChannelForm";
import { useChannelModelPicker } from "./channels/useChannelModelPicker";
import { useChannelModelTest } from "./channels/useChannelModelTest";
import { useChannelPersistence } from "./channels/useChannelPersistence";
import { useChannelQueries } from "./channels/useChannelQueries";
import { useChannelTransfer } from "./channels/useChannelTransfer";
import { useModelGroupEnsure } from "./channels/useModelGroupEnsure";

/** Coordinates channel management data, dialogs, and user actions. */
export function ChannelsScreen() {
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [advancedConfigIndex, setAdvancedConfigIndex] = useState<number | null>(
    null,
  );
  const queries = useChannelQueries(locale);
  const editor = useChannelForm(locale);
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
  const modelGroups = useModelGroupEnsure({
    locale,
    queryClient: queries.queryClient,
    validateSiteForm: editor.validateSiteForm,
    saveCurrentSite: persistence.saveCurrentSite,
    invalidateChannelData: queries.invalidateChannelData,
  });
  const overviewModels = useAggregatedModels(
    editor.form.protocolConfigs,
    editor.form.base_urls,
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
    editor.openCreate();
  }
  function openEdit(site: Site) {
    if (!editor.confirmDiscardChanges()) return;
    batchTest.clearBatchModelTestResults();
    editor.openEdit(site);
  }

  return (
    <TooltipProvider>
      <DashboardHeaderActions>
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={locale === "zh-CN" ? "新增渠道" : "Add channels"}
                >
                  <Plus />
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {locale === "zh-CN" ? "新增渠道" : "Add channels"}
            </TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={openCreate}>
              <Plus />
              {locale === "zh-CN" ? "新建渠道" : "New channel"}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={transfer.openBatchImport}>
              <FileInput />
              {locale === "zh-CN" ? "批量导入" : "Import channels"}
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => void transfer.openChannelModelSync()}
            >
              <RefreshCcw />
              {locale === "zh-CN" ? "同步模型" : "Sync models"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </DashboardHeaderActions>
      <section className="flex flex-col gap-4">
        <ChannelsOverview
          locale={locale}
          visibleSites={queries.visibleSites}
          isLoading={queries.isLoading}
          sitesIsError={queries.sitesIsError}
          siteRuntimeById={queries.siteRuntimeById}
          channelHealthById={queries.channelHealthById}
          timeZone={timeZone}
          search={queries.search}
          statusFilter={queries.statusFilter}
          protocolFilter={queries.protocolFilter}
          sortBy={queries.sortBy}
          activeFilterCount={queries.activeFilterCount}
          busyId={persistence.busyId}
          onSearchChange={queries.setSearch}
          onStatusChange={queries.setStatusFilter}
          onProtocolChange={queries.setProtocolFilter}
          onSortChange={queries.setSortBy}
          onReset={queries.resetFilters}
          onOpenEdit={openEdit}
          onToggleSiteEnabled={persistence.toggleSiteEnabled}
          setDeleteTarget={persistence.setDeleteTarget}
        />
        <ChannelsDialogs
          locale={locale}
          editor={editor}
          persistence={persistence}
          transfer={transfer}
          picker={picker}
          modelTest={modelTest}
          batchTest={batchTest}
          modelGroups={modelGroups}
          overviewModels={overviewModels}
          advancedConfigIndex={advancedConfigIndex}
          setAdvancedConfigIndex={setAdvancedConfigIndex}
        />
      </section>
    </TooltipProvider>
  );
}
