"use client"

import { useQuery } from "@tanstack/react-query"

import { apiRequest, type AppInfo } from "@/lib/api"

const DEFAULT_APP_TIME_ZONE = "Asia/Shanghai"

export function useAppTimeZone() {
  const { data } = useQuery({
    queryKey: ["app-info"],
    queryFn: () => apiRequest<AppInfo>("/admin/app-info"),
    staleTime: 5 * 60_000,
  })

  return data?.time_zone || DEFAULT_APP_TIME_ZONE
}
