"use client";

import {
  useState,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
} from "react";
import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiRequest, type ModelGroup, type RoutingStrategy } from "@/lib/api";
import {
  EMPTY_FORM,
  isGroupEnabled,
  itemKey,
  modelGroupErrorMessage,
  moveItems,
  toForm,
  toPayload,
  type FormState,
  type GroupRow,
} from "./modelGroupUtils";

type GroupCommandOptions = {
  editingId: string | null;
  form: FormState;
  invalidateGroupData: () => Promise<void>;
  locale: "zh-CN" | "en-US";
  queryClient: QueryClient;
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
  queryClient,
  setDialogOpen,
  setEditingId,
  setForm,
}: GroupCommandOptions) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null);
  const [cardDragging, setCardDragging] = useState<{
    groupId: string;
    index: number;
  } | null>(null);
  const [syncingPrices, setSyncingPrices] = useState(false);

  async function saveGroup(payload: FormState, groupId: string | null) {
    const savedGroup = await apiRequest<ModelGroup>(
      groupId ? `/admin/model-groups/${groupId}` : "/admin/model-groups",
      {
        method: groupId ? "PUT" : "POST",
        body: JSON.stringify(toPayload(payload)),
      },
    );
    await invalidateGroupData();
    return savedGroup;
  }

  async function saveGroupPrice(groupName: string, payload: FormState) {
    const priceValues = [
      payload.input_price_per_million,
      payload.output_price_per_million,
      payload.cache_read_price_per_million,
      payload.cache_write_price_per_million,
    ].map(Number);
    if (priceValues.some((value) => !Number.isFinite(value) || value < 0)) {
      throw new Error(
        locale === "zh-CN"
          ? "价格必须是大于等于 0 的数字"
          : "Prices must be numbers greater than or equal to 0",
      );
    }
    const [inputPrice, outputPrice, cacheReadPrice, cacheWritePrice] =
      priceValues;
    await apiRequest(`/admin/model-prices/${encodeURIComponent(groupName)}`, {
      method: "PUT",
      body: JSON.stringify({
        model_key: groupName,
        display_name: groupName,
        input_price_per_million: inputPrice,
        output_price_per_million: outputPrice,
        cache_read_price_per_million: cacheReadPrice,
        cache_write_price_per_million: cacheWritePrice,
      }),
    });
    await queryClient.invalidateQueries({ queryKey: ["groups"] });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "至少需要选择一项协议。"
          : "At least one protocol is required.",
      );
      return;
    }
    try {
      const savedGroup = await saveGroup(form, editingId);
      if (!savedGroup.route_group_id)
        await saveGroupPrice(savedGroup.name, form);
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

  async function syncPrices() {
    setSyncingPrices(true);
    try {
      await apiRequest("/admin/model-price-sync-jobs", { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      toast.success(
        locale === "zh-CN" ? "模型价格已同步" : "Model prices synced",
      );
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN"
            ? "同步模型价格失败"
            : "Failed to sync model prices",
        ),
      );
    } finally {
      setSyncingPrices(false);
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
      await saveGroup({ ...toForm(group), ...updates }, group.id);
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
      items: nextMembers.flatMap((member) =>
        member.items.map((item) => ({
          channel_id: item.channel_id,
          protocol_config_id: item.protocol_config_id,
          channel_name: item.channel_name,
          protocol: item.protocol,
          credential_id: item.credential_id,
          credential_name: item.credential_name,
          credential_number: item.credential_number,
          model_name: item.model_name,
          enabled: item.enabled,
          state: item.state,
          reasons: item.reasons,
        })),
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
    const items = toForm(group).items.map((item) => ({ ...item, enabled }));
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
    const removedKeys = new Set(member.items.map((item) => itemKey(item)));
    const items = toForm(group).items.filter(
      (item) => !removedKeys.has(itemKey(item)),
    );
    if (await updateGroupPartial(group, { items })) {
      toast.success(locale === "zh-CN" ? "成员已删除" : "Member removed");
    }
  }

  return {
    busyId,
    cardDragging,
    changeStrategy,
    deleteTarget,
    remove,
    removeGroupMember,
    reorderGroupMembers,
    setCardDragging,
    setDeleteTarget,
    submit,
    syncPrices,
    syncingPrices,
    toggleGroupEnabled,
  };
}
