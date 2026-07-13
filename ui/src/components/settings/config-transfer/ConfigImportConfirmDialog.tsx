import {
  CalendarClock,
  Database,
  KeyRound,
  ScrollText,
  Settings2,
  Upload,
  Waypoints,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/Item";
import type { ConfigBackupDump } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

/** Confirm replacement of the current configuration from a backup. */
export function ConfigImportConfirmDialog({
  open,
  onOpenChange,
  selectedFile,
  preview,
  isImporting,
  locale,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedFile: File | null;
  preview: ConfigBackupDump | null;
  isImporting: boolean;
  locale: Locale;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {titleForLocale(locale, "确认导入备份", "Confirm backup import")}
          </DialogTitle>
          <DialogDescription>
            {titleForLocale(
              locale,
              "当前实例中的相关配置会被备份文件覆盖，请确认文件内容无误后继续。",
              "The related configuration in this instance will be overwritten by the backup file.",
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <Item variant="muted">
            <ItemContent>
              <ItemTitle>
                {selectedFile?.name ??
                  titleForLocale(locale, "未选择文件", "No file selected")}
              </ItemTitle>
              <ItemDescription>
                {preview
                  ? titleForLocale(
                      locale,
                      `将覆盖 ${preview.sites.length} 个渠道、${preview.groups.length} 个模型组`,
                      `Will overwrite ${preview.sites.length} channels and ${preview.groups.length} model groups`,
                    )
                  : titleForLocale(
                      locale,
                      "将按备份内容执行覆盖导入",
                      "Will perform an overwrite import based on the backup contents",
                    )}
              </ItemDescription>
            </ItemContent>
          </Item>

          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">
              <Settings2 data-icon="inline-start" />
              {titleForLocale(locale, "设置", "Settings")}
            </Badge>
            <Badge variant="outline">
              <Waypoints data-icon="inline-start" />
              {titleForLocale(locale, "渠道", "Channels")}
            </Badge>
            <Badge variant="outline">
              <Database data-icon="inline-start" />
              {titleForLocale(locale, "模型组", "Model groups")}
            </Badge>
            <Badge variant="outline">
              <Database data-icon="inline-start" />
              {titleForLocale(locale, "统计数据", "Stats")}
            </Badge>
            <Badge variant="outline">
              <CalendarClock data-icon="inline-start" />
              {titleForLocale(locale, "定时任务", "Cron jobs")}
            </Badge>
            {preview?.include_gateway_api_keys ? (
              <Badge variant="outline">
                <KeyRound data-icon="inline-start" />
                {titleForLocale(locale, "网关 API Key", "Gateway API keys")}
              </Badge>
            ) : null}
            {preview?.include_request_logs ? (
              <Badge variant="outline">
                <ScrollText data-icon="inline-start" />
                {titleForLocale(locale, "请求日志", "Request logs")}
              </Badge>
            ) : null}
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isImporting}
          >
            {titleForLocale(locale, "取消", "Cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirm}
            disabled={isImporting}
          >
            <Upload data-icon="inline-start" />
            {isImporting
              ? titleForLocale(locale, "导入中...", "Importing...")
              : titleForLocale(locale, "确认覆盖导入", "Confirm import")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
