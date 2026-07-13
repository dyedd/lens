"use client";

import { Badge } from "@/components/ui/Badge";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { cn } from "@/lib/utils";
import type { ModelGroup, ModelGroupEnsureResultItem } from "@/lib/api";
import { compactProtocolLabel, protocolBadgeClassName } from "@/lib/protocols";
import type { Locale } from "./channelShared";
import {
  canSubmitModelGroupEnsureItem,
  modelGroupEnsureReasonLabel,
  modelGroupEnsureResultKey,
  selectableModelGroupsForEnsureItem,
} from "./modelGroupEnsure";
import {
  modelGroupEnsureStatusLabel,
  modelGroupEnsureStatusVariant,
} from "./modelGroupEnsureDialogUtils";
import { ModelGroupTargetSelector } from "./ModelGroupTargetSelector";

type Props = {
  items: ModelGroupEnsureResultItem[];
  modelGroups: ModelGroup[];
  selectedItemKeys: string[];
  createGroupNameDrafts: Record<string, string>;
  createGroupNameErrors: Record<string, string>;
  openTargetGroupKey: string | null;
  isProtocolExtensionAllowed: boolean;
  isConfirming: boolean;
  locale: Locale;
  getCreateGroupName: (
    item: ModelGroupEnsureResultItem,
    key: string,
    targetGroupIsSelectable: boolean,
  ) => string;
  onToggleItem: (item: ModelGroupEnsureResultItem) => void;
  onOpenTargetGroupChange: (key: string | null) => void;
  onSelectCreate: (item: ModelGroupEnsureResultItem, key: string) => void;
  onSelectExisting: (
    item: ModelGroupEnsureResultItem,
    key: string,
    groupName: string,
  ) => void;
  onDraftChange: (key: string, value: string) => void;
  onCommitDraft: (item: ModelGroupEnsureResultItem) => void;
};

/** Renders model-group ensure result rows and target selection controls. */
export function ModelGroupEnsureTable({
  items,
  modelGroups,
  selectedItemKeys,
  createGroupNameDrafts,
  createGroupNameErrors,
  openTargetGroupKey,
  isProtocolExtensionAllowed,
  isConfirming,
  locale,
  getCreateGroupName,
  onToggleItem,
  onOpenTargetGroupChange,
  onSelectCreate,
  onSelectExisting,
  onDraftChange,
  onCommitDraft,
}: Props) {
  return (
    <div className="overflow-hidden rounded-md border">
      <div className="max-h-[52dvh] overflow-y-auto sm:max-h-[420px]">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <span className="sr-only">
                  {locale === "zh-CN" ? "选择" : "Select"}
                </span>
              </TableHead>
              <TableHead className="w-24">
                {locale === "zh-CN" ? "状态" : "Status"}
              </TableHead>
              <TableHead className="w-[280px]">
                {locale === "zh-CN" ? "模型" : "Model"}
              </TableHead>
              <TableHead className="w-[360px]">
                {locale === "zh-CN" ? "目标模型组" : "Target group"}
              </TableHead>
              <TableHead className="w-44">
                {locale === "zh-CN" ? "协议" : "Protocols"}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const key = modelGroupEnsureResultKey(item);
              const targetModelGroups = selectableModelGroupsForEnsureItem(
                item,
                modelGroups,
                isProtocolExtensionAllowed,
              );
              const targetGroupIsSelectable = targetModelGroups.some(
                (group) => group.name === item.group_name,
              );
              const createGroupName = getCreateGroupName(
                item,
                key,
                targetGroupIsSelectable,
              );
              return (
                <TableRow key={key}>
                  <TableCell>
                    <Checkbox
                      checked={selectedItemKeys.includes(key)}
                      disabled={
                        !canSubmitModelGroupEnsureItem(item) || isConfirming
                      }
                      aria-label={
                        locale === "zh-CN"
                          ? `选择 ${item.group_name}`
                          : `Select ${item.group_name}`
                      }
                      onCheckedChange={() => onToggleItem(item)}
                    />
                  </TableCell>
                  <TableCell>
                    <Badge variant={modelGroupEnsureStatusVariant(item.status)}>
                      {modelGroupEnsureStatusLabel(item.status, locale)}
                    </Badge>
                  </TableCell>
                  <TableCell className="min-w-[220px] max-w-[300px]">
                    <div
                      className="truncate font-medium"
                      title={item.model_name}
                    >
                      {item.model_name}
                    </div>
                  </TableCell>
                  <TableCell className="min-w-[320px]">
                    <ModelGroupTargetSelector
                      item={item}
                      targetModelGroups={targetModelGroups}
                      targetGroupIsSelectable={targetGroupIsSelectable}
                      createGroupName={
                        createGroupNameDrafts[key] ?? createGroupName
                      }
                      createGroupNameError={createGroupNameErrors[key]}
                      isConfirming={isConfirming}
                      isOpen={openTargetGroupKey === key}
                      locale={locale}
                      onOpenChange={(open) =>
                        onOpenTargetGroupChange(open ? key : null)
                      }
                      onSelectCreate={() => onSelectCreate(item, key)}
                      onSelectExisting={(groupName) =>
                        onSelectExisting(item, key, groupName)
                      }
                      onDraftChange={(value) => onDraftChange(key, value)}
                      onCommitDraft={() => onCommitDraft(item)}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex max-w-[180px] flex-wrap gap-1">
                      {item.protocols.map((protocol) => (
                        <Badge
                          key={protocol}
                          variant="outline"
                          className={cn(
                            "max-w-[120px] truncate text-xs",
                            protocolBadgeClassName(protocol),
                          )}
                        >
                          {compactProtocolLabel(protocol)}
                        </Badge>
                      ))}
                      {item.skipped_reason === "protocol_extension_required" ? (
                        <Badge variant="outline" className="text-xs">
                          {modelGroupEnsureReasonLabel(
                            item.skipped_reason,
                            locale,
                          )}
                        </Badge>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
