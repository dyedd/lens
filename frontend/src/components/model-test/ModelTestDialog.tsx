import { useEffect, useState } from "react";
import {
  type ModelTestDialogTarget,
  modelTestProtocols,
} from "@/components/model-test/modelTestSession";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/ToggleGroup";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { ModelTestMode, SiteModelTestResult } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import type { Locale } from "@/lib/I18nContext";
import { formatJson } from "@/lib/jsonFormatting";
import { protocolLabel } from "@/lib/protocols";

export type ModelProbeItem = {
  target: ModelTestDialogTarget;
  result: SiteModelTestResult | null;
  protocol: ProtocolKind | null;
  protocols: ProtocolKind[];
  onProtocolChange: (protocol: ProtocolKind) => void;
  onDelete?: () => void;
};

type Props = {
  items: ModelProbeItem[];
  locale: Locale;
  testing: boolean;
  onClose: () => void;
  mode: ModelTestMode;
  onModeChange: (mode: ModelTestMode) => void;
  onRun: () => void;
  onProtocolChangeAll?: (protocol: ProtocolKind) => void;
  targetName?: string;
  credentialOptions?: Array<{ value: string; label: string }>;
  credentialValue?: string;
  onCredentialChange?: (value: string) => void;
};

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 grid-cols-[88px_minmax(0,1fr)] gap-3 text-xs leading-5">
      <span className="text-muted-foreground">{label}</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="min-w-0 truncate">{value || "-"}</span>
        </TooltipTrigger>
        {value ? (
          <TooltipContent className="max-w-sm break-all">
            {value}
          </TooltipContent>
        ) : null}
      </Tooltip>
    </div>
  );
}

function DebugBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <pre className="max-h-52 overflow-auto rounded-md border border-border/60 bg-background p-3 font-mono text-xs leading-5 whitespace-pre-wrap break-all text-foreground/80">
        {value || "-"}
      </pre>
    </div>
  );
}

