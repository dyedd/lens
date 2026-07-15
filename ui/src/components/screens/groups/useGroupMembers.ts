"use client";

import { useMemo, type Dispatch, type SetStateAction } from "react";
import type { ModelGroup } from "@/lib/api";
import { foldGroupMembers } from "./groupScreenData";
import {
  itemKey,
  modelFoldKey,
  moveItems,
  type FormItem,
  type FormState,
  type MemberStatusFilter,
} from "./modelGroupUtils";

function formItemMemberKey(item: FormItem) {
  return modelFoldKey(
    item.protocol_config_id,
    item.credential_id,
    item.model_name,
  );
}

/** Derive folded members and manage editor member operations. */
export function useGroupMembers(
  form: FormState,
  evaluatedItems: ModelGroup["items"],
  setForm: Dispatch<SetStateAction<FormState>>,
  memberStatusFilter: MemberStatusFilter,
) {
  const foldedMembers = useMemo(
    () => foldGroupMembers(form.items, evaluatedItems),
    [evaluatedItems, form.items],
  );
  const visibleFoldedMembers = useMemo(() => {
    return foldedMembers.flatMap((member, index) => {
      const hasProblem =
        member.invalid_item_count > 0 || member.unavailable_item_count > 0;
      const isVisible =
        memberStatusFilter === "all" ||
        (memberStatusFilter === "enabled" && member.enabled_item_count > 0) ||
        (memberStatusFilter === "disabled" && member.disabled_item_count > 0) ||
        (memberStatusFilter === "problem" && hasProblem);
      return isVisible ? [{ member, index }] : [];
    });
  }, [foldedMembers, memberStatusFilter]);
  const disabledItemCount = foldedMembers.reduce(
    (count, member) => count + member.disabled_item_count,
    0,
  );
  const invalidItemCount = foldedMembers.reduce(
    (count, member) => count + member.invalid_item_count,
    0,
  );
  const unavailableItemCount = foldedMembers.reduce(
    (count, member) => count + member.unavailable_item_count,
    0,
  );

  function removeFoldedMember(foldKey: string) {
    setForm((current) => ({
      ...current,
      items: current.items.filter(
        (item) => formItemMemberKey(item) !== foldKey,
      ),
    }));
  }

  function toggleFoldedMember(foldKey: string, enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) =>
        formItemMemberKey(item) === foldKey
          ? { ...item, enabled, state: null, reasons: [] }
          : item,
      ),
    }));
  }

  function moveFoldedMember(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const memberOrder = new Map<string, number>();
      const itemsByMember = new Map<string, FormItem[]>();
      for (const item of current.items) {
        const key = formItemMemberKey(item);
        if (!itemsByMember.has(key)) {
          memberOrder.set(key, memberOrder.size);
          itemsByMember.set(key, []);
        }
        itemsByMember.get(key)!.push(item);
      }
      const orderedKeys = Array.from(memberOrder.entries())
        .sort((left, right) => left[1] - right[1])
        .map(([key]) => key);
      const nextKeys = moveItems(orderedKeys, fromIndex, toIndex);
      if (nextKeys === orderedKeys) return current;
      return {
        ...current,
        items: nextKeys.flatMap((key) => itemsByMember.get(key) ?? []),
      };
    });
  }

  function clearMembers() {
    setForm((current) =>
      current.items.length ? { ...current, items: [] } : current,
    );
  }

  function setAllMembersEnabled(enabled: boolean) {
    setForm((current) => {
      if (!current.items.some((item) => item.enabled !== enabled)) {
        return current;
      }
      return {
        ...current,
        items: current.items.map((item) => ({
          ...item,
          enabled,
          state: null,
          reasons: [],
        })),
      };
    });
  }

  function removeDisabledMembers() {
    setForm((current) => {
      const items = current.items.filter((item) => item.enabled);
      return items.length === current.items.length
        ? current
        : { ...current, items };
    });
  }

  function removeItemsByState(state: "invalid" | "unavailable") {
    const keysToRemove = new Set(
      foldedMembers
        .flatMap((member) => member.subItems)
        .filter((item) => item.state === state)
        .map((item) => itemKey(item)),
    );
    if (!keysToRemove.size) return;
    setForm((current) => ({
      ...current,
      items: current.items.filter((item) => !keysToRemove.has(itemKey(item))),
    }));
  }

  function removeInvalidItems() {
    removeItemsByState("invalid");
  }

  function removeUnavailableItems() {
    removeItemsByState("unavailable");
  }

  return {
    clearMembers,
    disabledItemCount,
    foldedMembers,
    invalidItemCount,
    moveFoldedMember,
    removeDisabledMembers,
    removeFoldedMember,
    removeInvalidItems,
    removeUnavailableItems,
    setAllMembersEnabled,
    toggleFoldedMember,
    unavailableItemCount,
    visibleFoldedMembers,
  };
}
