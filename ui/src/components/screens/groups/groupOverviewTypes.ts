import type { Dispatch, SetStateAction } from "react";
import type { ModelGroup, ProtocolKind, RoutingStrategy } from "@/lib/api";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";
import type { GroupRow, GroupSort } from "./modelGroupUtils";

export type GroupCardDragging = { groupId: string; index: number } | null;

export interface GroupsOverviewProps {
  locale: "zh-CN" | "en-US";
  hasModelPrefixOptions: boolean;
  modelPrefixOptions: ModelPrefixOption[];
  effectiveSelectedModelPrefix: SelectedModelPrefix;
  setSelectedModelPrefix: Dispatch<SetStateAction<SelectedModelPrefix>>;
  isLoading: boolean;
  groupsIsError: boolean;
  visibleGroups: GroupRow[];
  busyId: string | null;
  cardDragging: GroupCardDragging;
  setCardDragging: Dispatch<SetStateAction<GroupCardDragging>>;
  search: string;
  protocolFilter: "all" | ProtocolKind;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  setSearch: Dispatch<SetStateAction<string>>;
  setProtocolFilter: Dispatch<SetStateAction<"all" | ProtocolKind>>;
  setStrategyFilter: Dispatch<SetStateAction<"all" | RoutingStrategy>>;
  setSortBy: Dispatch<SetStateAction<GroupSort>>;
  resetFilters: () => void;
  openEdit: (item: ModelGroup) => void;
  changeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  reorderGroupMembers: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
  toggleGroupEnabled: (group: GroupRow, enabled: boolean) => void;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
}
