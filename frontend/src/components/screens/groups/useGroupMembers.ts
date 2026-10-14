import { type Dispatch, type SetStateAction, useMemo } from "react";
import type { ModelGroup } from "@/lib/api/groups";
import type { FormItem, FormState, MemberStatusFilter } from "./groupTypes";
import { foldGroupMembers, groupFoldedMembersByChannel } from "./groupView";
import {
  insertNewMembers,
  modelFoldKey,
  modelGroupChannelKey,
  modelGroupItemKey,
  moveItems,
} from "./modelGroupFormatting";

function formItemMemberKey(item: FormItem) {
  return modelFoldKey(
    item.protocol_config_id,
    item.credential_id,
    item.model_name,
  );
}

function formItemChannelKey(item: FormItem) {
  return modelGroupChannelKey(item.site_id, item.channel_id);
}

type FormItemMember = {
  key: string;
  channelKey: string;
  items: FormItem[];
};

function groupFormItemsByMember(items: FormItem[]): FormItemMember[] {
  const membersByKey = new Map<string, FormItemMember>();
  for (const item of items) {
    const key = formItemMemberKey(item);
    let member = membersByKey.get(key);
    if (!member) {
      member = {
        key,
        channelKey: formItemChannelKey(item),
        items: [],
      };
      membersByKey.set(key, member);
    }
    member.items.push(item);
  }
  return Array.from(membersByKey.values());
}

function groupFormItemsByChannel(items: FormItem[]) {
  const channels = new Map<
    string,
    { key: string; members: FormItemMember[] }
  >();
  for (const member of groupFormItemsByMember(items)) {
    let channel = channels.get(member.channelKey);
    if (!channel) {
      channel = { key: member.channelKey, members: [] };
      channels.set(member.channelKey, channel);
    }
    channel.members.push(member);
  }
  return Array.from(channels.values());
}

/**
 * Remove matching members; ones that rules or placement would add back become
 * exclusions so the removal sticks, the same way the backend saves them.
 */
function removeFormItems(
  form: FormState,
  matches: (item: FormItem) => boolean,
  isAutoJoined: (form: FormState, modelName: string) => boolean,
): FormState {
  const removedItems = form.items.filter(matches);
  if (!removedItems.length) return form;
  const excludedItems = removedItems
    .filter(
      (item) =>
        item.state !== "invalid" &&
        (item.source !== "manual" || isAutoJoined(form, item.model_name)),
    )
    .map((item) => ({ ...item, state: null, reasons: [] }));
  return {
    ...form,
    items: form.items.filter((item) => !matches(item)),
    excluded_items: [...form.excluded_items, ...excludedItems],
  };
}

