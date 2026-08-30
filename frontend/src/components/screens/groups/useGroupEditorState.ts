import { type Dispatch, type SetStateAction, useState } from "react";
import type { ModelGroup } from "@/lib/api/groups";
import { modelGroupToForm } from "./groupForm";
import {
  type CandidateSearchMode,
  EMPTY_FORM,
  type FormState,
  type MemberStatusFilter,
} from "./groupTypes";

/** Manage model group dialog state and direct form interactions. */
export function useGroupEditorState() {
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
    const hasSavedFilter = Boolean(
      group.sync_filter_mode && group.sync_filter_query.trim(),
    );
    setEditingId(group.id);
    setForm(modelGroupToForm(group));
    setCandidateSearchValue(
      hasSavedFilter ? group.sync_filter_query : group.name,
    );
    setCandidateSearchMode(
      group.sync_filter_mode === "regex" ? "regex" : "contains",
    );
    setCandidateSearchUsesGroupName(
      !hasSavedFilter && group.sync_filter_mode !== "regex",
    );
    setDialogOpen(true);
  }

  function changeCandidateSearchMode(mode: CandidateSearchMode) {
    setCandidateSearchMode(mode);
    if (mode === "contains") {
      setCandidateSearchValue(form.name);
      setCandidateSearchUsesGroupName(true);
      return;
    }
    setCandidateSearchUsesGroupName(false);
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
