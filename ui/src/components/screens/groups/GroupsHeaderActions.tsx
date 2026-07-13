"use client";

import { Plus, RefreshCcw } from "lucide-react";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";

/** Render model group creation and price synchronization actions. */
export function GroupsHeaderActions({
  locale,
  openCreate,
  syncingPrices,
  syncPrices,
}: {
  locale: "zh-CN" | "en-US";
  openCreate: () => void;
  syncingPrices: boolean;
  syncPrices: () => void;
}) {
  const syncPricesLabel = syncingPrices
    ? locale === "zh-CN"
      ? "同步中..."
      : "Syncing..."
    : locale === "zh-CN"
      ? "同步价格"
      : "Sync prices";
  const createGroupLabel =
    locale === "zh-CN" ? "新增模型组" : "New model group";

  return (
    <DashboardHeaderActions>
      <div className="flex items-center justify-end gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={syncPricesLabel}
              onClick={() => void syncPrices()}
              disabled={syncingPrices}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={syncingPrices ? "animate-spin" : ""}
              />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {syncPricesLabel}
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              type="button"
              variant="ghost"
              aria-label={createGroupLabel}
              onClick={openCreate}
            >
              <Plus />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {createGroupLabel}
          </TooltipContent>
        </Tooltip>
      </div>
    </DashboardHeaderActions>
  );
}
