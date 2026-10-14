import { ArrowLeft, SlidersHorizontal } from "lucide-react";
import {
  type Dispatch,
  type FormEventHandler,
  type SetStateAction,
  useState,
} from "react";
import { HeaderRows } from "@/components/ruleEditors/HeaderRows";
import { ParamRuleRows } from "@/components/ruleEditors/ParamRuleRows";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
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
import type { ModelGroup, ModelGroupCandidateItem } from "@/lib/api/groups";
import type { RegexRule } from "@/lib/api/regexRules";
import type {
  CandidateChannelGroup,
  ChannelMemberGroup,
  FoldedMember,
  FormState,
  MemberStatusFilter,
} from "./groupTypes";
import { ModelGroupCandidateList } from "./ModelGroupCandidateList";
import { ModelGroupCandidateToolbar } from "./ModelGroupCandidateToolbar";
import { ModelGroupExcludedMembers } from "./ModelGroupExcludedMembers";
import { ModelGroupMatchRules } from "./ModelGroupMatchRules";
import { ModelGroupSelectedMembers } from "./ModelGroupSelectedMembers";
import { ModelGroupSettings } from "./ModelGroupSettings";
import { MultimodalFallbackGroups } from "./MultimodalFallbackGroups";
import { modelGroupItemKey } from "./modelGroupFormatting";

interface GroupEditorDialogProps {
  dialogOpen: boolean;
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  editingId: string | null;
  locale: "zh-CN" | "en-US";
  submit: FormEventHandler<HTMLFormElement>;
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  changeName: (name: string) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
  changeMatchRules: (
    rules: Partial<Pick<FormState, "match_models" | "match_rule_ids">>,
  ) => void;
  invalidMatchRules: RegexRule[];
  hasDeletedMatchRules: boolean;
  ruleMatchModelCount: number;
  ruleMatchSourceCount: number;
  memberChange: { added: number; removed: number } | null;
  excludedMembers: FoldedMember[];
  restoreExcludedMember: (foldKey: string) => void;
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
  groupedCandidates: CandidateChannelGroup[];
  expandedChannels: string[];
  toggleChannel: (channelId: string) => void;
  foldedMembers: FoldedMember[];
  addCandidate: (candidate: ModelGroupCandidateItem) => void;
  candidateIsError: boolean;
  candidateListError: unknown;
  disabledItemCount: number;
  invalidItemCount: number;
  removeInvalidItems: () => void;
  removeDisabledMembers: () => void;
  clearMembers: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  visibleChannelGroups: ChannelMemberGroup[];
  toggleChannelMembers: (channelKey: string, enabled: boolean) => void;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  moveChannelGroup: (fromIndex: number, toIndex: number) => void;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
  moveFoldedMemberWithinChannel: (
    channelKey: string,
    fromIndex: number,
    toIndex: number,
  ) => void;
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
  const [isBinding, setIsBinding] = useState(false);
  const existingItemKeys = new Set(
    form.items.map((item) => modelGroupItemKey(item)),
  );

