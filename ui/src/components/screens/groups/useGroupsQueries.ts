"use client";

import { useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  apiRequest,
  type ModelGroup,
  type ModelGroupCandidatesPayload,
  type ModelGroupCandidatesResponse,
} from "@/lib/api";
import { buildGroupRows } from "./groupScreenData";
import { itemKey, type FormState } from "./modelGroupUtils";

type GroupsQueryOptions = {
  dialogOpen: boolean;
  editingId: string | null;
  form: FormState;
  locale: "zh-CN" | "en-US";
};

/** Load model group data and derive query-backed display metadata. */
export function useGroupsQueries({
  dialogOpen,
  editingId,
  form,
  locale,
}: GroupsQueryOptions) {
  const queryClient = useQueryClient();
  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 2 * 60_000,
  });
  const candidatePayload: ModelGroupCandidatesPayload = useMemo(
    () => ({
      protocols: form.protocols,
      items: form.items
        .map((item) => ({
          channel_id: item.channel_id,
          credential_id: item.credential_id,
          model_name: item.model_name,
          enabled: item.enabled,
        }))
        .sort((left, right) => itemKey(left).localeCompare(itemKey(right))),
    }),
    [form.items, form.protocols],
  );
  const candidateQuery = useQuery({
    queryKey: ["group-candidates", candidatePayload],
    queryFn: () =>
      apiRequest<ModelGroupCandidatesResponse>(
        "/admin/model-group-candidates",
        {
          method: "POST",
          body: JSON.stringify(candidatePayload),
        },
      ),
    enabled: dialogOpen && !form.route_group_id && form.protocols.length > 0,
  });
  const groupRows = useMemo(
    () => buildGroupRows(groupsQuery.data ?? []),
    [groupsQuery.data],
  );
  const routeTargetOptions = useMemo(
    () =>
      (groupsQuery.data ?? [])
        .filter(
          (group) =>
            form.protocols.every((protocol) =>
              group.protocols.includes(protocol),
            ) &&
            !group.route_group_id &&
            group.id !== editingId,
        )
        .sort((left, right) => left.name.localeCompare(right.name, locale)),
    [editingId, form.protocols, groupsQuery.data, locale],
  );

  useEffect(() => {
    if (!groupsQuery.isError) return;
    toast.error(
      locale === "zh-CN" ? "模型组加载失败" : "Failed to load groups",
      {
        id: "groups-load-error",
        description:
          groupsQuery.error instanceof Error
            ? groupsQuery.error.message
            : locale === "zh-CN"
              ? "无法读取模型组"
              : "Unable to read groups",
      },
    );
  }, [groupsQuery.error, groupsQuery.isError, locale]);

  async function invalidateGroupData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
  }

  return {
    candidateQuery,
    evaluatedItems: candidateQuery.data?.evaluated_items ?? [],
    groupRows,
    groups: groupsQuery.data,
    groupsIsError: groupsQuery.isError,
    invalidateGroupData,
    isLoading: groupsQuery.isLoading,
    queryClient,
    routeTargetOptions,
  };
}