export function ModelTestDialog({
  items,
  locale,
  testing,
  onClose,
  mode,
  onModeChange,
  onRun,
  onProtocolChangeAll,
  targetName,
  credentialOptions = [],
  credentialValue,
  onCredentialChange,
}: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  useEffect(() => {
    if (!testing) return;
    const startedAt = performance.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds((performance.now() - startedAt) / 1000);
    }, 250);
    return () => window.clearInterval(timer);
  }, [testing]);
  const testItems = items.map((item) => ({
    ...item,
    protocols: modelTestProtocols(item.protocols, mode),
  }));
  const activeItem = testItems[Math.min(activeIndex, items.length - 1)];
  const { target, result, protocol, protocols, onProtocolChange, onDelete } =
    activeItem ?? {};
  const isChinese = locale === "zh-CN";
  const allProtocols = Array.from(
    new Set(
      testItems.flatMap((item) =>
        item.protocols.length > 1 ? item.protocols : [],
      ),
    ),
  );
  const testableCount = testItems.filter(
    (item) => item.protocol !== null,
  ).length;
  const canRun =
    testableCount > 0 &&
    testItems.every(
      (item) => !item.protocols.length || item.protocol !== null,
    ) &&
    !testing;
  const debug = result?.debug;
  const requestHeaders = debug
    ? JSON.stringify(debug.request.headers, null, 2)
    : "";
  const requestBody = debug ? JSON.stringify(debug.request.body, null, 2) : "";
  const responseHeaders = debug
    ? JSON.stringify(debug.response.headers, null, 2)
    : "";
  const responseBody =
    (formatJson(debug?.response.body || "") ?? debug?.response.body) ||
    result?.error_message ||
    "";

  return (
    <>
      <Dialog
        open
        onOpenChange={(open) => !open && !confirmDeleteOpen && onClose()}
      >
        <DialogContent className="flex max-h-[min(88vh,720px)] w-[calc(100vw-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[600px]">
          <DialogHeader className="shrink-0 px-5 pb-4 pt-5 pr-12">
            <DialogTitle>{isChinese ? "测试模型" : "Test model"}</DialogTitle>
            <DialogDescription className="truncate">
              {[targetName, target?.modelName].filter(Boolean).join(" · ") ||
                "-"}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-5">
            <FieldGroup className="gap-3 border-b border-border/60 pb-4">
              <div className="flex flex-wrap items-center gap-3">
                <ToggleGroup
                  type="single"
                  value={mode}
                  onValueChange={(value) => {
                    if (value) onModeChange(value as ModelTestMode);
                  }}
                  disabled={testing}
                  aria-label={isChinese ? "测试方式" : "Test mode"}
                  className="shrink-0"
                >
                  {(["direct", "codex", "claude"] as const).map((value) => (
                    <ToggleGroupItem
                      key={value}
                      value={value}
                      disabled={
                        !items.some(
                          (item) =>
                            modelTestProtocols(item.protocols, value).length,
                        )
                      }
                    >
                      {value === "direct"
                        ? isChinese
                          ? "直接发送"
                          : "Direct"
                        : value === "codex"
                          ? "Codex"
                          : "Claude"}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
                {items.length === 1 && credentialOptions.length > 1 ? (
                  <Field
                    orientation="horizontal"
                    data-disabled={testing}
                    className="grid min-w-0 flex-[1_1_280px] grid-cols-[88px_minmax(0,1fr)] gap-3 sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-2"
                  >
                    <FieldLabel
                      htmlFor="model-test-credential"
                      className="text-xs font-normal whitespace-nowrap text-muted-foreground"
                    >
                      API Key
                    </FieldLabel>
                    <Select
                      value={credentialValue ?? ""}
                      onValueChange={(value) => onCredentialChange?.(value)}
                      disabled={testing}
                    >
                      <SelectTrigger
                        id="model-test-credential"
                        aria-label={isChinese ? "API Key" : "API key"}
                        className="h-8 min-w-0 [&_[data-slot=select-value]]:truncate"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          {credentialOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                ) : null}
              </div>
              {items.length > 1 &&
              onProtocolChangeAll &&
              allProtocols.length ? (
                <div className="flex items-center justify-end gap-2 px-3">
                  <span className="text-sm text-muted-foreground">
                    {isChinese ? "全部设为" : "Set all"}
                  </span>
                  <Select
                    value=""
                    onValueChange={(value) =>
                      onProtocolChangeAll(value as ProtocolKind)
                    }
                    disabled={testing}
                  >
                    <SelectTrigger
                      className="h-7 w-36"
                      aria-label={
                        isChinese
                          ? "全部使用此协议"
                          : "Use this protocol for all"
                      }
                    >
                      <SelectValue
                        placeholder={isChinese ? "选择协议" : "Choose protocol"}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {allProtocols.map((value) => (
                          <SelectItem key={value} value={value}>
                            {protocolLabel(value, locale)}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              ) : null}
              {items.length > 1 ? (
                <div className="max-h-36 overflow-y-auto rounded-md bg-muted/35 p-1">
                  {testItems.map((item, index) => (
                    <div
                      key={`${item.target.modelName}-${index}`}
                      className="flex min-w-0 items-center gap-2 px-2 py-1 text-xs"
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className={cn(
                              "min-w-0 flex-1 truncate text-left",
                              index === activeIndex
                                ? "font-medium text-foreground"
                                : "text-muted-foreground",
                            )}
                            onClick={() => setActiveIndex(index)}
                          >
                            {item.target.modelName} · {item.target.upstreamName}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-sm break-all">
                          {item.target.modelName} · {item.target.upstreamName}
                        </TooltipContent>
                      </Tooltip>
                      <span
                        className={
                          item.result?.success
                            ? "text-foreground"
                            : item.result
                              ? "text-destructive"
                              : "text-muted-foreground"
                        }
                      >
                        {!item.protocols.length
                          ? isChinese
                            ? "不支持"
                            : "Unsupported"
                          : item.result
                            ? item.result.success
                              ? isChinese
                                ? "成功"
                                : "Success"
                              : isChinese
                                ? "失败"
                                : "Failed"
                            : testing
                              ? isChinese
                                ? "等待"
                                : "Pending"
                              : "-"}
                      </span>
                      {item.result ? (
                        <span className="shrink-0 tabular-nums text-muted-foreground">
                          {(item.result.latency_ms / 1000).toFixed(2)} s
                        </span>
                      ) : null}
                      {item.protocols.length > 1 ? (
                        <Select
                          value={item.protocol ?? ""}
                          onValueChange={(value) =>
                            item.onProtocolChange(value as ProtocolKind)
                          }
                          disabled={testing}
                        >
                          <SelectTrigger
                            className="h-7 w-36 shrink-0"
                            aria-label={
                              isChinese ? "测试协议" : "Test protocol"
                            }
                          >
                            <SelectValue
                              placeholder={
                                isChinese ? "选择协议" : "Choose protocol"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {item.protocols.map((value) => (
                                <SelectItem key={value} value={value}>
                                  {protocolLabel(value, locale)}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : protocols && protocols.length > 1 ? (
                <Field
                  orientation="horizontal"
                  data-disabled={testing}
                  className="grid grid-cols-[88px_minmax(0,1fr)] gap-3"
                >
                  <FieldLabel
                    htmlFor="model-test-protocol"
                    className="text-xs font-normal text-muted-foreground"
                  >
                    {isChinese ? "测试协议" : "Test protocol"}
                  </FieldLabel>
                  <Select
                    value={protocol ?? ""}
                    onValueChange={(value) =>
                      onProtocolChange?.(value as ProtocolKind)
                    }
                    disabled={testing}
                  >
                    <SelectTrigger
                      id="model-test-protocol"
                      aria-label={isChinese ? "测试协议" : "Test protocol"}
                      className="h-8 min-w-0 [&_[data-slot=select-value]]:truncate"
                    >
                      <SelectValue
                        placeholder={isChinese ? "选择协议" : "Choose protocol"}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {protocols.map((value) => (
                          <SelectItem key={value} value={value}>
                            {protocolLabel(value, locale)}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              ) : null}
              {testItems.some((item) => !item.protocols.length) ? (
                <p className="text-xs text-muted-foreground">
                  {items.length > 1
                    ? isChinese
                      ? "不支持此方式的模型会跳过。"
                      : "Models that do not support this mode will be skipped."
                    : isChinese
                      ? "此模型不支持当前测试方式"
                      : "This model does not support this test mode"}
                </p>
              ) : null}
            </FieldGroup>
            {result ? (
              <div className="mt-4 flex flex-col gap-4 pb-4">
                <div className="grid gap-x-5 gap-y-1.5 sm:grid-cols-2">
                  <Detail
                    label={isChinese ? "上游" : "Upstream"}
                    value={target?.upstreamName || "-"}
                  />
                  <Detail
                    label={isChinese ? "方法" : "Method"}
                    value={debug?.request.method || "-"}
                  />
                  <Detail
                    label={isChinese ? "路径" : "Path"}
                    value={debug?.request.path || "-"}
                  />
                  <Detail
                    label={isChinese ? "状态码" : "Status"}
                    value={String(result.status_code ?? "-")}
                  />
                  <Detail
                    label={isChinese ? "响应耗时" : "Duration"}
                    value={`${(result.latency_ms / 1000).toFixed(2)} s`}
                  />
                </div>
                {result.success && result.output_text ? (
                  <div className="whitespace-pre-wrap break-words rounded-md bg-muted/35 px-3 py-2 text-xs leading-5">
                    {result.output_text}
                  </div>
                ) : null}

                <Tabs
                  defaultValue="request"
                  className="gap-3 border-t border-border/60 pt-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span
                      className={cn(
                        "inline-flex items-center gap-2 text-xs font-medium",
                        result.success ? "text-foreground" : "text-destructive",
                      )}
                    >
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          result.success ? "bg-foreground" : "bg-destructive",
                        )}
                        aria-hidden="true"
                      />
                      {result.success
                        ? isChinese
                          ? "请求成功"
                          : "Request succeeded"
                        : isChinese
                          ? "请求失败"
                          : "Request failed"}
                    </span>
                    <TabsList>
                      <TabsTrigger value="request">
                        {isChinese ? "请求" : "Request"}
                      </TabsTrigger>
                      <TabsTrigger value="response">
                        {isChinese ? "响应" : "Response"}
                      </TabsTrigger>
                    </TabsList>
                  </div>
                  {result.error_message ? (
                    <p className="text-xs leading-5 text-muted-foreground break-words">
                      {result.error_message}
                    </p>
                  ) : null}
                  <TabsContent value="request" className="flex flex-col gap-3">
                    <DebugBlock
                      label={isChinese ? "请求头" : "Request headers"}
                      value={requestHeaders}
                    />
                    <DebugBlock
                      label={isChinese ? "内容" : "Body"}
                      value={requestBody}
                    />
                  </TabsContent>
                  <TabsContent value="response" className="flex flex-col gap-3">
                    <DebugBlock
                      label={isChinese ? "响应头" : "Response headers"}
                      value={responseHeaders}
                    />
                    <DebugBlock
                      label={isChinese ? "响应内容" : "Response body"}
                      value={responseBody}
                    />
                  </TabsContent>
                </Tabs>
              </div>
            ) : null}
          </div>

          <DialogFooter className="shrink-0 px-5 py-3">
            {testing ? (
              <span
                className="mr-auto self-center text-xs tabular-nums text-muted-foreground"
                role="timer"
              >
                {items.length > 1
                  ? isChinese
                    ? "本轮耗时"
                    : "Batch elapsed"
                  : isChinese
                    ? "已等待"
                    : "Waiting"}{" "}
                {elapsedSeconds.toFixed(1)} s
              </span>
            ) : null}
            {onDelete && !testing ? (
              <Button
                type="button"
                variant="ghost"
                className="mr-auto text-muted-foreground shadow-none"
                onClick={() => setConfirmDeleteOpen(true)}
              >
                {isChinese ? "删除模型" : "Delete model"}
              </Button>
            ) : null}
            <Button type="button" size="sm" variant="ghost" onClick={onClose}>
              {isChinese ? "关闭" : "Close"}
            </Button>
            <Button type="button" size="sm" onClick={onRun} disabled={!canRun}>
              {testing ? <Spinner /> : null}
              {items.length > 1
                ? isChinese
                  ? `测试 ${testableCount} 个模型`
                  : `Test ${testableCount} models`
                : isChinese
                  ? "开始测试"
                  : "Start test"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>{isChinese ? "删除模型" : "Delete model"}</DialogTitle>
            <DialogDescription>
              {isChinese
                ? `从当前渠道移除「${target?.modelName || "-"}」；保存后生效。`
                : `Remove "${target?.modelName || "-"}"; changes apply on save.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setConfirmDeleteOpen(false)}
            >
              {isChinese ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => {
                onDelete?.();
                setConfirmDeleteOpen(false);
                onClose();
              }}
            >
              {isChinese ? "删除" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
