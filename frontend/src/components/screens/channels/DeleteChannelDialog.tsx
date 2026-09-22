import type { Dispatch, SetStateAction } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
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
    <Dialog
      open={Boolean(deleteTarget)}
      onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}
    >
      <AppDialogContent
        className="max-w-lg"
        showCloseButton={false}
        title={locale === "zh-CN" ? "确认删除渠道" : "Delete channel"}
        description={
          locale === "zh-CN"
            ? `将删除渠道「${name}」。删除后该渠道下的协议配置、模型和模型组成员会一起移除。`
            : `Delete channel "${name}". Protocol configs, models, and group members under this channel will be removed together.`
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setDeleteTarget(null)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
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
          </>
        }
      />
    </Dialog>
  );
}
