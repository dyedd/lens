import { useQuery } from "@tanstack/react-query";
import { requestModelGroups } from "@/lib/api/groups";

/** Shared cache entry for the model group list; invalidate with `["groups"]`. */
export function useModelGroupsQuery() {
  return useQuery({
    queryKey: ["groups"],
    queryFn: requestModelGroups,
    staleTime: 2 * 60_000,
  });
}
