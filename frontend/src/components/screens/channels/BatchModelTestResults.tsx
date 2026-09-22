import type {
  BatchModelTestRow,
  BatchModelTestStatus,
} from "@/components/model-test/batchModelTestSession";
import { Badge } from "@/components/ui/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { cn } from "@/lib/classNames";
import { protocolLabel } from "@/lib/protocols";
import type { Locale } from "./channelTypes";

type Props = {
  rows: BatchModelTestRow[];
  locale: Locale;
};

function statusLabel(status: BatchModelTestStatus, locale: Locale) {
  if (status === "pending") return locale === "zh-CN" ? "等待中" : "Pending";
  if (status === "running") return locale === "zh-CN" ? "测试中" : "Running";
  if (status === "success") return locale === "zh-CN" ? "成功" : "Success";
  return locale === "zh-CN" ? "失败" : "Failed";
}

/** Renders batch model test result rows. */
export function BatchModelTestResults({ rows, locale }: Props) {
  if (!rows.length) return null;
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium">
        {locale === "zh-CN" ? "测试结果" : "Test results"}
      </h4>
      <div className="max-h-80 overflow-y-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{locale === "zh-CN" ? "模型" : "Model"}</TableHead>
              <TableHead className="w-28">
                {locale === "zh-CN" ? "协议" : "Protocol"}
              </TableHead>
              <TableHead className="w-24">
                {locale === "zh-CN" ? "状态" : "Status"}
              </TableHead>
              <TableHead className="w-28">
                {locale === "zh-CN" ? "耗时" : "Latency"}
              </TableHead>
              <TableHead>{locale === "zh-CN" ? "结果" : "Result"}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const displayMessage =
                row.message ||
                (row.status === "running"
                  ? locale === "zh-CN"
                    ? "测试中..."
                    : "Running..."
                  : "-");
              return (
                <TableRow key={row.key}>
                  <TableCell className="min-w-[180px]">
                    <div className="truncate font-medium">{row.modelName}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {row.credentialName}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="secondary"
                      className="max-w-[160px] truncate text-xs font-normal text-muted-foreground"
                    >
                      {protocolLabel(row.protocol, locale)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {statusLabel(row.status, locale)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    <div>HTTP {row.statusCode ?? "-"}</div>
                    <div>
                      {row.latencyMs === undefined ? "-" : `${row.latencyMs}ms`}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div
                      className={cn(
                        "max-h-24 min-w-[220px] overflow-y-auto whitespace-pre-wrap break-words text-xs",
                        row.status === "failed"
                          ? "text-destructive"
                          : "text-foreground",
                      )}
                    >
                      {displayMessage}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
