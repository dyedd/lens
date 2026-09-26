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
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import type { ModelGroup, ModelGroupCandidateItem } from "@/lib/api/groups";
import type {
  CandidateChannelGroup,
  CandidateSearchMode,
  ChannelMemberGroup,
  FoldedMember,
  FormState,
  MemberStatusFilter,
} from "./groupTypes";
import { ModelGroupCandidateList } from "./ModelGroupCandidateList";
import { ModelGroupCandidateToolbar } from "./ModelGroupCandidateToolbar";
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
                    ? "添加上游来源"
                    : "Add upstream sources"
                  : editingId
                    ? locale === "zh-CN"
                      ? "编辑模型组"
                      : "Edit group"
                    : locale === "zh-CN"
                      ? "新建模型组"
                      : "Create group"}
              </SheetTitle>
              <SheetDescription className="mt-1 truncate text-xs">
                {isBinding
                  ? locale === "zh-CN"
                    ? "选择渠道中的模型，加入当前模型组。"
                    : "Choose models from channels to add to this group."
                  : locale === "zh-CN"
                    ? "对外模型、上游来源与请求规则"
                    : "Model name, upstream sources and request rules"}
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
                form={form}
                candidateSearchMode={props.candidateSearchMode}
                changeCandidateSearchMode={props.changeCandidateSearchMode}
                candidateSearch={props.candidateSearch}
                changeCandidateSearch={props.changeCandidateSearch}
                addMatchedItems={props.addMatchedItems}
                candidateRegexInvalid={props.candidateRegexInvalid}
                filteredCandidateCount={props.filteredCandidates.length}
                refetchCandidates={props.refetchCandidates}
                isFetchingCandidates={props.isFetchingCandidates}
                clearSavedFilter={props.clearSavedFilter}
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
                routeTargetOptions={props.routeTargetOptions}
                changeRouteTarget={props.changeRouteTarget}
              />
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
                  ? "路由组"
                  : "Routing group"
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
                  <Button type="submit" size="sm">
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
    <Dialog
      open={Boolean(deleteTarget)}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
    >
      <AppDialogContent
        className="max-w-lg"
        showCloseButton={false}
        title={locale === "zh-CN" ? "确认删除模型组" : "Delete group"}
        description={
          locale === "zh-CN"
            ? `将删除模型组「${deleteTarget?.name ?? ""}」。删除后，该模型组名称将不再参与路由匹配。`
            : `Delete group "${deleteTarget?.name ?? ""}". This group will no longer participate in routing.`
        }
        footer={
          <>
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => setDeleteTarget(null)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
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
          </>
        }
      />
    </Dialog>
  );
}
