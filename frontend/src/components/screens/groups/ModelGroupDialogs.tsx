import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import { HeaderRows } from "@/components/ruleEditors/HeaderRows";
import { ParamRuleRows } from "@/components/ruleEditors/ParamRuleRows";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import type { ModelGroup } from "@/lib/api/groups";
import type { FormState, MemberStatusFilter } from "./groupTypes";
import { ModelGroupCandidateList } from "./ModelGroupCandidateList";
import { ModelGroupCandidateToolbar } from "./ModelGroupCandidateToolbar";
import { ModelGroupExcludedMembers } from "./ModelGroupExcludedMembers";
import { ModelGroupSelectedMembers } from "./ModelGroupSelectedMembers";
import { ModelGroupSettings } from "./ModelGroupSettings";
import { MultimodalFallbackGroups } from "./MultimodalFallbackGroups";
import type { GroupCandidates } from "./useGroupCandidates";
import type { GroupMembers } from "./useGroupMembers";

interface GroupEditorDialogProps {
  dialogOpen: boolean;
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  editingId: string | null;
  locale: "zh-CN" | "en-US";
  submit: FormEventHandler<HTMLFormElement>;
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  routeTargetOptions: ModelGroup[];
  members: GroupMembers;
  candidates: GroupCandidates;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
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
    candidates,
  } = props;

  return (
    <>
      <Sheet open={dialogOpen} onOpenChange={setDialogOpen}>
        <SheetContent className="flex flex-col gap-0 sm:max-w-[480px]">
          <SheetHeader>
            <SheetTitle>
              {editingId
                ? locale === "zh-CN"
                  ? "编辑模型组"
                  : "Edit model group"
                : locale === "zh-CN"
                  ? "新建模型组"
                  : "Create model group"}
            </SheetTitle>
            {editingId && form.name.trim() ? (
              <SheetDescription className="truncate font-mono">
                {form.name.trim()}
              </SheetDescription>
            ) : null}
          </SheetHeader>
          <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
            <Tabs
              defaultValue="routing"
              className="flex min-h-0 flex-1 flex-col gap-0"
            >
              <div className="shrink-0 border-b border-border/50 px-6">
                <TabsList className="h-auto w-full justify-start gap-4 rounded-none bg-transparent p-0">
                  <TabsTrigger
                    value="routing"
                    className="h-9 rounded-none border-b-2 border-transparent px-0 text-[13px] font-medium text-muted-foreground shadow-none data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
                  >
                    {locale === "zh-CN" ? "路由与成员" : "Routing & members"}
                  </TabsTrigger>
                  <TabsTrigger
                    value="advanced"
                    className="h-9 rounded-none border-b-2 border-transparent px-0 text-[13px] font-medium text-muted-foreground shadow-none data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
                  >
                    {locale === "zh-CN" ? "高级规则" : "Advanced rules"}
                  </TabsTrigger>
                </TabsList>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                <TabsContent value="routing" className="mt-0 space-y-5">
                  <ModelGroupSettings
                    locale={locale}
                    form={form}
                    setForm={setForm}
                    routeTargetOptions={props.routeTargetOptions}
                  />
                  {!form.route_group_id ? (
                    <ModelGroupSelectedMembers
                      onAddSources={() => candidates.setSheetOpen(true)}
                      locale={locale}
                      strategy={form.strategy}
                      members={props.members}
                      memberStatusFilter={props.memberStatusFilter}
                      setMemberStatusFilter={props.setMemberStatusFilter}
                    />
                  ) : null}
                  {!form.route_group_id ? (
                    <ModelGroupExcludedMembers
                      locale={locale}
                      excludedMembers={props.members.excludedMembers}
                      restoreExcludedMember={
                        props.members.restoreExcludedMember
                      }
                    />
                  ) : null}
                </TabsContent>
                <TabsContent value="advanced" className="mt-0 space-y-5">
                  <HeaderRows
                    title={locale === "zh-CN" ? "请求头" : "Request headers"}
                    headers={form.headers}
                    locale={locale}
                    onAdd={() =>
                      setForm((current) => ({
                        ...current,
                        headers: [
                          ...current.headers,
                          { key: "", value: "", action: "override" },
                        ],
                      }))
                    }
                    onUpdate={(index, patch) =>
                      setForm((current) => ({
                        ...current,
                        headers: current.headers.map((header, currentIndex) =>
                          currentIndex === index
                            ? { ...header, ...patch }
                            : header,
                        ),
                      }))
                    }
                    onRemove={(index) =>
                      setForm((current) => ({
                        ...current,
                        headers:
                          current.headers.length > 1
                            ? current.headers.filter(
                                (_, currentIndex) => currentIndex !== index,
                              )
                            : current.headers,
                      }))
                    }
                  />
                  <ParamRuleRows
                    title={locale === "zh-CN" ? "参数规则" : "Parameter rules"}
                    locale={locale}
                    rules={form.param_override}
                    onChange={(rules) =>
                      setForm((current) => ({
                        ...current,
                        param_override: rules,
                      }))
                    }
                  />
                  {!form.route_group_id ? (
                    <MultimodalFallbackGroups
                      locale={locale}
                      options={props.routeTargetOptions}
                      selectedIds={form.fallback_group_ids}
                      onChange={(ids) =>
                        setForm((current) => ({
                          ...current,
                          fallback_group_ids: ids,
                        }))
                      }
                    />
                  ) : null}
                </TabsContent>
              </div>
            </Tabs>
            <SheetFooter className="justify-between gap-3">
              <span className="text-xs text-muted-foreground">
                {form.route_group_id
                  ? locale === "zh-CN"
                    ? "别名模型组"
                    : "Alias group"
                  : locale === "zh-CN"
                    ? `已选 ${props.members.foldedMembers.length} 个模型`
                    : `${props.members.foldedMembers.length} selected models`}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  type="button"
                  onClick={() => setDialogOpen(false)}
                >
                  {locale === "zh-CN" ? "取消" : "Cancel"}
                </Button>
                <Button type="submit" size="sm">
                  {editingId
                    ? locale === "zh-CN"
                      ? "保存"
                      : "Save"
                    : locale === "zh-CN"
                      ? "创建"
                      : "Create"}
                </Button>
              </div>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>
      <Sheet open={candidates.sheetOpen} onOpenChange={candidates.setSheetOpen}>
        <SheetContent
          side="right"
          showOverlay={false}
          className="flex flex-col gap-0 sm:right-[480px] sm:max-w-[480px]"
        >
          <SheetHeader>
            <SheetTitle>
              {locale === "zh-CN" ? "添加渠道成员" : "Add channel members"}
            </SheetTitle>
          </SheetHeader>
          <section
            aria-label={locale === "zh-CN" ? "可选模型" : "Available models"}
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
          >
            <ModelGroupCandidateToolbar
              locale={locale}
              candidateSearch={candidates.candidateSearch}
              changeCandidateSearch={candidates.setCandidateSearch}
              refetchCandidates={candidates.refetch}
              isFetchingCandidates={candidates.isFetching}
              candidateRegex={candidates.candidateRegex}
              onCandidateRegexChange={candidates.setCandidateRegex}
              onAddAllCandidates={candidates.addAllVisibleCandidates}
              visibleCandidateCount={candidates.visibleCandidateCount}
            />
            <ModelGroupCandidateList
              locale={locale}
              groupedCandidates={candidates.groupedCandidates}
              expandedChannels={candidates.expandedChannels}
              existingItemKeys={candidates.existingItemKeys}
              toggleChannel={candidates.toggleChannel}
              addCandidate={candidates.addCandidate}
              candidateIsError={candidates.isError}
              candidateListError={candidates.error}
            />
          </section>
          <SheetFooter>
            <Button
              type="button"
              size="sm"
              onClick={() => candidates.setSheetOpen(false)}
            >
              {locale === "zh-CN" ? "完成" : "Done"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
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
    <ConfirmDeleteDialog
      open={Boolean(deleteTarget)}
      locale={locale}
      title={locale === "zh-CN" ? "删除模型组" : "Delete model group"}
      description={
        locale === "zh-CN"
          ? `确定删除模型组 ${deleteTarget?.name ?? ""}？仍存在于渠道中的模型可能会在下次同步时重新加入；若仅需停用，请关闭对应渠道模型。`
          : `Delete model group "${deleteTarget?.name ?? ""}"? Channels may sync its models back; disable them in the channel to stop calls.`
      }
      isBusy={Boolean(deleteTarget) && busyId === deleteTarget?.id}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
      onConfirm={() => deleteTarget && void remove(deleteTarget)}
    />
  );
}
