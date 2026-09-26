import { type Dispatch, type SetStateAction, useState } from "react";
import type { ModelGroup } from "@/lib/api/groups";
import { useI18n } from "@/lib/I18nContext";
import { lazyComponent } from "@/lib/lazyComponent";
import { GroupsOverview } from "./groups/GroupsOverview";
import {
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
  const [candidateSearch, setCandidateSearch] = useState("");
  const [expandedChannels, setExpandedChannels] = useState<string[]>([]);
  const [memberStatusFilter, setMemberStatusFilter] =
    useState<MemberStatusFilter>("all");
  const setDialogOpen: Dispatch<SetStateAction<boolean>> = (value) => {
    const isOpen = typeof value === "function" ? value(dialogOpen) : value;
    if (!isOpen) {
      setCandidateSearch("");
      setExpandedChannels([]);
    }
    setDialogOpenState(isOpen);
  };
  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }
  function openEdit(group: ModelGroup) {
    setEditingId(group.id);
    setForm(modelGroupToForm(group));
    setDialogOpen(true);
  }
  return {
    candidateSearch,
    dialogOpen,
    editingId,
    expandedChannels,
    form,
    memberStatusFilter,
    openCreate,
    openEdit,
    setCandidateSearch,
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
    expandedChannels: editor.expandedChannels,
    form: editor.form,
    isCreating: !editor.editingId,
    locale,
    setExpandedChannels: editor.setExpandedChannels,
    setForm: editor.setForm,
  });
  const commands = useGroupCommands({
    editingId: editor.editingId,
    form: editor.form,
    groups: queries.groups ?? [],
    invalidateGroupData: queries.invalidateGroupData,
    locale,
    setDialogOpen: editor.setDialogOpen,
    setEditingId: editor.setEditingId,
    setForm: editor.setForm,
  });

  return (
    <section>
      <GroupsOverview
        locale={locale}
        visibleGroups={filters.visibleGroups}
        unplacedModels={queries.unplacedModels}
        joinableGroupIds={
          new Set(
            queries.groupRows
              .filter((group) => !group.is_route_group)
              .map((group) => group.id),
          )
        }
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
        onChangeStrategy={commands.changeStrategy}
        onMerge={commands.mergeGroup}
        onDelete={commands.setDeleteTarget}
        onTest={modelTest.openModelTest}
        onBulkEnabled={commands.applyEnabled}
        onBulkStrategy={commands.applyStrategy}
        onBulkDelete={commands.removeGroups}
        onAddModelsToGroup={commands.addModelsToGroup}
        onCreateGroupForModels={commands.createGroupForModels}
        onAutoPlace={commands.autoPlaceModels}
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
          changeName={candidates.changeName}
          routeTargetOptions={queries.routeTargetOptions}
          changeRouteTarget={candidates.changeRouteTarget}
          changeMatchRules={candidates.changeMatchRules}
          matchRegexInvalid={candidates.matchRegexInvalid}
          ruleMatchModelCount={candidates.ruleMatchModelCount}
          ruleMatchSourceCount={candidates.ruleMatchSourceCount}
          candidateSearch={editor.candidateSearch}
          changeCandidateSearch={editor.setCandidateSearch}
          refetchCandidates={queries.candidateQuery.refetch}
          isFetchingCandidates={queries.candidateQuery.isFetching}
          groupedCandidates={candidates.groupedCandidates}
          expandedChannels={candidates.expandedChannels}
          toggleChannel={candidates.toggleChannel}
          foldedMembers={members.foldedMembers}
          addCandidate={candidates.addCandidate}
          candidateIsError={queries.candidateQuery.isError}
          candidateListError={queries.candidateQuery.error}
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
          locale={locale}
          targetName={modelTest.targetName}
          rows={modelTest.batchTestRows}
          testing={modelTest.isBatchModelTestRunning}
          prompts={modelTest.prompts}
          promptMode={modelTest.batchTestPromptMode}
          prompt={modelTest.batchTestPrompt}
          onPromptModeChange={modelTest.changeBatchTestPromptMode}
          onPromptChange={modelTest.changeBatchTestPrompt}
          onProtocolChange={modelTest.changeBatchTestProtocol}
          onRun={() => void modelTest.runBatchModelTests()}
          onClose={() => modelTest.changeBatchModelTestOpen(false)}
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
