import { Plus, RefreshCcw } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ModelGroup } from "@/lib/api/groups";
import { useI18n } from "@/lib/I18nContext";
import { lazyComponent } from "@/lib/lazyComponent";
import { GroupsOverview } from "./groups/GroupsOverview";
import {
  type CandidateSearchMode,
  EMPTY_FORM,
  type FormState,
  type MemberStatusFilter,
} from "./groups/groupTypes";
import { modelGroupToForm } from "./groups/groupView";
import { useGroupCandidates } from "./groups/useGroupCandidates";
import { useGroupCommands } from "./groups/useGroupCommands";
import { useGroupMembers } from "./groups/useGroupMembers";
import { useGroupModelTest } from "./groups/useGroupModelTest";
import { useGroupFilters, useGroupsQueries } from "./groups/useGroupsQueries";

const GroupEditorDialog = lazyComponent(() =>
  import("./groups/ModelGroupDialogs").then(
    (module) => module.GroupEditorDialog,
  ),
);
const DeleteGroupDialog = lazyComponent(() =>
  import("./groups/ModelGroupDialogs").then(
    (module) => module.DeleteGroupDialog,
  ),
);
const BatchModelTestDialog = lazyComponent(() =>
  import("./channels/BatchModelTestDialog").then(
    (module) => module.BatchModelTestDialog,
  ),
);

function useGroupEditorState() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpenState] = useState(false);
  const [candidateSearchMode, setCandidateSearchMode] =
    useState<CandidateSearchMode>("contains");
  const [candidateSearchValue, setCandidateSearchValue] = useState("");
  const [candidateSearchUsesGroupName, setCandidateSearchUsesGroupName] =
    useState(true);
  const [expandedChannels, setExpandedChannels] = useState<string[]>([]);
  const [memberStatusFilter, setMemberStatusFilter] =
    useState<MemberStatusFilter>("all");
  const candidateSearch =
    candidateSearchMode === "contains" && candidateSearchUsesGroupName
      ? form.name
      : candidateSearchValue;
  const setDialogOpen: Dispatch<SetStateAction<boolean>> = (value) => {
    const isOpen = typeof value === "function" ? value(dialogOpen) : value;
    if (!isOpen) {
      setCandidateSearchValue("");
      setCandidateSearchMode("contains");
      setCandidateSearchUsesGroupName(true);
      setExpandedChannels([]);
    }
    setDialogOpenState(isOpen);
  };
  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setCandidateSearchValue("");
    setCandidateSearchMode("contains");
    setCandidateSearchUsesGroupName(true);
    setDialogOpen(true);
  }
  function openEdit(group: ModelGroup) {
    const saved = Boolean(
      group.sync_filter_mode && group.sync_filter_query.trim(),
    );
    setEditingId(group.id);
    setForm(modelGroupToForm(group));
    setCandidateSearchValue(saved ? group.sync_filter_query : group.name);
    setCandidateSearchMode(
      group.sync_filter_mode === "regex" ? "regex" : "contains",
    );
    setCandidateSearchUsesGroupName(
      !saved && group.sync_filter_mode !== "regex",
    );
    setDialogOpen(true);
  }
  function changeCandidateSearchMode(mode: CandidateSearchMode) {
    setCandidateSearchMode(mode);
    if (mode === "contains") {
      setCandidateSearchValue(form.name);
      setCandidateSearchUsesGroupName(true);
    } else setCandidateSearchUsesGroupName(false);
  }
  function changeCandidateSearch(value: string) {
    setCandidateSearchValue(value);
    setCandidateSearchUsesGroupName(false);
  }
  function changeRouteTarget(routeGroupId: string) {
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      sync_filter_mode: routeGroupId ? "" : current.sync_filter_mode,
      sync_filter_query: routeGroupId ? "" : current.sync_filter_query,
      fallback_group_ids: routeGroupId ? [] : current.fallback_group_ids,
    }));
    setExpandedChannels([]);
  }
  return {
    candidateSearch,
    candidateSearchMode,
    changeCandidateSearch,
    changeCandidateSearchMode,
    changeRouteTarget,
    dialogOpen,
    editingId,
    expandedChannels,
    form,
    memberStatusFilter,
    openCreate,
    openEdit,
    setDialogOpen,
    setEditingId,
    setExpandedChannels,
    setForm,
    setMemberStatusFilter,
  };
}