/** Derive folded members and manage editor member operations. */
export function useGroupMembers(
  form: FormState,
  evaluatedItems: ModelGroup["items"],
  setForm: Dispatch<SetStateAction<FormState>>,
  memberStatusFilter: MemberStatusFilter,
  isAutoJoined: (form: FormState, modelName: string) => boolean,
) {
  const foldedMembers = useMemo(
    () => foldGroupMembers(form.items, evaluatedItems),
    [evaluatedItems, form.items],
  );
  const excludedMembers = useMemo(
    () => foldGroupMembers(form.excluded_items, []),
    [form.excluded_items],
  );
  const visibleFoldedMembers = useMemo(() => {
    return foldedMembers.flatMap((member, index) => {
      const hasProblem =
        member.invalid_item_count > 0 || member.unavailable_item_count > 0;
      const isVisible =
        memberStatusFilter === "all" ||
        (memberStatusFilter === "enabled" && member.ready_item_count > 0) ||
        (memberStatusFilter === "disabled" &&
          member.ready_item_count < member.subItems.length) ||
        (memberStatusFilter === "problem" && hasProblem);
      return isVisible ? [{ member, index }] : [];
    });
  }, [foldedMembers, memberStatusFilter]);
  const channelGroups = useMemo(
    () =>
      groupFoldedMembersByChannel(
        foldedMembers.map((member, index) => ({ member, index })),
      ),
    [foldedMembers],
  );
  const visibleChannelGroups = useMemo(() => {
    const visibleKeys = new Set(
      visibleFoldedMembers.map(({ member }) => member.key),
    );
    return channelGroups.flatMap((channel) => {
      const members = channel.members.filter(({ member }) =>
        visibleKeys.has(member.key),
      );
      return members.length ? [{ ...channel, members }] : [];
    });
  }, [channelGroups, visibleFoldedMembers]);
  const disabledItemCount = foldedMembers.reduce(
    (count, member) => count + member.disabled_item_count,
    0,
  );
  const invalidItemCount = foldedMembers.reduce(
    (count, member) => count + member.invalid_item_count,
    0,
  );

  function setItemsEnabled(
    enabled: boolean,
    matches: (item: FormItem) => boolean,
  ) {
    setForm((current) => {
      let changed = false;
      const items = current.items.map((item) => {
        if (!matches(item) || item.enabled === enabled) return item;
        changed = true;
        return { ...item, enabled, state: null, reasons: [] };
      });
      return changed ? { ...current, items } : current;
    });
  }

  function removeFoldedMember(foldKey: string) {
    setForm((current) =>
      removeFormItems(
        current,
        (item) => formItemMemberKey(item) === foldKey,
        isAutoJoined,
      ),
    );
  }

  /** Bring an excluded member back at the group's insert position. */
  function restoreExcludedMember(foldKey: string) {
    setForm((current) => {
      const restoredItems = current.excluded_items.filter(
        (item) => formItemMemberKey(item) === foldKey,
      );
      if (!restoredItems.length) return current;
      return {
        ...current,
        items: insertNewMembers(
          current.items,
          // Exclusions are stored disabled; bringing one back turns it on.
          restoredItems.map((item) => ({
            ...item,
            enabled: true,
            state: null,
            reasons: [],
          })),
          current.new_member_position,
        ),
        excluded_items: current.excluded_items.filter(
          (item) => formItemMemberKey(item) !== foldKey,
        ),
      };
    });
  }

  function toggleFoldedMember(foldKey: string, enabled: boolean) {
    setItemsEnabled(enabled, (item) => formItemMemberKey(item) === foldKey);
  }

  function toggleChannelMembers(channelKey: string, enabled: boolean) {
    setItemsEnabled(enabled, (item) => formItemChannelKey(item) === channelKey);
  }

  function moveFoldedMember(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const members = groupFormItemsByMember(current.items);
      const nextMembers = moveItems(members, fromIndex, toIndex);
      if (nextMembers === members) return current;
      return {
        ...current,
        items: nextMembers.flatMap((member) => member.items),
      };
    });
  }

  function moveChannelGroup(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const channels = groupFormItemsByChannel(current.items);
      const nextChannels = moveItems(channels, fromIndex, toIndex);
      if (nextChannels === channels) return current;
      return {
        ...current,
        items: nextChannels.flatMap((channel) =>
          channel.members.flatMap((member) => member.items),
        ),
      };
    });
  }

  function moveFoldedMemberWithinChannel(
    channelKey: string,
    fromIndex: number,
    toIndex: number,
  ) {
    setForm((current) => {
      const channels = groupFormItemsByChannel(current.items);
      const channelIndex = channels.findIndex(
        (channel) => channel.key === channelKey,
      );
      if (channelIndex < 0) return current;
      const channel = channels[channelIndex];
      const nextMembers = moveItems(channel.members, fromIndex, toIndex);
      if (nextMembers === channel.members) return current;
      const nextChannels = channels.slice();
      nextChannels[channelIndex] = { ...channel, members: nextMembers };
      return {
        ...current,
        items: nextChannels.flatMap((item) =>
          item.members.flatMap((member) => member.items),
        ),
      };
    });
  }

  function clearMembers() {
    setForm((current) => removeFormItems(current, () => true, isAutoJoined));
  }

  function setAllMembersEnabled(enabled: boolean) {
    setItemsEnabled(enabled, () => true);
  }

  function removeDisabledMembers() {
    setForm((current) =>
      removeFormItems(current, (item) => !item.enabled, isAutoJoined),
    );
  }

  function removeInvalidItems() {
    const keysToRemove = new Set(
      foldedMembers
        .flatMap((member) => member.subItems)
        .filter((item) => item.state === "invalid")
        .map((item) => modelGroupItemKey(item)),
    );
    if (!keysToRemove.size) return;
    setForm((current) =>
      removeFormItems(
        current,
        (item) => keysToRemove.has(modelGroupItemKey(item)),
        isAutoJoined,
      ),
    );
  }

  return {
    clearMembers,
    disabledItemCount,
    excludedMembers,
    foldedMembers,
    invalidItemCount,
    moveChannelGroup,
    moveFoldedMember,
    moveFoldedMemberWithinChannel,
    removeDisabledMembers,
    removeFoldedMember,
    removeInvalidItems,
    restoreExcludedMember,
    setAllMembersEnabled,
    toggleChannelMembers,
    toggleFoldedMember,
    visibleChannelGroups,
    visibleFoldedMembers,
  };
}
