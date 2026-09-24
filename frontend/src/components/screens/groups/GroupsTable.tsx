import { MoreHorizontal, Settings2, TestTube2, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { ModelGroup } from "@/lib/api/groups";
import { getModelGroupAvatar } from "@/lib/ModelIcons";
import { protocolLabel } from "@/lib/protocols";
import type { GroupRow } from "./groupTypes";
import {
  groupMemberProtocols,
  isGroupEnabled,
  STRATEGY_OPTIONS,
} from "./modelGroupFormatting";

type Props = {
  locale: "zh-CN" | "en-US";
  items: GroupRow[];
  loading: boolean;
  selected: Set<string>;
  busyId: string | null;
  testingModel: boolean;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (id: string, checked: boolean) => void;
  onEdit: (group: ModelGroup) => void;
  onToggleEnabled: (group: GroupRow, enabled: boolean) => void;
  onDelete: (group: ModelGroup) => void;
  onTest: (group: GroupRow) => void;
};

function strategyLabel(
  strategy: GroupRow["strategy"],
  locale: "zh-CN" | "en-US",
) {
  const option = STRATEGY_OPTIONS.find((item) => item.value === strategy);
  return option ? (locale === "zh-CN" ? option.zh : option.en) : strategy;
}

/** Renders the model group table. */
export function GroupsTable({
  locale,
  items,
  loading,
  selected,
  busyId,
  testingModel,
  onSelectAll,
  onSelectOne,
  onEdit,
  onToggleEnabled,
  onDelete,
  onTest,
}: Props) {
  const allSelected =
    items.length > 0 && items.every((item) => selected.has(item.id));
  const someSelected = items.some((item) => selected.has(item.id));
  const emptyLabel = locale === "zh-CN" ? "暂无模型组" : "No groups";
  const loadingLabel = locale === "zh-CN" ? "加载中..." : "Loading...";

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[44px] text-center">
            <div className="flex h-7 items-center justify-center">
              <Checkbox
                checked={
                  allSelected ? true : someSelected ? "indeterminate" : false
                }
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={
                  locale === "zh-CN" ? "全选模型组" : "Select all groups"
                }
              />
            </div>
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "模型组" : "Group"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "类型" : "Type"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "协议" : "Protocols"}</TableHead>
          <TableHead className="text-center">
            {locale === "zh-CN" ? "成员" : "Members"}
          </TableHead>
          <TableHead className="text-center">
            {locale === "zh-CN" ? "状态" : "Status"}
          </TableHead>
          <TableHead className="w-[56px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={7}
              className="h-32 text-center text-muted-foreground"
            >
              {loadingLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {!loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={7}
              className="h-32 text-center text-muted-foreground"
            >
              {emptyLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {items.map((group) => {
          const Avatar = getModelGroupAvatar(group.name);
          const protocols = groupMemberProtocols(group);
          const enabled = isGroupEnabled(group);
          const busy = busyId === group.id || busyId === "bulk";
          const canToggle = !group.is_route_group && group.items.length > 0;
          const canTest =
            !group.is_route_group &&
            group.display_members.some((member) =>
              member.items.some(
                (item) => item.state === "ready" && item.protocol,
              ),
            );
          return (
            <TableRow
              key={group.id}
              data-state={selected.has(group.id) ? "selected" : undefined}
            >
              <TableCell className="w-[44px] py-1.5 text-center">
                <div className="flex h-7 items-center justify-center">
                  <Checkbox
                    checked={selected.has(group.id)}
                    onCheckedChange={(checked) =>
                      onSelectOne(group.id, checked === true)
                    }
                    aria-label={
                      locale === "zh-CN"
                        ? `选择 ${group.name}`
                        : `Select ${group.name}`
                    }
                  />
                </div>
              </TableCell>
              <TableCell className="py-1.5">
                <div className="flex min-w-0 items-center gap-2">
                  <Avatar size={16} />
                  <span className="min-w-0 truncate text-xs font-medium">
                    {group.name}
                  </span>
                  {group.problem_member_count > 0 ? (
                    <Badge variant="secondary" className="shrink-0">
                      {group.problem_member_count}
                    </Badge>
                  ) : null}
                </div>
              </TableCell>
              <TableCell className="py-1.5">
                <div className="flex items-center gap-1">
                  <Badge variant="secondary">
                    {group.is_route_group
                      ? locale === "zh-CN"
                        ? "路由组"
                        : "Route"
                      : locale === "zh-CN"
                        ? "执行组"
                        : "Execute"}
                  </Badge>
                  {group.is_route_group ? null : (
                    <Badge
                      variant="secondary"
                      className="text-muted-foreground"
                    >
                      {strategyLabel(group.strategy, locale)}
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell className="py-1.5">
                {protocols.length ? (
                  <div className="flex flex-wrap gap-1">
                    {protocols.map((protocol) => (
                      <Badge key={protocol} variant="secondary">
                        {protocolLabel(protocol, locale)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="py-1.5 text-center text-xs text-muted-foreground">
                {group.is_route_group
                  ? "—"
                  : locale === "zh-CN"
                    ? `${group.enabled_member_count} / ${group.member_count}`
                    : `${group.enabled_member_count} / ${group.member_count}`}
              </TableCell>
              <TableCell className="py-1.5">
                <div className="flex h-7 items-center justify-center">
                  {group.is_route_group ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    <Switch
                      size="sm"
                      checked={enabled}
                      disabled={busy || !canToggle}
                      onCheckedChange={(checked) =>
                        void onToggleEnabled(group, checked)
                      }
                      aria-label={
                        locale === "zh-CN"
                          ? `${enabled ? "停止" : "启动"} ${group.name}`
                          : `${enabled ? "Disable" : "Enable"} ${group.name}`
                      }
                    />
                  )}
                </div>
              </TableCell>
              <TableCell className="w-[56px] py-1.5">
                <div className="flex h-7 items-center justify-end">
                  <DropdownMenu modal={false}>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none"
                      >
                        <MoreHorizontal className="size-3.5 stroke-1" />
                        <span className="sr-only">
                          {locale === "zh-CN" ? "操作" : "Actions"}
                        </span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => onEdit(group)}>
                        <Settings2 className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "编辑模型组" : "Edit group"}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        disabled={!canTest || testingModel}
                        onSelect={() => onTest(group)}
                      >
                        <TestTube2 className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "测试模型" : "Test models"}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => onDelete(group)}>
                        <Trash2 className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "删除模型组" : "Delete group"}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
