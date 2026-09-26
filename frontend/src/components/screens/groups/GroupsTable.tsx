import {
  Check,
  ChevronDown,
  Combine,
  MoreHorizontal,
  Settings2,
  TestTube2,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { ModelGroup, RoutingStrategy } from "@/lib/api/groups";
import { getModelGroupAvatar } from "@/lib/ModelIcons";
import { protocolLabel } from "@/lib/protocols";
import type {
  GroupDisplayMember,
  GroupRow,
  SimilarGroupView,
} from "./groupTypes";
import {
  formatCredentialIdentity,
  groupMemberProtocols,
  isGroupEnabled,
  STRATEGY_OPTIONS,
  strategyLabel,
} from "./modelGroupFormatting";

const MATCH_MODEL_PREVIEW_LIMIT = 2;

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
  onChangeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  onRequestMerge: (source: GroupRow, target: SimilarGroupView) => void;
  onDelete: (group: ModelGroup) => void;
  onTest: (group: GroupRow) => void;
};

function formatMemberState(
  member: GroupDisplayMember,
  locale: "zh-CN" | "en-US",
) {
  if (member.ready_item_count > 0) return locale === "zh-CN" ? "可用" : "Ready";
  if (member.enabled_item_count === 0) {
    return locale === "zh-CN" ? "已关闭" : "Disabled";
  }
  if (member.invalid_item_count > 0) {
    return locale === "zh-CN" ? "配置错误" : "Invalid";
  }
  return locale === "zh-CN" ? "不可用" : "Unavailable";
}

function GroupMembersPopover({
  group,
  locale,
}: {
  group: GroupRow;
  locale: "zh-CN" | "en-US";
}) {
  if (group.is_route_group) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  if (!group.display_members.length) {
    return (
      <span className="text-xs text-muted-foreground">
        {locale === "zh-CN" ? "暂无成员" : "No members"}
      </span>
    );
  }
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="xs"
          className="-ml-2 font-normal text-muted-foreground tabular-nums shadow-none"
        >
          {locale === "zh-CN"
            ? `${group.site_count} 站点 · ${group.credential_count} 密钥`
            : `${group.site_count} sites · ${group.credential_count} keys`}
          {group.problem_member_count > 0 ? (
            <Badge variant="destructive" className="h-4 px-1.5 text-[10px]">
              {group.problem_member_count}
            </Badge>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[420px] p-2">
        <p className="px-1 pb-1.5 text-[11px] text-muted-foreground">
          {group.strategy === "failover"
            ? locale === "zh-CN"
              ? "按顺序故障转移"
              : "Failover in order"
            : locale === "zh-CN"
              ? "轮询分配"
              : "Round robin"}
        </p>
        <ol className="max-h-72 space-y-0.5 overflow-y-auto">
          {group.display_members.map((member, index) => (
            <li
              key={member.key}
              className="flex items-start gap-2 rounded-md px-1 py-1 text-xs"
            >
              <span className="w-4 shrink-0 text-right tabular-nums text-muted-foreground">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate">
                  {formatCredentialIdentity(member, locale)}
                </div>
                {member.model_name !== group.name ? (
                  <div className="truncate font-mono text-[11px] text-muted-foreground">
                    {member.model_name}
                  </div>
                ) : null}
              </div>
              {member.matched_by_rule ? (
                <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                  {locale === "zh-CN" ? "规则" : "Rule"}
                </Badge>
              ) : null}
              <span
                className={
                  member.ready_item_count > 0
                    ? "shrink-0 text-muted-foreground"
                    : "shrink-0 text-destructive"
                }
              >
                {formatMemberState(member, locale)}
              </span>
            </li>
          ))}
        </ol>
      </PopoverContent>
    </Popover>
  );
}

function GroupMatchRules({ group }: { group: GroupRow }) {
  if (!group.match_models.length && !group.match_regex) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const hiddenCount = group.match_models.length - MATCH_MODEL_PREVIEW_LIMIT;
  return (
    <div
      className="flex flex-wrap gap-1"
      title={[...group.match_models, group.match_regex]
        .filter(Boolean)
        .join("\n")}
    >
      {group.match_models.slice(0, MATCH_MODEL_PREVIEW_LIMIT).map((name) => (
        <Badge key={name} variant="outline" className="font-mono font-normal">
          {name}
        </Badge>
      ))}
      {hiddenCount > 0 ? (
        <Badge variant="secondary">+{hiddenCount}</Badge>
      ) : null}
      {group.match_regex ? (
        <Badge variant="secondary" className="font-mono font-normal">
          /{group.match_regex}/
        </Badge>
      ) : null}
    </div>
  );
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
  onChangeStrategy,
  onRequestMerge,
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
          <TableHead>{locale === "zh-CN" ? "策略" : "Strategy"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "成员" : "Members"}</TableHead>
          <TableHead>
            {locale === "zh-CN" ? "匹配规则" : "Match rules"}
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "协议" : "Protocols"}</TableHead>
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
              colSpan={8}
              className="h-32 text-center text-muted-foreground"
            >
              {loadingLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {!loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={8}
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
            group.items.some((item) => item.state === "ready" && item.protocol);
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
                  <span className="min-w-0 truncate font-mono text-xs font-medium">
                    {group.name}
                  </span>
                  {group.similar_groups.length ? (
                    <DropdownMenu modal={false}>
                      <DropdownMenuTrigger asChild>
                        <button
                          type="button"
                          disabled={busy}
                          className="shrink-0 rounded-4xl"
                        >
                          <Badge variant="outline" className="hover:bg-muted">
                            {locale === "zh-CN" ? "疑似重复" : "Similar"}
                          </Badge>
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuLabel className="text-[10px] text-muted-foreground">
                          {locale === "zh-CN" ? "合并到…" : "Merge into…"}
                        </DropdownMenuLabel>
                        {group.similar_groups.map((target) => (
                          <DropdownMenuItem
                            key={target.id}
                            onSelect={() => onRequestMerge(group, target)}
                          >
                            <Combine className="size-3.5 stroke-1" />
                            <span className="font-mono">{target.name}</span>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : null}
                </div>
              </TableCell>
              <TableCell className="py-1.5">
                {group.is_route_group ? (
                  <Badge variant="secondary" className="max-w-48">
                    <span className="truncate">
                      {locale === "zh-CN" ? "路由 → " : "Route → "}
                      {group.route_group_name || group.route_group_id}
                    </span>
                  </Badge>
                ) : (
                  <DropdownMenu modal={false}>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        disabled={busy}
                        className="-ml-2 font-normal text-muted-foreground shadow-none"
                      >
                        {strategyLabel(group.strategy, locale)}
                        <ChevronDown data-icon="inline-end" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start">
                      {STRATEGY_OPTIONS.map((option) => (
                        <DropdownMenuItem
                          key={option.value}
                          onSelect={() => onChangeStrategy(group, option.value)}
                        >
                          <span className="flex-1">
                            {locale === "zh-CN" ? option.zh : option.en}
                          </span>
                          {group.strategy === option.value ? (
                            <Check className="size-3.5 text-muted-foreground" />
                          ) : null}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </TableCell>
              <TableCell className="py-1.5">
                <GroupMembersPopover group={group} locale={locale} />
              </TableCell>
              <TableCell className="py-1.5">
                <GroupMatchRules group={group} />
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
