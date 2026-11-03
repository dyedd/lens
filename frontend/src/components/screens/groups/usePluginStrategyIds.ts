import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import type { RoutingStrategy } from "@/lib/api/groups";

/** 插件列表里策略选择器用到的部分。 */
type PluginStrategiesView = { state: string; strategies: RoutingStrategy[] };

/** 启用中的插件提供的策略 id；与插件页共用 ["plugins"] 查询。 */
export function usePluginStrategyIds(): RoutingStrategy[] {
  const pluginsQuery = useQuery({
    queryKey: ["plugins"],
    queryFn: () => apiRequest<PluginStrategiesView[]>("/admin/plugins"),
  });
  return (pluginsQuery.data ?? [])
    .filter((plugin) => plugin.state === "active")
    .flatMap((plugin) => plugin.strategies);
}
