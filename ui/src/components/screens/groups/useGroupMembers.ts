"use client";

import { useMemo, type Dispatch, type SetStateAction } from "react";
import { foldGroupMembers } from "./groupScreenData";
import {
  itemKey,
  modelFoldKey,
  moveItems,
  protocolConfigIdFromChannelId,
  type FormItem,
  type FormState,
} from "./modelGroupUtils";

/** Derive folded members and manage editor member operations. */
export function useGroupMembers(
  form: FormState,
  setForm: Dispatch<SetStateAction<FormState>>,
  showEnabledOnly: boolean,
) {
  const foldedMembers = useMemo(
    () => foldGroupMembers(form.items, form.protocols),
    [form.items, form.protocols],
  );
  const visibleFoldedMembers = useMemo(() => {
    if (!showEnabledOnly) {
      return foldedMembers.map((member, index) => ({ member, index }));
    }
    return foldedMembers.flatMap((member, index) =>
      member.enabled ? [{ member, index }] : [],
    );
  }, [foldedMembers, showEnabledOnly]);
  const invalidSelectedMemberCount = useMemo(
    () => foldedMembers.filter((member) => member.invalid).length,
    [foldedMembers],
  );

  function removeFoldedMember(foldKey: string) {
    setForm((current) => {
      const keysToRemove = new Set<string>();
      for (const item of current.items) {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        if (
          modelFoldKey(
            protocolConfigId,
            item.credential_id,
            item.model_name,
          ) === foldKey
        ) {
          keysToRemove.add(itemKey(item));
        }
      }
      return {
        ...current,
        items: current.items.filter((item) => !keysToRemove.has(itemKey(item))),
      };
    });
  }

  function toggleFoldedMember(foldKey: string, enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        const key = modelFoldKey(
          protocolConfigId,
          item.credential_id,
          item.model_name,
        );
        return key === foldKey ? { ...item, enabled } : item;
      }),
    }));
  }

  function moveFoldedMember(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const memberOrder = new Map<string, number>();
      const itemsByMember = new Map<string, FormItem[]>();
      for (const item of current.items) {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        const key = modelFoldKey(
          protocolConfigId,
          item.credential_id,
          item.model_name,
        );
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

  function setAllMembersEnabled(enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => ({ ...item, enabled })),
    }));
  }

  function removeInvalidItems() {
    const invalidKeys = new Set(
      foldedMembers
        .filter((member) => member.invalid)
        .map((member) => member.key),
    );
    setForm((current) => ({
      ...current,
      items: current.items.filter((item) => {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        return !invalidKeys.has(
          modelFoldKey(protocolConfigId, item.credential_id, item.model_name),
        );
      }),
    }));
  }

  return {
    foldedMembers,
    invalidSelectedMemberCount,
    moveFoldedMember,
    removeFoldedMember,
    removeInvalidItems,
    setAllMembersEnabled,
    toggleFoldedMember,
    visibleFoldedMembers,
  };
}
