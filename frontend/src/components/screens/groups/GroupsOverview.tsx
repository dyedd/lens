import { GroupsFilterPanel } from "./GroupsFilterPanel";
import type { GroupsOverviewProps } from "./groupOverviewTypes";
import { ModelGroupList } from "./ModelGroupList";
import { ModelSeriesSelector } from "./ModelSeriesSelector";

/** Render the filtered model group overview and editor actions. */
export function GroupsOverview(props: GroupsOverviewProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
      <div className="order-2 flex min-w-0 flex-col gap-4 xl:order-1">
        {props.hasModelPrefixOptions ? (
          <ModelSeriesSelector
            locale={props.locale}
            modelPrefixOptions={props.modelPrefixOptions}
            selectedModelPrefix={props.effectiveSelectedModelPrefix}
            setSelectedModelPrefix={props.setSelectedModelPrefix}
          />
        ) : null}
        <ModelGroupList
          locale={props.locale}
          isLoading={props.isLoading}
          groupsIsError={props.groupsIsError}
          visibleGroups={props.visibleGroups}
          busyId={props.busyId}
          cardDragging={props.cardDragging}
          setCardDragging={props.setCardDragging}
          effectiveSelectedModelPrefix={props.effectiveSelectedModelPrefix}
          search={props.search}
          strategyFilter={props.strategyFilter}
          openEdit={props.openEdit}
          changeStrategy={props.changeStrategy}
          reorderGroupMembers={props.reorderGroupMembers}
          reorderGroupChannels={props.reorderGroupChannels}
          removeGroupChannel={props.removeGroupChannel}
          removeGroupMember={props.removeGroupMember}
          toggleGroupEnabled={props.toggleGroupEnabled}
          setDeleteTarget={props.setDeleteTarget}
          testingModel={props.testingModel}
          openModelTest={props.openModelTest}
        />
      </div>
      <GroupsFilterPanel
        locale={props.locale}
        search={props.search}
        strategyFilter={props.strategyFilter}
        sortBy={props.sortBy}
        activeFilterCount={props.activeFilterCount}
        setSearch={props.setSearch}
        setStrategyFilter={props.setStrategyFilter}
        setSortBy={props.setSortBy}
        resetFilters={props.resetFilters}
      />
    </div>
  );
}
