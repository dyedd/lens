"use client";

import type { Dispatch, FormEventHandler, SetStateAction } from "react";

import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Separator } from "@/components/ui/Separator";
import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ProtocolKind,
} from "@/lib/api";
import { ModelGroupCandidateList } from "./ModelGroupCandidateList";
import { ModelGroupCandidateToolbar } from "./ModelGroupCandidateToolbar";
import { ModelGroupSelectedMembers } from "./ModelGroupSelectedMembers";
import { ModelGroupSettings } from "./ModelGroupSettings";
import {
  itemKey,
  type CandidateChannelGroup,
  type CandidateSearchMode,
  type FoldedMember,
  type FormState,
  type MemberStatusFilter,
} from "./modelGroupUtils";

interface GroupEditorDialogProps {
  dialogOpen: boolean;
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  editingId: string | null;
  locale: "zh-CN" | "en-US";
  submit: FormEventHandler<HTMLFormElement>;
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  toggleProtocol: (protocol: ProtocolKind) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
  candidateSearchMode: CandidateSearchMode;
  changeCandidateSearchMode: (mode: CandidateSearchMode) => void;
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  addMatchedItems: () => void;
  candidateRegexInvalid: boolean;
  filteredCandidates: ModelGroupCandidateItem[];
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
  applySavedFilter: () => void;
  clearSavedFilter: () => void;
  groupedCandidates: CandidateChannelGroup[];
  expandedChannels: string[];
  toggleChannel: (channelId: string) => void;
  foldedMembers: FoldedMember[];
  addCandidate: (candidate: ModelGroupCandidateItem) => void;
  candidateIsError: boolean;
  candidateListError: unknown;
  disabledItemCount: number;
  invalidItemCount: number;
  unavailableItemCount: number;
  removeInvalidItems: () => void;
  removeUnavailableItems: () => void;
  removeDisabledMembers: () => void;
  clearMembers: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  draggingIndex: number | null;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  setDraggingIndex: Dispatch<SetStateAction<number | null>>;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
}

interface DeleteGroupDialogProps {
  deleteTarget: ModelGroup | null;
  locale: "zh-CN" | "en-US";
  busyId: string | null;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
  remove: (item: ModelGroup) => void;
}

/** Render the create or edit dialog for a model group. */
export function GroupEditorDialog(props: GroupEditorDialogProps) {
  const {
    dialogOpen,
    setDialogOpen,
    editingId,
    locale,
    submit,
    form,
    setForm,
  } = props;
  const existingItemKeys = new Set(form.items.map((item) => itemKey(item)));

  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <AppDialogContent
        className="h-[92dvh] max-w-6xl sm:h-[88vh]"
        title={
          editingId
            ? locale === "zh-CN"
              ? "编辑模型组"
              : "Edit group"
            : locale === "zh-CN"
              ? "新建模型组"
              : "Create group"
        }
      >
        <form className="flex flex-col gap-4 pr-1" onSubmit={submit}>
          <div className="flex flex-col gap-4">
            <ModelGroupSettings
              locale={locale}
              form={form}
              setForm={setForm}
              toggleProtocol={props.toggleProtocol}
              routeTargetOptions={props.routeTargetOptions}
              changeRouteTarget={props.changeRouteTarget}
            />

            {!form.route_group_id ? (
              <>
                <Separator />
                <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                  <section className="flex flex-col rounded-lg bg-muted/10">
                    <ModelGroupCandidateToolbar
                      locale={locale}
                      form={form}
                      candidateSearchMode={props.candidateSearchMode}
                      changeCandidateSearchMode={
                        props.changeCandidateSearchMode
                      }
                      candidateSearch={props.candidateSearch}
                      changeCandidateSearch={props.changeCandidateSearch}
                      addMatchedItems={props.addMatchedItems}
                      candidateRegexInvalid={props.candidateRegexInvalid}
                      filteredCandidateCount={props.filteredCandidates.length}
                      refetchCandidates={props.refetchCandidates}
                      isFetchingCandidates={props.isFetchingCandidates}
                      applySavedFilter={props.applySavedFilter}
                      clearSavedFilter={props.clearSavedFilter}
                    />
                    <ModelGroupCandidateList
                      locale={locale}
                      protocols={form.protocols}
                      groupedCandidates={props.groupedCandidates}
                      expandedChannels={props.expandedChannels}
                      existingItemKeys={existingItemKeys}
                      toggleChannel={props.toggleChannel}
                      addCandidate={props.addCandidate}
                      candidateIsError={props.candidateIsError}
                      candidateListError={props.candidateListError}
                    />
                  </section>
                  <ModelGroupSelectedMembers
                    locale={locale}
                    foldedMembers={props.foldedMembers}
                    disabledItemCount={props.disabledItemCount}
                    invalidItemCount={props.invalidItemCount}
                    unavailableItemCount={props.unavailableItemCount}
                    removeInvalidItems={props.removeInvalidItems}
                    removeUnavailableItems={props.removeUnavailableItems}
                    removeDisabledMembers={props.removeDisabledMembers}
                    clearMembers={props.clearMembers}
                    setAllMembersEnabled={props.setAllMembersEnabled}
                    memberStatusFilter={props.memberStatusFilter}
                    setMemberStatusFilter={props.setMemberStatusFilter}
                    visibleFoldedMembers={props.visibleFoldedMembers}
                    draggingIndex={props.draggingIndex}
                    toggleFoldedMember={props.toggleFoldedMember}
                    removeFoldedMember={props.removeFoldedMember}
                    setDraggingIndex={props.setDraggingIndex}
                    moveFoldedMember={props.moveFoldedMember}
                  />
                </div>
              </>
            ) : null}
          </div>

          <div className="sticky bottom-0 z-10 -mx-1 mt-4 shrink-0 border-t bg-background/95 px-1 pt-4 pb-1 backdrop-blur supports-[backdrop-filter]:bg-background/85">
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                variant="outline"
                type="button"
                onClick={() => setDialogOpen(false)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button type="submit" disabled={form.protocols.length === 0}>
                {editingId
                  ? locale === "zh-CN"
                    ? "保存模型组"
                    : "Save group"
                  : locale === "zh-CN"
                    ? "创建模型组"
                    : "Create group"}
              </Button>
            </div>
          </div>
        </form>
      </AppDialogContent>
    </Dialog>
  );
}

/** Render the confirmation dialog for deleting a model group. */
export function DeleteGroupDialog({
  deleteTarget,
  locale,
  busyId,
  setDeleteTarget,
  remove,
}: DeleteGroupDialogProps) {
  return (
    <Dialog
      open={Boolean(deleteTarget)}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
    >
      <AppDialogContent
        className="max-w-lg"
        title={locale === "zh-CN" ? "确认删除模型组" : "Delete group"}
        description={
          locale === "zh-CN"
            ? "删除后，该模型组名称将不再参与路由匹配。"
            : "This group will no longer participate in routing."
        }
      >
        <div className="grid gap-5 overflow-y-auto pr-1">
          <div className="rounded-md border bg-muted/30 p-4">
            <strong>{deleteTarget?.name}</strong>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <Button
              variant="outline"
              type="button"
              onClick={() => setDeleteTarget(null)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              variant="destructive"
              type="button"
              onClick={() => deleteTarget && void remove(deleteTarget)}
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
