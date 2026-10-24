import type { Dispatch, SetStateAction } from "react";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import type { Site } from "@/lib/api/sites";
import type { Locale } from "./channelTypes";

type Props = {
  deleteTarget: Site | null;
  locale: Locale;
  busyId: string | null;
  setDeleteTarget: Dispatch<SetStateAction<Site | null>>;
  removeSite: (site: Site) => void;
};

/** Renders the confirmation dialog for deleting a channel. */
export function DeleteChannelDialog({
  deleteTarget,
  locale,
  busyId,
  setDeleteTarget,
  removeSite,
}: Props) {
  const name = deleteTarget?.name ?? "";
  return (
    <ConfirmDeleteDialog
      open={Boolean(deleteTarget)}
      locale={locale}
      title={locale === "zh-CN" ? "确认删除渠道" : "Delete channel"}
      description={
        locale === "zh-CN"
          ? `删除渠道「${name}」及其协议配置、模型和模型组成员。`
          : `Delete channel "${name}" and its protocol configs, models, and group members.`
      }
      isBusy={Boolean(deleteTarget) && busyId === deleteTarget?.id}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
      onConfirm={() => deleteTarget && void removeSite(deleteTarget)}
    />
  );
}
