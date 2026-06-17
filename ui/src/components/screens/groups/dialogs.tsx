"use client";

import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import {
  AlertCircle,
  ChevronDown,
  RefreshCcw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Combobox, ComboboxOption } from "@/components/ui/combobox";
import { ProtocolMultiSelect } from "@/components/ui/protocol-multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ProtocolKind,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  CandidateRow,
  EditablePriceRow,
  FoldedMemberRow,
  StrategyToggle,
} from "./components";
import {
  modelFoldKey,
  protocolOptions,
  type CandidateChannelGroup,
  type CandidateSearchMode,
  type FoldedMember,
  type FormState,
} from "./shared";

export function GroupEditorDialog({
  dialogOpen,
  setDialogOpen,
  editingId,
  locale,
  submit,
  form,
  setForm,
  toggleProtocol,
  routeTargetOptions,
  changeRouteTarget,
  candidateSearchMode,
  changeCandidateSearchMode,
  candidateSearch,
  changeCandidateSearch,
  addMatchedItems,
  candidateRegexInvalid,
  filteredCandidates,
  refetchCandidates,
  isFetchingCandidates,
  applySavedFilter,
  clearSavedFilter,
  groupedCandidates,
  expandedChannels,
  toggleChannel,
  foldedMembers,
  addCandidate,
  sitesIsError,
  candidateIsError,
  candidateListError,
  invalidSelectedMemberCount,
  removeInvalidItems,
  setAllMembersEnabled,
  showEnabledOnly,
  setShowEnabledOnly,
  visibleFoldedMembers,
  draggingIndex,
  toggleFoldedMember,
  removeFoldedMember,
  setDraggingIndex,
  moveFoldedMember,
}: {
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
  sitesIsError: boolean;
  candidateIsError: boolean;
  candidateListError: unknown;
  invalidSelectedMemberCount: number;
  removeInvalidItems: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  showEnabledOnly: boolean;
  setShowEnabledOnly: Dispatch<SetStateAction<boolean>>;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  draggingIndex: number | null;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  setDraggingIndex: Dispatch<SetStateAction<number | null>>;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
}) {
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
            <section className="grid gap-4">
              <div className="text-base font-semibold text-foreground">
                {locale === "zh-CN" ? "基本信息" : "Group settings"}
              </div>
              <FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "协议" : "External Protocols"}
                  </FieldLabel>
                  <ProtocolMultiSelect
                    value={form.protocols}
                    onChange={(next) => {
                      const changedProtocols = protocolOptions(locale)
                        .map((option) => option.value)
                        .filter(
                          (protocol) =>
                            form.protocols.includes(protocol) !==
                            next.includes(protocol),
                        );
                      if (changedProtocols.length === 1) {
                        toggleProtocol(changedProtocols[0]);
                        return;
                      }
                      setForm((current) => ({
                        ...current,
                        protocols: next,
                      }));
                    }}
                    locale={locale}
                    invalid={form.protocols.length === 0}
                  />
                  {form.protocols.length === 0 ? (
                    <p className="text-sm text-destructive">
                      {locale === "zh-CN"
                        ? "至少需要选择一项协议。"
                        : "At least one protocol is required."}
                    </p>
                  ) : null}
                </Field>
                <Field>
                  <FieldLabel htmlFor="group-name">
                    {locale === "zh-CN" ? "模型组名称" : "Group name"}
                  </FieldLabel>
                  <Input
                    id="group-name"
                    placeholder={
                      locale === "zh-CN" ? "输入模型组名称" : "Enter group name"
                    }
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="group-route-target">
                    {locale === "zh-CN"
                      ? "路由目标模型组"
                      : "Route target group"}
                  </FieldLabel>
                  <Combobox
                    id="group-route-target"
                    className="w-full"
                    value={form.route_group_id}
                    onChange={(event) => changeRouteTarget(event.target.value)}
                  >
                    <ComboboxOption value="">
                      {locale === "zh-CN"
                        ? "不启用模型组路由"
                        : "No group routing"}
                    </ComboboxOption>
                    {routeTargetOptions.map((group) => (
                      <ComboboxOption key={group.id} value={group.id}>
                        {group.name}
                      </ComboboxOption>
                    ))}
                  </Combobox>
                </Field>
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "模型组策略" : "Group strategy"}
                  </FieldLabel>
                  <StrategyToggle
                    value={form.strategy}
                    locale={locale}
                    disabled={Boolean(form.route_group_id)}
                    onChange={(value) =>
                      setForm((current) => ({ ...current, strategy: value }))
                    }
                  />
                </Field>
              </FieldGroup>
            </section>

            {!form.route_group_id ? (
              <>
                <Separator />

                <section className="grid gap-4">
                  <div className="text-base font-semibold text-foreground">
                    {locale === "zh-CN" ? "价格" : "Pricing"}
                  </div>
                  <div className="grid gap-3 xl:grid-cols-2">
                    <EditablePriceRow
                      locale={locale}
                      primaryLabel="input"
                      primaryValue={form.input_price_per_million}
                      secondaryLabel="cache_read"
                      secondaryValue={form.cache_read_price_per_million}
                      onPrimaryChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          input_price_per_million: value,
                        }))
                      }
                      onSecondaryChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          cache_read_price_per_million: value,
                        }))
                      }
                    />
                    <EditablePriceRow
                      locale={locale}
                      primaryLabel="output"
                      primaryValue={form.output_price_per_million}
                      secondaryLabel="cache_write"
                      secondaryValue={form.cache_write_price_per_million}
                      onPrimaryChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          output_price_per_million: value,
                        }))
                      }
                      onSecondaryChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          cache_write_price_per_million: value,
                        }))
                      }
                    />
                  </div>
                </section>

                <Separator />

                <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                  <section className="flex flex-col rounded-lg bg-muted/10">
                    <div className="grid gap-3 py-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                      <div className="grid min-w-0 gap-2 sm:grid-cols-[128px_minmax(0,1fr)]">
                        <Select
                          value={candidateSearchMode}
                          onValueChange={(value) =>
                            changeCandidateSearchMode(
                              value as CandidateSearchMode,
                            )
                          }
                        >
                          <SelectTrigger className="h-7 w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="contains">
                              {locale === "zh-CN" ? "包含" : "Contains"}
                            </SelectItem>
                            <SelectItem value="regex">
                              {locale === "zh-CN" ? "正则" : "Regex"}
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3">
                          <Search size={14} className="text-muted-foreground" />
                          <Input
                            className="min-w-0 flex-1 border-0 bg-transparent px-0 py-0 text-sm shadow-none focus-visible:ring-0"
                            value={candidateSearch}
                            onChange={(e) =>
                              changeCandidateSearch(e.target.value)
                            }
                            placeholder={
                              candidateSearchMode === "regex"
                                ? locale === "zh-CN"
                                  ? "输入正则表达式"
                                  : "Enter regular expression"
                                : locale === "zh-CN"
                                  ? "输入包含条件"
                                  : "Enter contains filter"
                            }
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={addMatchedItems}
                          disabled={
                            form.protocols.length === 0 ||
                            candidateRegexInvalid ||
                            (!filteredCandidates.length &&
                              !candidateSearch.trim())
                          }
                        >
                          <Sparkles size={13} />
                          {candidateSearch.trim()
                            ? locale === "zh-CN"
                              ? `加入并保存筛选 ${filteredCandidates.length}`
                              : `Add and save filter ${filteredCandidates.length}`
                            : locale === "zh-CN"
                              ? `加入全部 ${filteredCandidates.length}`
                              : `Add all ${filteredCandidates.length}`}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void refetchCandidates()}
                          disabled={
                            isFetchingCandidates || form.protocols.length === 0
                          }
                        >
                          <RefreshCcw size={13} />
                          {locale === "zh-CN" ? "刷新列表" : "Refresh"}
                        </Button>
                      </div>
                    </div>
                    {candidateRegexInvalid ? (
                      <div className="px-2 text-sm text-destructive">
                        {locale === "zh-CN"
                          ? "正则表达式无效"
                          : "Invalid regex"}
                      </div>
                    ) : null}
                    {form.sync_filter_mode && form.sync_filter_query ? (
                      <div className="mx-2 mb-2 flex flex-col gap-2 rounded-md border bg-muted/20 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0 text-sm text-muted-foreground">
                          <span className="text-foreground">
                            {locale === "zh-CN" ? "已保存筛选" : "Saved filter"}
                          </span>
                          <span className="mx-2">·</span>
                          <span>
                            {form.sync_filter_mode === "regex"
                              ? locale === "zh-CN"
                                ? "正则"
                                : "Regex"
                              : locale === "zh-CN"
                                ? "包含"
                                : "Contains"}
                          </span>
                          <span className="mx-2">·</span>
                          <span className="break-all">
                            {form.sync_filter_query}
                          </span>
                        </div>
                        <div className="flex shrink-0 flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => void applySavedFilter()}
                          >
                            <RefreshCcw data-icon="inline-start" />
                            {locale === "zh-CN"
                              ? "按规则更新"
                              : "Update by rule"}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="text-muted-foreground"
                            onClick={clearSavedFilter}
                          >
                            <X data-icon="inline-start" />
                            {locale === "zh-CN" ? "清除规则" : "Clear rule"}
                          </Button>
                        </div>
                      </div>
                    ) : null}

                    <div className="px-2 pb-2">
                      <div className="flex flex-col">
                        {groupedCandidates.map((channelGroup) => {
                          const channelKey = channelGroup.key;
                          const isOpen = expandedChannels.includes(channelKey);
                          return (
                            <div
                              key={channelKey}
                              className="border-b last:border-b-0"
                            >
                              <Button
                                type="button"
                                variant="ghost"
                                className="h-auto min-h-11 w-full justify-start gap-3 rounded-none px-3 py-2 text-left hover:bg-muted"
                                onClick={() => toggleChannel(channelKey)}
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="truncate text-sm font-medium text-foreground">
                                    {channelGroup.channel_name}
                                  </div>
                                </div>
                                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                  {channelGroup.candidates.length}
                                </span>
                                <ChevronDown
                                  size={15}
                                  className={cn(
                                    "text-muted-foreground transition-transform",
                                    isOpen && "rotate-180",
                                  )}
                                />
                              </Button>
                              {isOpen ? (
                                <div className="flex flex-col gap-0.5 px-3 pb-2 pt-1">
                                  <Separator className="mb-1" />
                                  {channelGroup.candidates.map((candidate) => {
                                    const fk = modelFoldKey(
                                      candidate.protocol_config_id,
                                      candidate.credential_id,
                                      candidate.model_name,
                                    );
                                    const isActive = foldedMembers.some(
                                      (m) => m.key === fk,
                                    );
                                    return (
                                      <CandidateRow
                                        key={`${candidate.protocol_config_id}-${candidate.credential_id}-${candidate.model_name}`}
                                        candidate={candidate}
                                        active={isActive}
                                        selectedProtocols={form.protocols}
                                        locale={locale}
                                        onClick={() => addCandidate(candidate)}
                                      />
                                    );
                                  })}
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                        {sitesIsError || candidateIsError ? (
                          <Alert variant="destructive" className="my-2">
                            <AlertCircle />
                            <AlertTitle>
                              {candidateIsError
                                ? locale === "zh-CN"
                                  ? "候选模型加载失败"
                                  : "Failed to load candidates"
                                : locale === "zh-CN"
                                  ? "渠道加载失败"
                                  : "Failed to load channels"}
                            </AlertTitle>
                            <AlertDescription>
                              {candidateListError instanceof Error
                                ? candidateListError.message
                                : locale === "zh-CN"
                                  ? "无法读取候选模型"
                                  : "Unable to read candidates"}
                            </AlertDescription>
                          </Alert>
                        ) : !groupedCandidates.length ? (
                          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
                            {form.protocols.length === 0
                              ? locale === "zh-CN"
                                ? "请先在上方选择对外协议以加载候选节点。"
                                : "Select external protocols above to load candidates."
                              : locale === "zh-CN"
                                ? "暂无可选模型"
                                : "No candidates found"}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </section>

                  <section className="flex flex-col rounded-lg bg-muted/10">
                    <div className="flex flex-col items-start justify-between gap-3 px-2 py-1 sm:flex-row sm:items-center">
                      <div className="text-sm font-medium text-foreground">
                        {locale === "zh-CN" ? "已选模型" : "Selected models"}
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {invalidSelectedMemberCount > 0 ? (
                          <Button
                            type="button"
                            variant="outline"
                            className="text-destructive"
                            onClick={removeInvalidItems}
                          >
                            <AlertCircle size={13} />
                            {locale === "zh-CN"
                              ? "一键移除失效节点"
                              : "Remove invalid items"}
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          variant="outline"
                          className="text-muted-foreground"
                          onClick={() => setAllMembersEnabled(true)}
                        >
                          {locale === "zh-CN" ? "全开" : "Enable all"}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          className="text-muted-foreground"
                          onClick={() => setAllMembersEnabled(false)}
                        >
                          {locale === "zh-CN" ? "全关" : "Disable all"}
                        </Button>
                        <Button
                          type="button"
                          variant={showEnabledOnly ? "default" : "outline"}
                          className={cn(
                            !showEnabledOnly && "text-muted-foreground",
                          )}
                          onClick={() =>
                            setShowEnabledOnly((current) => !current)
                          }
                        >
                          {locale === "zh-CN" ? "仅看启用" : "Enabled only"}
                        </Button>
                        <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                          {visibleFoldedMembers.length}/{foldedMembers.length}
                        </span>
                      </div>
                    </div>
                    <div className="px-2 pb-2 pt-1">
                      <div className="flex flex-col gap-1.5">
                        {visibleFoldedMembers.length ? (
                          visibleFoldedMembers.map(({ member, index }) => (
                            <FoldedMemberRow
                              key={member.key}
                              member={member}
                              index={index}
                              dragging={draggingIndex === index}
                              busy={false}
                              onToggle={() =>
                                toggleFoldedMember(member.key, !member.enabled)
                              }
                              onRemove={() => removeFoldedMember(member.key)}
                              onDragStart={() => setDraggingIndex(index)}
                              onDragEnter={() => {
                                if (
                                  draggingIndex === null ||
                                  draggingIndex === index
                                )
                                  return;
                                moveFoldedMember(draggingIndex, index);
                                setDraggingIndex(index);
                              }}
                              onDragEnd={() => setDraggingIndex(null)}
                              locale={locale}
                            />
                          ))
                        ) : (
                          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
                            {locale === "zh-CN"
                              ? "当前筛选下没有成员"
                              : "No members under current filter"}
                          </p>
                        )}
                      </div>
                    </div>
                  </section>
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

export function DeleteGroupDialog({
  deleteTarget,
  locale,
  busyId,
  setDeleteTarget,
  remove,
}: {
  deleteTarget: ModelGroup | null;
  locale: "zh-CN" | "en-US";
  busyId: string | null;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
  remove: (item: ModelGroup) => void;
}) {
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
