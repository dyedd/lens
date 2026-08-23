"use client";

import { useState } from "react";
import { RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import type {
  ModelGroup,
  ModelGroupEnsureFromSiteResponse,
  ModelGroupEnsureResultItem,
} from "@/lib/api";
import type { Locale } from "./channelShared";
import {
  canSubmitModelGroupEnsureItem,
  executionModelGroups,
  modelGroupEnsureResultKey,
  selectableModelGroupsForEnsureItem,
} from "./modelGroupEnsure";
import { nextCreateModelGroupName } from "./modelGroupEnsureDialogUtils";
import { ModelGroupEnsureTable } from "./ModelGroupEnsureTable";

type Props = {
  open: boolean;
  locale: Locale;
  result: ModelGroupEnsureFromSiteResponse | null;
  modelGroups: ModelGroup[];
  selectedItemKeys: string[];
  isConfirming: boolean;
  onOpenChange: (open: boolean) => void;
  onToggleItem: (item: ModelGroupEnsureResultItem) => void;
  onTargetGroupChange: (
    item: ModelGroupEnsureResultItem,
    groupName: string,
  ) => void;
  onConfirm: (groupNameOverrides?: Record<string, string>) => void;
};

/** Renders the preview and selection flow for adding models to groups. */
export function ModelGroupEnsureDialog({
  open,
  locale,
  result,
  modelGroups,
  selectedItemKeys,
  isConfirming,
  onOpenChange,
  onToggleItem,
  onTargetGroupChange,
  onConfirm,
}: Props) {
  const [createGroupNameDrafts, setCreateGroupNameDrafts] = useState<
    Record<string, string>
  >({});
  const [createGroupNameErrors, setCreateGroupNameErrors] = useState<
    Record<string, string>
  >({});
  const [openTargetGroupKey, setOpenTargetGroupKey] = useState<string | null>(
    null,
  );
  function getCreateGroupName(
    item: ModelGroupEnsureResultItem,
    key: string,
    targetGroupIsSelectable: boolean,
  ) {
    return (
      createGroupNameDrafts[key] ??
      (targetGroupIsSelectable
        ? item.group_name
        : nextCreateModelGroupName(item.model_name, modelGroups))
    );
  }

  function clearCreateGroupNameError(key: string) {
    setCreateGroupNameErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function commitCreateGroupName(item: ModelGroupEnsureResultItem) {
    const key = modelGroupEnsureResultKey(item);
    const nextGroupName = createGroupNameDrafts[key]?.trim();
    if (!nextGroupName) return;
    const matchedGroup = executionModelGroups(modelGroups).find(
      (group) => group.name === nextGroupName,
    );
    if (matchedGroup) {
      setCreateGroupNameErrors((current) => ({
        ...current,
        [key]:
          locale === "zh-CN"
            ? "同名组已存在，请使用其他名称。"
            : "Name already exists, choose another.",
      }));
      return;
    }
    clearCreateGroupNameError(key);
    setCreateGroupNameDrafts((current) => ({
      ...current,
      [key]: nextGroupName,
    }));
    if (nextGroupName !== item.group_name) {
      onTargetGroupChange(item, nextGroupName);
    }
  }

  function selectCreateTarget(item: ModelGroupEnsureResultItem, key: string) {
    const nextGroupName = nextCreateModelGroupName(
      item.model_name,
      modelGroups,
    );
    clearCreateGroupNameError(key);
    setCreateGroupNameDrafts((current) => ({
      ...current,
      [key]: nextGroupName,
    }));
    setOpenTargetGroupKey(null);
    onTargetGroupChange(item, nextGroupName);
  }

  function selectExistingTarget(
    item: ModelGroupEnsureResultItem,
    key: string,
    groupName: string,
  ) {
    clearCreateGroupNameError(key);
    setCreateGroupNameDrafts((current) => ({ ...current, [key]: groupName }));
    setOpenTargetGroupKey(null);
    onTargetGroupChange(item, groupName);
  }

  function confirmWithDrafts() {
    const overrides: Record<string, string> = {};
    for (const [key, value] of Object.entries(createGroupNameDrafts)) {
      const groupName = value.trim();
      if (groupName) overrides[key] = groupName;
    }
    onConfirm(overrides);
  }

  const hasInvalidSelectedCreateName =
    result?.items.some((item) => {
      const key = modelGroupEnsureResultKey(item);
      if (
        !selectedItemKeys.includes(key) ||
        !canSubmitModelGroupEnsureItem(item)
      ) {
        return false;
      }
      const targetModelGroups = selectableModelGroupsForEnsureItem(
        item,
        modelGroups,
      );
      const targetGroupExists = targetModelGroups.some(
        (group) => group.name === item.group_name,
      );
      if (targetGroupExists) return false;
      const createName = getCreateGroupName(
        item,
        key,
        targetGroupExists,
      ).trim();
      return (
        !createName ||
        executionModelGroups(modelGroups).some(
          (group) => group.name === createName,
        )
      );
    }) ?? false;

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && isConfirming) return;
        onOpenChange(nextOpen);
      }}
    >
      {open && result ? (
        <AppDialogContent
          className="max-w-5xl"
          title={
            locale === "zh-CN"
              ? "确认模型组处理"
              : "Confirm model-group changes"
          }
        >
          <div className="grid gap-4 pt-1">
            <div className="flex flex-wrap gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
              <span>{`${locale === "zh-CN" ? "新建" : "Create"} ${result.created_count}`}</span>
              <span>{`${locale === "zh-CN" ? "加入" : "Update"} ${result.updated_count}`}</span>
              <span>{`${locale === "zh-CN" ? "已存在" : "Unchanged"} ${result.unchanged_count}`}</span>
              <span>{`${locale === "zh-CN" ? "跳过" : "Skipped"} ${result.skipped_count}`}</span>
            </div>
            <ModelGroupEnsureTable
              items={result.items}
              modelGroups={modelGroups}
              selectedItemKeys={selectedItemKeys}
              createGroupNameDrafts={createGroupNameDrafts}
              createGroupNameErrors={createGroupNameErrors}
              openTargetGroupKey={openTargetGroupKey}
              isConfirming={isConfirming}
              locale={locale}
              getCreateGroupName={getCreateGroupName}
              onToggleItem={onToggleItem}
              onOpenTargetGroupChange={setOpenTargetGroupKey}
              onSelectCreate={selectCreateTarget}
              onSelectExisting={selectExistingTarget}
              onDraftChange={(key, value) => {
                clearCreateGroupNameError(key);
                setCreateGroupNameDrafts((current) => ({
                  ...current,
                  [key]: value,
                }));
              }}
              onCommitDraft={commitCreateGroupName}
            />
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                onClick={confirmWithDrafts}
                disabled={isConfirming || hasInvalidSelectedCreateName}
              >
                <RefreshCcw
                  data-icon="inline-start"
                  className={isConfirming ? "animate-spin" : undefined}
                />
                {locale === "zh-CN" ? "保存渠道" : "Save channel"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}
