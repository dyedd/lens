import { Badge } from "@/components/ui/Badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { Locale } from "./channelTypes";

type Props = {
  /** Distinct keys serving the row, in display order. */
  keys: Array<{ id: string; label: string }>;
  /** Keys that could serve the row; when all of them do, one badge says so. */
  totalCount: number;
  /** Tooltip lines, one per key and URL pair. */
  details: string[];
  locale: Locale;
};

/** Shows which keys serve one model row, with details in a tooltip. */
export function CredentialBadges({ keys, totalCount, details, locale }: Props) {
  if (!keys.length) {
    return <span className="text-xs text-muted-foreground">-</span>;
  }
  const coversAllKeys = totalCount > 1 && keys.length >= totalCount;
  const hiddenCount = keys.length - 2;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex h-7 min-w-0 items-center gap-1">
          {coversAllKeys ? (
            <Badge variant="secondary">
              {locale === "zh-CN"
                ? `全部 ${totalCount} 个`
                : `All ${totalCount}`}
            </Badge>
          ) : (
            keys.slice(0, 2).map((key) => (
              <Badge
                key={key.id}
                variant="secondary"
                className="max-w-[60px] shrink px-1.5"
              >
                <span className="truncate">{key.label}</span>
              </Badge>
            ))
          )}
          {!coversAllKeys && hiddenCount > 0 ? (
            <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">
              +{hiddenCount}
            </span>
          ) : null}
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="flex-col items-start gap-0.5">
        {details.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </TooltipContent>
    </Tooltip>
  );
}
