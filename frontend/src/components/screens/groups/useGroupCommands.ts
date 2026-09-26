import {
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useState,
} from "react";
import { toast } from "sonner";
import { apiRequest } from "@/lib/api/client";
import type {
  ModelGroup,
  ModelGroupMergeRequest,
  ModelGroupPlacementRequest,
  ModelGroupPlacementResponse,
  RoutingStrategy,
} from "@/lib/api/groups";
import {
  EMPTY_FORM,
  type FormState,
  type GroupRow,
  type SimilarGroupView,
} from "./groupTypes";
import { formToModelGroupPayload, modelGroupToForm } from "./groupView";
import {
  isGroupEnabled,
  modelGroupErrorMessage,
  strategyLabel,
} from "./modelGroupFormatting";

type GroupCommandOptions = {
  editingId: string | null;
  form: FormState;
  groups: ModelGroup[];
  invalidateGroupData: () => Promise<void>;
  locale: "zh-CN" | "en-US";
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Manage persistence commands for model groups and model placement. */
export function useGroupCommands({
  editingId,
  form,
  groups,
  invalidateGroupData,
  locale,
  setDialogOpen,
  setEditingId,
  setForm,
}: GroupCommandOptions) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null);

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

  /** Run one persistence action under a busy marker, toasting failures. */
  async function runCommand(
    marker: string,
    failureMessage: string,
    action: () => Promise<void>,
  ) {
    setBusyId(marker);
    try {
      await action();
      return true;
    } catch (error) {
      toast.error(modelGroupErrorMessage(error, failureMessage));
      return false;
    } finally {
      setBusyId(null);
    }
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
    const removed = await runCommand(
      group.id,
      locale === "zh-CN" ? "删除模型组失败" : "Failed to delete group",
      async () => {
        await apiRequest<void>(`/admin/model-groups/${group.id}`, {
          method: "DELETE",
        });
        setDeleteTarget(null);
        await invalidateGroupData();
      },
    );
    if (removed) {
      toast.success(locale === "zh-CN" ? "模型组已删除" : "Group deleted");
    }
  }

  function updateGroupPartial(group: ModelGroup, updates: Partial<FormState>) {
    return runCommand(
      group.id,
      locale === "zh-CN" ? "更新模型组失败" : "Failed to update group",
      async () => {
        await saveGroup({ ...modelGroupToForm(group), ...updates }, group.id);
      },
    );
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

  async function applyEnabled(targetGroups: GroupRow[], enabled: boolean) {
    const targets = targetGroups.filter(
      (group) =>
        !group.is_route_group &&
        group.items.length > 0 &&
        isGroupEnabled(group) !== enabled,
    );
    if (!targets.length) return;
    const updated = await runCommand(
      "bulk",
      locale === "zh-CN" ? "批量更新模型组失败" : "Failed to update groups",
      async () => {
        for (const group of targets) {
          const groupForm = modelGroupToForm(group);
          const items = groupForm.items.map((item) => ({ ...item, enabled }));
          await saveGroup({ ...groupForm, items }, group.id);
        }
      },
    );
    if (!updated) return;
    toast.success(
      enabled
        ? locale === "zh-CN"
          ? `已启动 ${targets.length} 个模型组`
          : `Enabled ${targets.length} groups`
        : locale === "zh-CN"
          ? `已停止 ${targets.length} 个模型组`
          : `Disabled ${targets.length} groups`,
    );
  }

  async function applyStrategy(
    targetGroups: GroupRow[],
    strategy: RoutingStrategy,
  ) {
    const targets = targetGroups.filter(
      (group) => !group.is_route_group && group.strategy !== strategy,
    );
    if (!targets.length) return;
    const updated = await runCommand(
      "bulk",
      locale === "zh-CN" ? "批量更新模型组失败" : "Failed to update groups",
      async () => {
        for (const group of targets) {
          await saveGroup({ ...modelGroupToForm(group), strategy }, group.id);
        }
      },
    );
    if (!updated) return;
    toast.success(
      locale === "zh-CN"
        ? `已将 ${targets.length} 个模型组设为${strategyLabel(strategy, locale)}`
        : `Set ${targets.length} groups to ${strategyLabel(strategy, locale)}`,
    );
  }

  async function removeGroups(targetGroups: ModelGroup[]) {
    if (!targetGroups.length) return;
    const removed = await runCommand(
      "bulk",
      locale === "zh-CN" ? "批量删除模型组失败" : "Failed to delete groups",
      async () => {
        for (const group of targetGroups) {
          await apiRequest<void>(`/admin/model-groups/${group.id}`, {
            method: "DELETE",
          });
        }
        setDeleteTarget(null);
        await invalidateGroupData();
      },
    );
    if (!removed) return;
    toast.success(
      locale === "zh-CN"
        ? `已删除 ${targetGroups.length} 个模型组`
        : `Deleted ${targetGroups.length} groups`,
    );
  }

  /** Merge a group into another; the backend repoints references. */
  async function mergeGroup(source: ModelGroup, target: SimilarGroupView) {
    const payload: ModelGroupMergeRequest = { target_group_id: target.id };
    const merged = await runCommand(
      source.id,
      locale === "zh-CN" ? "合并模型组失败" : "Failed to merge groups",
      async () => {
        await apiRequest<ModelGroup>(`/admin/model-groups/${source.id}/merge`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        await invalidateGroupData();
      },
    );
    if (!merged) return;
    toast.success(
      locale === "zh-CN"
        ? `已将「${source.name}」合并到「${target.name}」`
        : `Merged "${source.name}" into "${target.name}"`,
    );
  }

  /** Add unplaced model names to an existing group's match rules. */
  async function addModelsToGroup(groupId: string, modelNames: string[]) {
    const group = groups.find((item) => item.id === groupId);
    if (!group) return;
    const matchModels = [...new Set([...group.match_models, ...modelNames])];
    if (await updateGroupPartial(group, { match_models: matchModels })) {
      toast.success(
        locale === "zh-CN"
          ? `已加入「${group.name}」`
          : `Added to "${group.name}"`,
      );
    }
  }

  /** Create one group whose match rules cover the given model names. */
  async function createGroupForModels(name: string, modelNames: string[]) {
    const created = await runCommand(
      `place:${name}`,
      locale === "zh-CN" ? "创建模型组失败" : "Failed to create group",
      async () => {
        await saveGroup(
          { ...EMPTY_FORM, name, match_models: modelNames },
          null,
        );
      },
    );
    if (created) {
      toast.success(
        locale === "zh-CN" ? `已创建「${name}」` : `Created "${name}"`,
      );
    }
  }

  /** Let the backend place every unplaced name that no longer collides. */
  async function autoPlaceModels() {
    const payload: ModelGroupPlacementRequest = { model_names: null };
    setBusyId("placement");
    try {
      const { created, unplaced } =
        await apiRequest<ModelGroupPlacementResponse>(
          "/admin/model-group-placements",
          { method: "POST", body: JSON.stringify(payload) },
        );
      await invalidateGroupData();
      toast.success(
        locale === "zh-CN"
          ? `已创建 ${created.length} 个模型组，剩余 ${unplaced.length} 个待放置`
          : `Created ${created.length} groups, ${unplaced.length} still unplaced`,
      );
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "自动放置失败" : "Auto placement failed",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  return {
    addModelsToGroup,
    applyEnabled,
    applyStrategy,
    autoPlaceModels,
    busyId,
    changeStrategy,
    createGroupForModels,
    deleteTarget,
    mergeGroup,
    remove,
    removeGroups,
    setDeleteTarget,
    submit,
    toggleGroupEnabled,
  };
}