  return (
    <Sheet open={dialogOpen} onOpenChange={setDialogOpen}>
      <SheetContent className="flex flex-col gap-0 sm:max-w-[560px]">
        <SheetHeader className="shrink-0 px-4 py-4 pr-14">
          <div className="flex items-center gap-3">
            {isBinding ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={locale === "zh-CN" ? "返回模型组" : "Back to group"}
                onClick={() => setIsBinding(false)}
              >
                <ArrowLeft />
              </Button>
            ) : null}
            <div className="min-w-0">
              <SheetTitle>
                {isBinding
                  ? locale === "zh-CN"
                    ? "添加渠道成员"
                    : "Add channel members"
                  : editingId
                    ? locale === "zh-CN"
                      ? "编辑模型组"
                      : "Edit model group"
                    : locale === "zh-CN"
                      ? "新建模型组"
                      : "Create model group"}
              </SheetTitle>
              <SheetDescription className="mt-1 truncate text-xs">
                {isBinding
                  ? locale === "zh-CN"
                    ? "选择要添加的渠道成员；手动添加已排除的模型会取消排除。"
                    : "Choose channel members to add. Adding an excluded model lifts its exclusion."
                  : locale === "zh-CN"
                    ? "模型名称、渠道成员和匹配规则"
                    : "Model name, channel members, and match rules"}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>
        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit}>
          {isBinding ? (
            <section
              aria-label={locale === "zh-CN" ? "可选模型" : "Available models"}
              className="mx-6 mb-5 flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border/60"
            >
              <ModelGroupCandidateToolbar
                locale={locale}
                candidateSearch={props.candidateSearch}
                changeCandidateSearch={props.changeCandidateSearch}
                refetchCandidates={props.refetchCandidates}
                isFetchingCandidates={props.isFetchingCandidates}
              />
              <ModelGroupCandidateList
                locale={locale}
                groupedCandidates={props.groupedCandidates}
                expandedChannels={props.expandedChannels}
                existingItemKeys={existingItemKeys}
                toggleChannel={props.toggleChannel}
                addCandidate={props.addCandidate}
                candidateIsError={props.candidateIsError}
                candidateListError={props.candidateListError}
              />
            </section>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6 pb-6">
              <ModelGroupSettings
                locale={locale}
                form={form}
                setForm={setForm}
                changeName={props.changeName}
                routeTargetOptions={props.routeTargetOptions}
                changeRouteTarget={props.changeRouteTarget}
              />
              {!form.route_group_id ? (
                <ModelGroupMatchRules
                  locale={locale}
                  matchModels={form.match_models}
                  matchRuleIds={form.match_rule_ids}
                  invalidMatchRules={props.invalidMatchRules}
                  hasDeletedMatchRules={props.hasDeletedMatchRules}
                  ruleMatchModelCount={props.ruleMatchModelCount}
                  ruleMatchSourceCount={props.ruleMatchSourceCount}
                  newMemberPosition={form.new_member_position}
                  memberChange={props.memberChange}
                  onMatchModelsChange={(matchModels) =>
                    props.changeMatchRules({ match_models: matchModels })
                  }
                  onMatchRuleIdsChange={(matchRuleIds) =>
                    props.changeMatchRules({ match_rule_ids: matchRuleIds })
                  }
                  onNewMemberPositionChange={(position) =>
                    setForm((current) => ({
                      ...current,
                      new_member_position: position,
                    }))
                  }
                />
              ) : null}
              {!form.route_group_id ? (
                <ModelGroupSelectedMembers
                  onAddSources={() => setIsBinding(true)}
                  locale={locale}
                  strategy={form.strategy}
                  foldedMembers={props.foldedMembers}
                  disabledItemCount={props.disabledItemCount}
                  invalidItemCount={props.invalidItemCount}
                  removeInvalidItems={props.removeInvalidItems}
                  removeDisabledMembers={props.removeDisabledMembers}
                  clearMembers={props.clearMembers}
                  setAllMembersEnabled={props.setAllMembersEnabled}
                  memberStatusFilter={props.memberStatusFilter}
                  setMemberStatusFilter={props.setMemberStatusFilter}
                  visibleFoldedMembers={props.visibleFoldedMembers}
                  visibleChannelGroups={props.visibleChannelGroups}
                  toggleChannelMembers={props.toggleChannelMembers}
                  toggleFoldedMember={props.toggleFoldedMember}
                  removeFoldedMember={props.removeFoldedMember}
                  moveChannelGroup={props.moveChannelGroup}
                  moveFoldedMember={props.moveFoldedMember}
                  moveFoldedMemberWithinChannel={
                    props.moveFoldedMemberWithinChannel
                  }
                />
              ) : null}
              {!form.route_group_id ? (
                <ModelGroupExcludedMembers
                  locale={locale}
                  excludedMembers={props.excludedMembers}
                  restoreExcludedMember={props.restoreExcludedMember}
                />
              ) : null}
              <Accordion
                type="single"
                collapsible
                className="border-y border-border/60"
              >
                <AccordionItem value="advanced">
                  <AccordionTrigger className="items-center py-3 text-xs font-normal text-muted-foreground hover:no-underline">
                    <span className="flex items-center gap-2">
                      <SlidersHorizontal className="size-3.5" />
                      {locale === "zh-CN" ? "高级设置" : "Advanced settings"}
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="flex flex-col gap-5">
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
                          headers: current.headers.map(
                            (header, currentIndex) =>
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
                      title={
                        locale === "zh-CN" ? "参数规则" : "Parameter rules"
                      }
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
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          )}
          <SheetFooter className="shrink-0 flex-row items-center justify-between gap-3 px-4 py-4">
            <span className="text-xs text-muted-foreground">
              {form.route_group_id
                ? locale === "zh-CN"
                  ? "别名模型组"
                  : "Alias group"
                : locale === "zh-CN"
                  ? `已选 ${props.foldedMembers.length} 个模型`
                  : `${props.foldedMembers.length} selected models`}
            </span>
            <div className="flex items-center gap-2">
              {isBinding ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setIsBinding(false)}
                >
                  {locale === "zh-CN" ? "完成选择" : "Done"}
                </Button>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => setDialogOpen(false)}
                  >
                    {locale === "zh-CN" ? "取消" : "Cancel"}
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={
                      props.invalidMatchRules.length > 0 ||
                      props.hasDeletedMatchRules
                    }
                  >
                    {editingId
                      ? locale === "zh-CN"
                        ? "保存"
                        : "Save"
                      : locale === "zh-CN"
                        ? "创建"
                        : "Create"}
                  </Button>
                </>
              )}
            </div>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
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
          ? `删除模型组「${deleteTarget?.name ?? ""}」？如果渠道仍提供这些模型，自动同步可能再次加入它们。要停止调用，请先在渠道中停用模型。`
          : `Delete model group "${deleteTarget?.name ?? ""}"? If channels still provide its models, automatic sync may add them again. Disable the models in the channel to stop calls.`
      }
      isBusy={Boolean(deleteTarget) && busyId === deleteTarget?.id}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
      onConfirm={() => deleteTarget && void remove(deleteTarget)}
    />
  );
}
