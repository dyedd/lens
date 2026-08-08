"use client";

import { Info, RefreshCcw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
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
import type {
  ChannelModelSyncResponse,
  ChannelModelSyncResultItem,
} from "@/lib/api";
import type { Locale } from "./channelShared";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locale: Locale;
  result: ChannelModelSyncResponse | null;
  syncing: boolean;
  onConfirm: () => void;
};

function statusLabel(
  locale: Locale,
  status: ChannelModelSyncResultItem["status"],
) {
  const labels: Record<ChannelModelSyncResultItem["status"], [string, string]> =
    {
      updated: ["已更新", "Updated"],
      unchanged: ["无变更", "Unchanged"],
      failed: ["失败", "Failed"],
    };
  const [zh, en] = labels[status];
  return locale === "zh-CN" ? zh : en;
}

function statusVariant(status: ChannelModelSyncResultItem["status"]) {
  if (status === "failed") return "destructive" as const;
  if (status === "updated") return "secondary" as const;
  return "outline" as const;
}

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
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">
                  {locale === "zh-CN"
                    ? `${result.eligible_target_count} 个目标`
                    : `${result.eligible_target_count} targets`}
                </Badge>
                <Badge variant="secondary">
                  {locale === "zh-CN"
                    ? `${result.updated_target_count} 个更新`
                    : `${result.updated_target_count} updated`}
                </Badge>
                <Badge variant="outline">
                  {locale === "zh-CN"
                    ? `${result.unchanged_target_count} 个无变更`
                    : `${result.unchanged_target_count} unchanged`}
                </Badge>
                {result.failed_target_count ? (
                  <Badge variant="destructive">
                    {locale === "zh-CN"
                      ? `${result.failed_target_count} 个失败`
                      : `${result.failed_target_count} failed`}
                  </Badge>
                ) : null}
              </div>
            ) : null}
            {syncing && !result ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                {locale === "zh-CN"
                  ? "正在生成预览..."
                  : "Generating preview..."}
              </div>
            ) : null}
            {result?.eligible_target_count === 0 ? (
              <Alert>
                <Info />
                <AlertTitle>
                  {locale === "zh-CN"
                    ? "没有可同步目标"
                    : "No eligible sync targets"}
                </AlertTitle>
                <AlertDescription>
                  {locale === "zh-CN"
                    ? "请先在渠道组合中开启「同步」，或把模型来源改为同步，并确保地址、密钥和客户端协议均已启用。"
                    : "Click Sync in a channel combination or switch models to synced, and make sure the URL, key, and client protocol are enabled."}
                </AlertDescription>
              </Alert>
            ) : null}
            {result?.eligible_target_count ? (
              <div className="max-h-[420px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        {locale === "zh-CN" ? "同步目标" : "Sync target"}
                      </TableHead>
                      <TableHead>
                        {locale === "zh-CN" ? "状态" : "Status"}
                      </TableHead>
                      <TableHead>
                        {locale === "zh-CN" ? "变更" : "Changes"}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.items.map((item) => (
                      <TableRow
                        key={`${item.protocol_config_id}:${item.credential_id}:${item.protocol}`}
                      >
                        <TableCell className="align-top">
                          <div className="font-medium">{item.channel_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {`${item.protocol_config_name} · ${item.credential_name || item.credential_id} · ${item.protocol}`}
                          </div>
                        </TableCell>
                        <TableCell className="align-top">
                          <Badge variant={statusVariant(item.status)}>
                            {statusLabel(locale, item.status)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          <div className="flex flex-col gap-1">
                            {item.status === "failed" ? (
                              <div className="text-destructive">
                                {(locale === "zh-CN" ? "失败：" : "Failed: ") +
                                  item.error}
                              </div>
                            ) : null}
                            {item.warning ? (
                              <div className="text-muted-foreground">
                                {(locale === "zh-CN" ? "警告：" : "Warning: ") +
                                  item.warning}
                              </div>
                            ) : null}
                            {item.added.map((name) => (
                              <div key={`a-${name}`}>{`+ ${name}`}</div>
                            ))}
                            {item.removed.map((name) => (
                              <div
                                key={`r-${name}`}
                                className="text-destructive"
                              >
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
                            {item.status !== "failed" &&
                            !item.added.length &&
                            !item.removed.length &&
                            !item.group_added.length &&
                            !item.warning ? (
                              <div className="text-muted-foreground">
                                {locale === "zh-CN" ? "无变更" : "No changes"}
                              </div>
                            ) : null}
                          </div>
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
                disabled={
                  syncing ||
                  !result ||
                  result.eligible_target_count === 0 ||
                  !hasChanges
                }
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
