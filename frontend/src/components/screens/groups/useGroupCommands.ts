import {
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useState,
} from "react";
import { toast } from "sonner";
import { apiRequest } from "@/lib/api/client";
import type { ModelGroup, RoutingStrategy } from "@/lib/api/groups";
import type { GroupCardDragging } from "./groupTypes";
import { EMPTY_FORM, type FormState, type GroupRow } from "./groupTypes";
import { formToModelGroupPayload, modelGroupToForm } from "./groupView";
import {
  isGroupEnabled,
  modelGroupErrorMessage,
  modelGroupItemKey,
  moveItems,
} from "./modelGroupFormatting";

type GroupCommandOptions = {
  editingId: string | null;
  form: FormState;
  invalidateGroupData: () => Promise<void>;
  locale: "zh-CN" | "en-US";
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Manage persistence commands for model groups and prices. */
export function useGroupCommands({
  editingId,
  form,
  invalidateGroupData,
  locale,
  setDialogOpen,
  setEditingId,
  setForm,
}: GroupCommandOptions) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null);
  const [cardDragging, setCardDragging] = useState<GroupCardDragging>(null);

  async function saveGroup(payload: FormState, groupId: string | null) {
    const savedGroup = await apiRequest<ModelGroup>(
      groupId ? `/admin/model-groups/${groupId}` : "/admin/model-groups",
      {
        method: groupId ? "PUT" : "POST",
        body: JSON.stringify(formToModelGroupPayload(payload)),
      },
    );
    await invalidateGroupData();
    return savedGroup;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await saveGroup(form, editingId);
      toast.success(
        editingId
          ? locale === "zh-CN"
            ? "模型组已更新"
            : "Group updated"
          : locale === "zh-CN"
            ? "模型组已创建"
            : "Group created",
      );
      setDialogOpen(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "保存模型组失败" : "Failed to save group",
        ),
      );
    }
  }

  async function remove(group: ModelGroup) {
    setBusyId(group.id);
    try {
      await apiRequest<void>(`/admin/model-groups/${group.id}`, {
        method: "DELETE",
      });
      setDeleteTarget(null);
      await invalidateGroupData();
      toast.success(locale === "zh-CN" ? "模型组已删除" : "Group deleted");
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "删除模型组失败" : "Failed to delete group",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function updateGroupPartial(
    group: ModelGroup,
    updates: Partial<FormState>,
  ) {
    setBusyId(group.id);
    try {
      await saveGroup({ ...modelGroupToForm(group), ...updates }, group.id);
      return true;
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "更新模型组失败" : "Failed to update group",
        ),
      );
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function reorderGroupMembers(
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) {
    if (group.is_route_group || fromIndex === toIndex || busyId === group.id) {
      return;
    }
    const nextMembers = moveItems(group.display_members, fromIndex, toIndex);
    if (nextMembers === group.display_members) return;
    await updateGroupPartial(group, {
      items: nextMembers.flatMap((member) => member.items),
    });
  }

  async function reorderGroupChannels(
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) {
    if (group.is_route_group || fromIndex === toIndex || busyId === group.id) {
      return;
    }
    const nextChannels = moveItems(group.display_channels, fromIndex, toIndex);
    if (nextChannels === group.display_channels) return;
    await updateGroupPartial(group, {
      items: nextChannels.flatMap((channel) =>
        channel.members.flatMap((member) => member.items),
      ),
    });
  }

  async function changeStrategy(group: GroupRow, strategy: RoutingStrategy) {
    if (
      group.is_route_group ||
      busyId === group.id ||
      group.strategy === strategy
    ) {
      return;
    }
    if (await updateGroupPartial(group, { strategy })) {
      toast.success(locale === "zh-CN" ? "策略已更新" : "Strategy updated");
    }
  }

  async function toggleGroupEnabled(group: GroupRow, enabled: boolean) {
    if (
      group.is_route_group ||
      !group.items.length ||
      busyId === group.id ||
      isGroupEnabled(group) === enabled
    ) {
      return;
    }
    const items = modelGroupToForm(group).items.map((item) => ({
      ...item,
      enabled,
    }));
    if (await updateGroupPartial(group, { items })) {
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? "模型组已启动"
            : "Group enabled"
          : locale === "zh-CN"
            ? "模型组已停止"
            : "Group disabled",
      );
    }
  }

  async function removeGroupMember(group: GroupRow, memberKey: string) {
    if (group.is_route_group || busyId === group.id) return;
    const member = group.display_members.find((item) => item.key === memberKey);
    if (!member) return;
    const removedKeys = new Set(
      member.items.map((item) => modelGroupItemKey(item)),
    );
    const items = modelGroupToForm(group).items.filter(
      (item) => !removedKeys.has(modelGroupItemKey(item)),
    );
    if (await updateGroupPartial(group, { items })) {
      toast.success(locale === "zh-CN" ? "成员已删除" : "Member removed");
    }
  }

  async function removeGroupChannel(group: GroupRow, channelKey: string) {
    if (group.is_route_group || busyId === group.id) return;
    const channel = group.display_channels.find(
      (item) => item.key === channelKey,
    );
    if (!channel) return;
    const removedKeys = new Set(
      channel.members.flatMap((member) =>
        member.items.map((item) => modelGroupItemKey(item)),
      ),
    );
    const items = modelGroupToForm(group).items.filter(
      (item) => !removedKeys.has(modelGroupItemKey(item)),
    );
    if (await updateGroupPartial(group, { items })) {
      toast.success(locale === "zh-CN" ? "渠道已移除" : "Channel removed");
    }
  }

  async function applyEnabled(groups: GroupRow[], enabled: boolean) {
    const targets = groups.filter(
      (group) =>
        !group.is_route_group &&
        group.items.length > 0 &&
        isGroupEnabled(group) !== enabled,
    );
    if (!targets.length) return;
    setBusyId("bulk");
    try {
      for (const group of targets) {
        const items = modelGroupToForm(group).items.map((item) => ({
          ...item,
          enabled,
        }));
        await saveGroup({ ...modelGroupToForm(group), items }, group.id);
      }
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? `已启动 ${targets.length} 个模型组`
            : `Enabled ${targets.length} groups`
          : locale === "zh-CN"
            ? `已停止 ${targets.length} 个模型组`
            : `Disabled ${targets.length} groups`,
      );
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "批量更新模型组失败" : "Failed to update groups",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function removeGroups(groups: ModelGroup[]) {
    if (!groups.length) return;
    setBusyId("bulk");
    try {
      for (const group of groups) {
        await apiRequest<void>(`/admin/model-groups/${group.id}`, {
          method: "DELETE",
        });
      }
      setDeleteTarget(null);
      await invalidateGroupData();
      toast.success(
        locale === "zh-CN"
          ? `已删除 ${groups.length} 个模型组`
          : `Deleted ${groups.length} groups`,
      );
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "批量删除模型组失败" : "Failed to delete groups",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  return {
    applyEnabled,
    busyId,
    cardDragging,
    changeStrategy,
    deleteTarget,
    remove,
    removeGroupChannel,
    removeGroupMember,
    removeGroups,
    reorderGroupChannels,
    reorderGroupMembers,
    setCardDragging,
    setDeleteTarget,
    submit,
    toggleGroupEnabled,
  };
}
