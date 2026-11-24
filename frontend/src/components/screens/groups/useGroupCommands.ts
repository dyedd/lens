import { useQueryClient } from "@tanstack/react-query";
import {
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useState,
} from "react";
import { toast } from "sonner";
import { apiFetch, apiRequest, getApiErrorMessage } from "@/lib/api/client";
import {
  createModelGroup,
  type ModelGroup,
  type ModelGroupMergeRequest,
  type ModelGroupPlacementRequest,
  type ModelGroupPlacementResponse,
  type RoutingStrategy,
  type UnplacedModelRemovalRequest,
  type UnplacedModelRemovalResponse,
} from "@/lib/api/groups";
import { parseContextWindowInput } from "@/lib/contextWindow";
import { titleForLocale } from "@/lib/I18nContext";
import {
  EMPTY_FORM,
  type FormState,
  type GroupRow,
  type SimilarGroupView,
} from "./groupTypes";
import { formToModelGroupPayload, modelGroupToForm } from "./groupView";
import { isGroupEnabled, strategyLabel } from "./modelGroupFormatting";

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
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null);

  async function saveGroup(
    payload: FormState,
    groupId: string | null,
    refresh = true,
  ) {
    const body = JSON.stringify(formToModelGroupPayload(payload));
    const id = groupId ?? (await createModelGroup(body));
    if (groupId !== null) {
      await apiRequest<unknown>(`/admin/model-groups/${groupId}`, {
        method: "PUT",
        body,
      });
    }
    if (refresh) await invalidateGroupData();
    return id;
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
      toast.error(getApiErrorMessage(error, failureMessage));
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function runBulkCommand<T>(
    items: T[],
    failureMessage: string,
    action: (item: T) => Promise<void>,
    busyMarker = "bulk",
  ) {
    setBusyId(busyMarker);
    let completed = 0;
    let commandError: unknown;
    let failed = false;
    for (const item of items) {
      try {
        await action(item);
        completed += 1;
      } catch (error) {
        commandError = error;
        failed = true;
        break;
      }
    }

    try {
      if (completed) await invalidateGroupData();
    } catch (refreshError) {
      const message =
        completed === items.length
          ? titleForLocale(
              locale,
              `已完成 ${completed} 项操作，但列表刷新失败`,
              `Completed all ${completed} operations, but could not refresh the list`,
            )
          : titleForLocale(
              locale,
              `已完成 ${completed} / ${items.length} 项操作，后续操作未执行且列表刷新失败`,
              `Completed ${completed} of ${items.length} operations. The remaining operations were not run and the list could not refresh`,
            );
      const errorMessages = [getApiErrorMessage(refreshError, failureMessage)];
      if (failed) {
        errorMessages.push(getApiErrorMessage(commandError, failureMessage));
      }
      toast.error(`${message}. ${errorMessages.join(". ")}`);
      setBusyId(null);
      return false;
    }

    setBusyId(null);
    if (!failed) return true;

    const message = getApiErrorMessage(commandError, failureMessage);
    toast.error(
      completed
        ? `${titleForLocale(
            locale,
            `已完成 ${completed} / ${items.length} 项操作，后续操作未执行`,
            `Completed ${completed} of ${items.length} operations. Remaining operations were not run`,
          )}. ${message}`
        : message,
    );
    return false;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (parseContextWindowInput(form.context_window) === undefined) {
      toast.error(
        locale === "zh-CN"
          ? "默认上下文格式无效，示例：200K、1M、128000"
          : "Invalid default context. Examples: 200K, 1M, 128000",
      );
      return;
    }
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
        getApiErrorMessage(
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
        await apiFetch(`/admin/model-groups/${group.id}`, {
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
    const updated = await runBulkCommand(
      targets,
      locale === "zh-CN" ? "批量更新模型组失败" : "Failed to update groups",
      async (group) => {
        const groupForm = modelGroupToForm(group);
        const items = groupForm.items.map((item) => ({ ...item, enabled }));
        await saveGroup({ ...groupForm, items }, group.id, false);
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
    const updated = await runBulkCommand(
      targets,
      locale === "zh-CN" ? "批量更新模型组失败" : "Failed to update groups",
      async (group) => {
        await saveGroup(
          { ...modelGroupToForm(group), strategy },
          group.id,
          false,
        );
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
    const removed = await runBulkCommand(
      targetGroups,
      locale === "zh-CN" ? "批量删除模型组失败" : "Failed to delete groups",
      async (group) => {
        await apiFetch(`/admin/model-groups/${group.id}`, {
          method: "DELETE",
        });
      },
    );
    if (!removed) return;
    setDeleteTarget(null);
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
    if (!merged) return false;
    toast.success(
      locale === "zh-CN"
        ? `已将「${source.name}」合并到「${target.name}」`
        : `Merged "${source.name}" into "${target.name}"`,
    );
    return true;
  }

  /** Save unplaced model names as members of an existing group. */
  async function addModelsToGroup(groupId: string, modelNames: string[]) {
    const group = groups.find((item) => item.id === groupId);
    if (!group) return;
    const added = await runCommand(
      group.id,
      locale === "zh-CN" ? "加入模型组失败" : "Failed to add to the group",
      async () => {
        await apiRequest<unknown>("/admin/model-group-placements", {
          method: "POST",
          body: JSON.stringify({ model_names: modelNames, group_id: groupId }),
        });
        await invalidateGroupData();
      },
    );
    if (added) {
      toast.success(
        locale === "zh-CN"
          ? `已加入「${group.name}」`
          : `Added to "${group.name}"`,
      );
    }
  }

  /** Create one own group per model name, then refresh once. */
  async function createOwnGroups(modelNames: string[]) {
    const names = [
      ...new Set(modelNames.map((name) => name.trim()).filter(Boolean)),
    ];
    if (!names.length) return false;
    const failureMessage =
      locale === "zh-CN" ? "创建模型组失败" : "Failed to create groups";
    const created = await runBulkCommand(
      names,
      failureMessage,
      async (name) => {
        await createModelGroup(
          JSON.stringify(formToModelGroupPayload({ ...EMPTY_FORM, name })),
        );
      },
      "unplaced-own-groups",
    );
    if (!created) return false;
    toast.success(
      locale === "zh-CN"
        ? `已创建 ${names.length} 个模型组`
        : `Created ${names.length} groups`,
    );
    return true;
  }

  /** Create a group and save the given models as its members. */
  async function createGroupForModels(name: string, modelNames: string[]) {
    const created = await runCommand(
      `place:${name}`,
      locale === "zh-CN" ? "创建模型组失败" : "Failed to create group",
      async () => {
        const groupId = await saveGroup({ ...EMPTY_FORM, name }, null);
        await apiRequest<unknown>("/admin/model-group-placements", {
          method: "POST",
          body: JSON.stringify({ model_names: modelNames, group_id: groupId }),
        });
        await invalidateGroupData();
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
      const { created, joined, unplaced } =
        await apiRequest<ModelGroupPlacementResponse>(
          "/admin/model-group-placements",
          { method: "POST", body: JSON.stringify(payload) },
        );
      await invalidateGroupData();
      const joinedModelCount = new Set(joined.map((item) => item.model_name))
        .size;
      toast.success(
        locale === "zh-CN"
          ? `已创建 ${created.length} 个模型组，${joinedModelCount} 个加入同名模型组，剩余 ${unplaced.length} 个待分配`
          : `Created ${created.length} groups, ${joinedModelCount} joined same-named groups, ${unplaced.length} still need assignment`,
      );
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "自动分配失败" : "Automatic assignment failed",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  /** Remove unplaced model names from every channel offering them. */
  function removeUnplacedModels(modelNames: string[]) {
    const payload: UnplacedModelRemovalRequest = { model_names: modelNames };
    return runCommand(
      "unplaced-removal",
      locale === "zh-CN" ? "删除渠道模型失败" : "Failed to remove models",
      async () => {
        const { deleted } = await apiRequest<UnplacedModelRemovalResponse>(
          "/admin/unplaced-model-removals",
          { method: "POST", body: JSON.stringify(payload) },
        );
        await Promise.all([
          invalidateGroupData(),
          queryClient.invalidateQueries({ queryKey: ["sites"] }),
        ]);
        toast.success(
          locale === "zh-CN"
            ? `已删除 ${deleted} 个渠道模型`
            : `Removed ${deleted} channel models`,
        );
      },
    );
  }

  return {
    addModelsToGroup,
    applyEnabled,
    applyStrategy,
    autoPlaceModels,
    busyId,
    changeStrategy,
    createGroupForModels,
    createOwnGroups,
    deleteTarget,
    mergeGroup,
    remove,
    removeGroups,
    removeUnplacedModels,
    setDeleteTarget,
    submit,
    toggleGroupEnabled,
  };
}
