import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import type { ModelGroup } from "@/lib/api/groups";

/** Shared cache entry for the model group list; invalidate with `["groups"]`. */
export function useModelGroupsQuery() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 2 * 60_000,
  });
}
