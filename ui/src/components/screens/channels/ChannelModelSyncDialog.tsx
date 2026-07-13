"use client";

import { RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { ChannelModelSyncResponse } from "@/lib/api";
import type { Locale } from "./channelShared";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locale: Locale;
  result: ChannelModelSyncResponse | null;
  syncing: boolean;
  onConfirm: () => void;
};

/** Renders a channel model-sync preview and confirmation flow. */
export function ChannelModelSyncDialog({
  open,
  onOpenChange,
  locale,
  result,
  syncing,
  onConfirm,
}: Props) {
  const hasChanges = (result?.items ?? []).some(
    (item) =>
      item.added.length > 0 ||
      item.removed.length > 0 ||
      item.group_added.length > 0,
  );
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && syncing) return;
        onOpenChange(nextOpen);
      }}
    >
      {open ? (
        <AppDialogContent
          className="max-w-2xl"
          title={locale === "zh-CN" ? "同步预览" : "Sync preview"}
        >
          <div className="grid gap-4">
            {result ? (
              <div className="rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                {locale === "zh-CN"
                  ? `将同步 ${result.synced_channel_count} 个渠道，跳过 ${result.skipped_channel_count} 个`
                  : `${result.synced_channel_count} channels to sync, ${result.skipped_channel_count} skipped`}
              </div>
            ) : null}
            {syncing && !result ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                {locale === "zh-CN"
                  ? "正在生成预览..."
                  : "Generating preview..."}
              </div>
            ) : null}
            {result ? (
              <div className="max-h-[420px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        {locale === "zh-CN" ? "渠道" : "Channel"}
                      </TableHead>
                      <TableHead>
                        {locale === "zh-CN" ? "变更" : "Changes"}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.items.map((item) => (
                      <TableRow key={item.protocol_config_id}>
                        <TableCell className="align-top font-medium">
                          {item.channel_name}
                        </TableCell>
                        <TableCell className="space-y-1 text-xs">
                          {!item.success ? (
                            <div className="text-destructive">
                              {(locale === "zh-CN" ? "失败：" : "Failed: ") +
                                item.error}
                            </div>
                          ) : null}
                          {item.success && item.warning ? (
                            <div className="text-amber-600">
                              {(locale === "zh-CN" ? "警告：" : "Warning: ") +
                                item.warning}
                            </div>
                          ) : null}
                          {item.added.map((name) => (
                            <div key={`a-${name}`} className="text-emerald-600">
                              {`+ ${name}`}
                            </div>
                          ))}
                          {item.removed.map((name) => (
                            <div key={`r-${name}`} className="text-destructive">
                              {`- ${name}`}
                            </div>
                          ))}
                          {item.group_added.map((change) => (
                            <div
                              key={`g-${change.group_name}-${change.model_name}`}
                              className="text-muted-foreground"
                            >
                              {`↳ ${change.model_name} → ${change.group_name}`}
                            </div>
                          ))}
                          {item.success &&
                          !item.added.length &&
                          !item.removed.length &&
                          !item.warning ? (
                            <div className="text-muted-foreground">
                              {locale === "zh-CN" ? "无变更" : "No changes"}
                            </div>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={syncing}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                onClick={onConfirm}
                disabled={syncing || !result || !hasChanges}
              >
                <RefreshCcw
                  data-icon="inline-start"
                  className={syncing ? "animate-spin" : undefined}
                />
                {locale === "zh-CN" ? "确认同步" : "Confirm sync"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}
