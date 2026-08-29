import type { Dispatch, SetStateAction } from "react";
import type { ModelGroup, RoutingStrategy } from "@/lib/api/groups";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";
import type { GroupRow, GroupSort } from "./groupTypes";

export type GroupCardDragging = {
  groupId: string;
  kind: "channel" | "member";
  index: number;
} | null;

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
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  setSearch: Dispatch<SetStateAction<string>>;
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
  reorderGroupChannels: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupChannel: (group: GroupRow, channelKey: string) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
  toggleGroupEnabled: (group: GroupRow, enabled: boolean) => void;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
  testingModel: boolean;
  openModelTest: (group: GroupRow) => void;
}