/** Render the model group management screen. */
export function GroupsScreen() {
  const { locale } = useI18n();
  const editor = useGroupEditorState();
  const queries = useGroupsQueries({
    dialogOpen: editor.dialogOpen,
    editingId: editor.editingId,
    form: editor.form,
    locale,
  });
  const filters = useGroupFilters(queries.groupRows, locale);
  const members = useGroupMembers(
    editor.form,
    queries.evaluatedItems,
    editor.setForm,
    editor.memberStatusFilter,
  );
  const modelTest = useGroupModelTest(locale);
  const candidates = useGroupCandidates({
    candidateResponse: queries.candidateQuery.data,
    candidateSearch: editor.candidateSearch,
    candidateSearchMode: editor.candidateSearchMode,
    expandedChannels: editor.expandedChannels,
    form: editor.form,
    locale,
    setExpandedChannels: editor.setExpandedChannels,
    setForm: editor.setForm,
  });
  const commands = useGroupCommands({
    editingId: editor.editingId,
    form: editor.form,
    invalidateGroupData: queries.invalidateGroupData,
    locale,
    queryClient: queries.queryClient,
    setDialogOpen: editor.setDialogOpen,
    setEditingId: editor.setEditingId,
    setForm: editor.setForm,
  });
  const candidateListError = queries.candidateQuery.error;

  return (
    <>
      <GroupsHeaderActions
        locale={locale}
        openCreate={editor.openCreate}
        syncingPrices={commands.syncingPrices}
        syncPrices={commands.syncPrices}
      />

      <section className="flex flex-col gap-4">
        <GroupsOverview
          locale={locale}
          hasModelPrefixOptions={filters.hasModelPrefixOptions}
          modelPrefixOptions={filters.modelPrefixOptions}
          effectiveSelectedModelPrefix={filters.effectiveSelectedModelPrefix}
          setSelectedModelPrefix={filters.setSelectedModelPrefix}
          isLoading={queries.isLoading}
          groupsIsError={queries.groupsIsError}
          visibleGroups={filters.visibleGroups}
          busyId={commands.busyId}
          cardDragging={commands.cardDragging}
          setCardDragging={commands.setCardDragging}
          search={filters.search}
          strategyFilter={filters.strategyFilter}
          sortBy={filters.sortBy}
          activeFilterCount={filters.activeFilterCount}
          setSearch={filters.setSearch}
          setStrategyFilter={filters.setStrategyFilter}
          setSortBy={filters.setSortBy}
          resetFilters={filters.resetFilters}
          openEdit={editor.openEdit}
          changeStrategy={commands.changeStrategy}
          reorderGroupMembers={commands.reorderGroupMembers}
          reorderGroupChannels={commands.reorderGroupChannels}
          removeGroupChannel={commands.removeGroupChannel}
          removeGroupMember={commands.removeGroupMember}
          toggleGroupEnabled={commands.toggleGroupEnabled}
          setDeleteTarget={commands.setDeleteTarget}
          testingModel={modelTest.testingModel}
          openModelTest={modelTest.openModelTest}
        />

        {editor.dialogOpen ? (
          <GroupEditorDialog
            dialogOpen={editor.dialogOpen}
            setDialogOpen={editor.setDialogOpen}
            editingId={editor.editingId}
            locale={locale}
            submit={commands.submit}
            form={editor.form}
            setForm={editor.setForm}
            routeTargetOptions={queries.routeTargetOptions}
            changeRouteTarget={editor.changeRouteTarget}
            candidateSearchMode={editor.candidateSearchMode}
            changeCandidateSearchMode={editor.changeCandidateSearchMode}
            candidateSearch={editor.candidateSearch}
            changeCandidateSearch={editor.changeCandidateSearch}
            addMatchedItems={candidates.addMatchedItems}
            candidateRegexInvalid={candidates.candidateRegexInvalid}
            filteredCandidates={candidates.filteredCandidates}
            refetchCandidates={queries.candidateQuery.refetch}
            isFetchingCandidates={queries.candidateQuery.isFetching}
            applySavedFilter={candidates.applySavedFilter}
            clearSavedFilter={candidates.clearSavedFilter}
            groupedCandidates={candidates.groupedCandidates}
            expandedChannels={candidates.expandedChannels}
            toggleChannel={candidates.toggleChannel}
            foldedMembers={members.foldedMembers}
            addCandidate={candidates.addCandidate}
            candidateIsError={queries.candidateQuery.isError}
            candidateListError={candidateListError}
            disabledItemCount={members.disabledItemCount}
            invalidItemCount={members.invalidItemCount}
            removeInvalidItems={members.removeInvalidItems}
            removeDisabledMembers={members.removeDisabledMembers}
            clearMembers={members.clearMembers}
            setAllMembersEnabled={members.setAllMembersEnabled}
            memberStatusFilter={editor.memberStatusFilter}
            setMemberStatusFilter={editor.setMemberStatusFilter}
            visibleFoldedMembers={members.visibleFoldedMembers}
            visibleChannelGroups={members.visibleChannelGroups}
            toggleChannelMembers={members.toggleChannelMembers}
            toggleFoldedMember={members.toggleFoldedMember}
            removeFoldedMember={members.removeFoldedMember}
            moveChannelGroup={members.moveChannelGroup}
            moveFoldedMember={members.moveFoldedMember}
            moveFoldedMemberWithinChannel={
              members.moveFoldedMemberWithinChannel
            }
          />
        ) : null}

        {modelTest.batchModelTestOpen ? (
          <BatchModelTestDialog
            open={modelTest.batchModelTestOpen}
            locale={locale}
            modelTestPrompts={modelTest.modelTestPrompts}
            batchTestPromptMode={modelTest.batchTestPromptMode}
            batchTestPrompt={modelTest.batchTestPrompt}
            batchTestConcurrency={modelTest.batchTestConcurrency}
            batchTestOptions={modelTest.batchTestOptions}
            batchTestRows={modelTest.batchTestRows}
            isBatchModelTestRunning={modelTest.isBatchModelTestRunning}
            onOpenChange={modelTest.changeBatchModelTestOpen}
            onPromptModeChange={modelTest.changeBatchTestPromptMode}
            onPromptChange={modelTest.changeBatchTestPrompt}
            onConcurrencyChange={modelTest.setBatchTestConcurrency}
            onProtocolChange={modelTest.changeBatchTestProtocol}
            onRun={() => void modelTest.runBatchModelTests()}
          />
        ) : null}

        {commands.deleteTarget ? (
          <DeleteGroupDialog
            deleteTarget={commands.deleteTarget}
            locale={locale}
            busyId={commands.busyId}
            setDeleteTarget={commands.setDeleteTarget}
            remove={commands.remove}
          />
        ) : null}
      </section>
    </>
  );
}

/** Render model group creation and price synchronization actions. */
function GroupsHeaderActions({
  locale,
  openCreate,
  syncingPrices,
  syncPrices,
}: {
  locale: "zh-CN" | "en-US";
  openCreate: () => void;
  syncingPrices: boolean;
  syncPrices: () => void;
}) {
  const syncPricesLabel = syncingPrices
    ? locale === "zh-CN"
      ? "同步中..."
      : "Syncing..."
    : locale === "zh-CN"
      ? "同步价格"
      : "Sync prices";
  const createGroupLabel =
    locale === "zh-CN" ? "新增模型组" : "New model group";

  return (
    <DashboardHeaderActions>
      <div className="flex items-center justify-end gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={syncPricesLabel}
              onClick={() => void syncPrices()}
              disabled={syncingPrices}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={syncingPrices ? "animate-spin" : ""}
              />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {syncPricesLabel}
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              type="button"
              variant="ghost"
              aria-label={createGroupLabel}
              onClick={openCreate}
            >
              <Plus />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {createGroupLabel}
          </TooltipContent>
        </Tooltip>
      </div>
    </DashboardHeaderActions>
  );
}
