import { type Dispatch, type SetStateAction, useState } from "react";
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
    setDialogOpen: editor.setDialogOpen,
    setEditingId: editor.setEditingId,
    setForm: editor.setForm,
  });
  const candidateListError = queries.candidateQuery.error;

  return (
    <section>
      <GroupsOverview
        locale={locale}
        visibleGroups={filters.visibleGroups}
        isLoading={queries.isLoading}
        search={filters.search}
        strategyFilter={filters.strategyFilter}
        sortBy={filters.sortBy}
        activeFilterCount={filters.activeFilterCount}
        protocolOptions={filters.protocolOptions}
        protocolFilter={filters.effectiveProtocolFilter}
        busyId={commands.busyId}
        testingModel={modelTest.testingModel}
        onSearchChange={filters.setSearch}
        onStrategyChange={filters.setStrategyFilter}
        onSortChange={filters.setSortBy}
        onProtocolChange={filters.setProtocolFilter}
        onReset={filters.resetFilters}
        onRefresh={() =>
          void queries.queryClient.invalidateQueries({ queryKey: ["groups"] })
        }
        onCreate={editor.openCreate}
        onOpenEdit={editor.openEdit}
        onToggleEnabled={commands.toggleGroupEnabled}
        onDelete={commands.setDeleteTarget}
        onTest={modelTest.openModelTest}
        onBulkEnabled={commands.applyEnabled}
        onBulkDelete={commands.removeGroups}
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
          moveFoldedMemberWithinChannel={members.moveFoldedMemberWithinChannel}
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
  );
}
