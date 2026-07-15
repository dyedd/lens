"use client";

import dynamic from "next/dynamic";
import { useI18n } from "@/lib/I18nContext";
import { GroupsHeaderActions } from "./groups/GroupsHeaderActions";
import { GroupsOverview } from "./groups/GroupsOverview";
import { useGroupCandidates } from "./groups/useGroupCandidates";
import { useGroupCommands } from "./groups/useGroupCommands";
import { useGroupEditorState } from "./groups/useGroupEditorState";
import { useGroupFilters } from "./groups/useGroupFilters";
import { useGroupMembers } from "./groups/useGroupMembers";
import { useGroupsQueries } from "./groups/useGroupsQueries";

const GroupEditorDialog = dynamic(() =>
  import("./groups/ModelGroupDialogs").then(
    (module) => module.GroupEditorDialog,
  ),
);
const DeleteGroupDialog = dynamic(() =>
  import("./groups/ModelGroupDialogs").then(
    (module) => module.DeleteGroupDialog,
  ),
);

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
          protocolFilter={filters.protocolFilter}
          strategyFilter={filters.strategyFilter}
          sortBy={filters.sortBy}
          activeFilterCount={filters.activeFilterCount}
          setSearch={filters.setSearch}
          setProtocolFilter={filters.setProtocolFilter}
          setStrategyFilter={filters.setStrategyFilter}
          setSortBy={filters.setSortBy}
          resetFilters={filters.resetFilters}
          openEdit={editor.openEdit}
          changeStrategy={commands.changeStrategy}
          reorderGroupMembers={commands.reorderGroupMembers}
          removeGroupMember={commands.removeGroupMember}
          toggleGroupEnabled={commands.toggleGroupEnabled}
          setDeleteTarget={commands.setDeleteTarget}
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
            toggleProtocol={editor.toggleProtocol}
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
            unavailableItemCount={members.unavailableItemCount}
            removeInvalidItems={members.removeInvalidItems}
            removeUnavailableItems={members.removeUnavailableItems}
            removeDisabledMembers={members.removeDisabledMembers}
            clearMembers={members.clearMembers}
            setAllMembersEnabled={members.setAllMembersEnabled}
            memberStatusFilter={editor.memberStatusFilter}
            setMemberStatusFilter={editor.setMemberStatusFilter}
            visibleFoldedMembers={members.visibleFoldedMembers}
            draggingIndex={editor.draggingIndex}
            toggleFoldedMember={members.toggleFoldedMember}
            removeFoldedMember={members.removeFoldedMember}
            setDraggingIndex={editor.setDraggingIndex}
            moveFoldedMember={members.moveFoldedMember}
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
