import type { Dispatch, SetStateAction } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import type { Site } from "@/lib/api";
import type { Locale } from "./channelShared";
import { siteSubtitle } from "./channelShared";

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
  return (
    <Dialog
      open={Boolean(deleteTarget)}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
    >
      <AppDialogContent
        className="max-w-lg"
        title={locale === "zh-CN" ? "确认删除渠道" : "Delete channel"}
        description={
          locale === "zh-CN"
            ? "删除后该渠道下的组合、模型和模型组成员会一起移除。"
            : "Combinations, models, and group members under this channel will be removed together."
        }
      >
        <div className="grid gap-5">
          <div className="rounded-md border bg-muted/30 p-4">
            <strong className="text-foreground">{deleteTarget?.name}</strong>
            <p className="mt-2 text-xs text-muted-foreground">
              {deleteTarget ? siteSubtitle(deleteTarget, locale) : ""}
            </p>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => deleteTarget && void removeSite(deleteTarget)}
              disabled={busyId === deleteTarget?.id}
            >
              {busyId === deleteTarget?.id
                ? locale === "zh-CN"
                  ? "删除中..."
                  : "Deleting..."
                : locale === "zh-CN"
                  ? "确认删除"
                  : "Delete"}
            </Button>
          </div>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
