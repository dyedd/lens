import { Gauge } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type {
  SiteEndpointProbePayload,
  SiteEndpointProbeResult,
} from "@/lib/api/sites";
import type { FormState, Locale } from "./channelTypes";

type Props = {
  url: string;
  proxyMode: FormState["proxy_mode"];
  channelProxy: string;
  locale: Locale;
};

/** Times one endpoint from the gateway host and shows the round-trip. */
export function ChannelEndpointProbe({
  url,
  proxyMode,
  channelProxy,
  locale,
}: Props) {
  const isZh = locale === "zh-CN";
  const [probing, setProbing] = useState(false);
  const [result, setResult] = useState<SiteEndpointProbeResult | null>(null);
  const target = url.trim();

  async function probe() {
    if (!target || probing) return;
    const payload: SiteEndpointProbePayload = {
      base_url: target,
      proxy_mode: proxyMode,
      channel_proxy: channelProxy,
    };
    setProbing(true);
    setResult(null);
    try {
      setResult(
        await apiRequest<SiteEndpointProbeResult>("/admin/endpoint-probes", {
          method: "POST",
          body: JSON.stringify(payload),
        }),
      );
    } catch (error) {
      setResult({
        success: false,
        status_code: null,
        latency_ms: 0,
        error_message: getApiErrorMessage(
          error,
          isZh ? "测速失败" : "Probe failed",
        ),
      });
    } finally {
      setProbing(false);
    }
  }

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      {result ? (
        result.success ? (
          <span className="text-xs text-muted-foreground tabular-nums">
            {result.latency_ms} ms
          </span>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="max-w-24 truncate text-xs text-destructive">
                {isZh ? "失败" : "Failed"}
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">
              {result.error_message}
            </TooltipContent>
          </Tooltip>
        )
      ) : null}
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex">
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="text-muted-foreground shadow-none hover:text-foreground"
              disabled={!target || probing}
              aria-label={isZh ? "测试地址连通性" : "Test endpoint latency"}
              onClick={() => void probe()}
            >
              {probing ? <Spinner className="size-3.5" /> : <Gauge />}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          {isZh ? "测试地址连通性" : "Test endpoint latency"}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
