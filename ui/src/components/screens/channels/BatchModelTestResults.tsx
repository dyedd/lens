import { Badge } from "@/components/ui/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { cn } from "@/lib/utils";
import { compactProtocolLabel, protocolBadgeClassName } from "@/lib/protocols";
import { batchTestStatusLabel, batchTestStatusVariant } from "./channelShared";
import type { BatchModelTestRow, Locale } from "./channelShared";

type Props = {
  rows: BatchModelTestRow[];
  locale: Locale;
};

/** Renders batch model test result rows. */
export function BatchModelTestResults({ rows, locale }: Props) {
  if (!rows.length) return null;
  return (
    <div className="overflow-hidden rounded-md border">
      <div className="border-b px-3 py-2 text-sm font-medium">
        {locale === "zh-CN" ? "测试结果" : "Test results"}
      </div>
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
                      variant="outline"
                      className={cn(
                        "max-w-[120px] truncate text-xs",
                        protocolBadgeClassName(row.protocol),
                      )}
                    >
                      {compactProtocolLabel(row.protocol)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={batchTestStatusVariant(row.status)}>
                      {batchTestStatusLabel(row.status, locale)}
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
