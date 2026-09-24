import { useState } from "react";
import type { ModelTestDialogTarget } from "@/components/model-test/modelTestSession";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SiteModelTestResult } from "@/lib/api/sites";
import { protocolLabel } from "@/lib/protocols";
import type { Locale } from "./channelTypes";

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
  prompts: string[];
  promptMode: string;
  prompt: string;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onRun: () => void;
  targetName?: string;
};

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 grid-cols-[88px_minmax(0,1fr)] gap-3 text-xs leading-5">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate" title={value}>
        {value || "-"}
      </span>
    </div>
  );
}

function DebugBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1.5">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <pre className="max-h-52 overflow-auto rounded-md border border-border/60 bg-background p-3 font-mono text-[11px] leading-5 whitespace-pre-wrap break-all text-foreground/80">
        {value || "-"}
      </pre>
    </div>
  );
}

function formatResponseBody(body: string): string {
  if (!body.trim()) return "";
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}

export function ModelTestDialog({
  items,
  locale,
  testing,
  onClose,
  prompts,
  promptMode,
  prompt,
  onPromptModeChange,
  onPromptChange,
  onRun,
  targetName,
}: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const activeItem = items[Math.min(activeIndex, items.length - 1)];
  const { target, result, protocol, protocols, onProtocolChange, onDelete } =
    activeItem ?? {};
  const isChinese = locale === "zh-CN";
  const canRun =
    Boolean(prompt.trim()) &&
    items.length > 0 &&
    items.every((item) => item.protocol !== null) &&
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
    formatResponseBody(debug?.response.body || "") ||
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
            <DialogTitle>{isChinese ? "模型测试" : "Model test"}</DialogTitle>
            <DialogDescription className="truncate">
              {[targetName, target?.modelName].filter(Boolean).join(" · ") ||
                "-"}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
            <div className="grid gap-3 border-b border-border/60 pb-4">
              {items.length > 1 ? (
                <div className="max-h-36 overflow-y-auto rounded-md bg-muted/35 p-1">
                  {items.map((item, index) => (
                    <div
                      key={`${item.target.modelName}-${index}`}
                      className="flex min-w-0 items-center gap-2 px-2 py-1 text-xs"
                    >
                      <button
                        type="button"
                        className={`min-w-0 flex-1 truncate text-left ${index === activeIndex ? "font-medium text-foreground" : "text-muted-foreground"}`}
                        onClick={() => setActiveIndex(index)}
                        title={`${item.target.modelName} · ${item.target.upstreamName}`}
                      >
                        {item.target.modelName} · {item.target.upstreamName}
                      </button>
                      <span
                        className={
                          item.result?.success
                            ? "text-foreground"
                            : item.result
                              ? "text-destructive"
                              : "text-muted-foreground"
                        }
                      >
                        {item.result
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
                      {item.protocols.length === 1 && item.protocol ? (
                        <span
                          className="w-28 shrink-0 truncate text-right text-muted-foreground"
                          title={protocolLabel(item.protocol, locale)}
                        >
                          {protocolLabel(item.protocol, locale)}
                        </span>
                      ) : (
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
                            {item.protocols.map((value) => (
                              <SelectItem key={value} value={value}>
                                {protocolLabel(value, locale)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  ))}
                </div>
              ) : protocols && protocols.length > 1 ? (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {isChinese ? "测试协议" : "Test protocol"}
                  </span>
                  <Select
                    value={protocol ?? ""}
                    onValueChange={(value) =>
                      onProtocolChange?.(value as ProtocolKind)
                    }
                    disabled={testing}
                  >
                    <SelectTrigger
                      className="h-8 min-w-44 max-w-60"
                      aria-label={isChinese ? "测试协议" : "Test protocol"}
                    >
                      <SelectValue
                        placeholder={isChinese ? "选择协议" : "Choose protocol"}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {protocols.map((value) => (
                        <SelectItem key={value} value={value}>
                          {protocolLabel(value, locale)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {isChinese ? "测试输入" : "Test input"}
                </span>
                <Select
                  value={promptMode}
                  onValueChange={onPromptModeChange}
                  disabled={testing}
                >
                  <SelectTrigger
                    className="h-7 w-32"
                    aria-label={isChinese ? "预设问题" : "Preset prompt"}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {prompts.map((_, index) => (
                      <SelectItem key={index} value={String(index)}>
                        {isChinese
                          ? `预设 ${index + 1}`
                          : `Preset ${index + 1}`}
                      </SelectItem>
                    ))}
                    <SelectItem value="custom">
                      {isChinese ? "自定义" : "Custom"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Textarea
                className="min-h-16 resize-y text-xs"
                value={prompt}
                onChange={(event) => onPromptChange(event.target.value)}
                disabled={testing}
                maxLength={2000}
                aria-label={isChinese ? "测试输入内容" : "Test input content"}
              />
            </div>
            {result ? (
              <div className="space-y-4">
                <div className="grid gap-x-5 gap-y-1.5 pt-3 sm:grid-cols-2">
                  <Detail
                    label={isChinese ? "上游" : "Upstream"}
                    value={target?.upstreamName || "-"}
                  />
                  <Detail
                    label={isChinese ? "端点" : "Endpoint"}
                    value={protocol ? protocolLabel(protocol, locale) : "-"}
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
                    label={isChinese ? "延迟" : "Latency"}
                    value={`${result.latency_ms} ms`}
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
                      className={`inline-flex items-center gap-2 text-xs font-medium ${
                        result.success ? "text-foreground" : "text-destructive"
                      }`}
                    >
                      <span
                        className={`size-1.5 rounded-full ${result.success ? "bg-foreground" : "bg-destructive"}`}
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
                  <TabsContent value="request" className="space-y-3">
                    <DebugBlock
                      label={isChinese ? "请求头" : "Request headers"}
                      value={requestHeaders}
                    />
                    <DebugBlock
                      label={isChinese ? "内容" : "Body"}
                      value={requestBody}
                    />
                  </TabsContent>
                  <TabsContent value="response" className="space-y-3">
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
            ) : (
              <div className="flex h-40 items-center justify-center text-xs text-muted-foreground">
                {testing ? (
                  <>
                    <Spinner />
                    {isChinese ? "正在测试" : "Testing"}
                  </>
                ) : isChinese ? (
                  "暂无测试结果"
                ) : (
                  "No test result"
                )}
              </div>
            )}
          </div>

          <DialogFooter className="shrink-0 px-5 py-3">
            {onDelete && !testing ? (
              <Button
                type="button"
                variant="ghost"
                className="mr-auto text-destructive hover:text-destructive"
                onClick={() => setConfirmDeleteOpen(true)}
              >
                {isChinese ? "删除此模型" : "Delete model"}
              </Button>
            ) : null}
            <Button type="button" size="sm" onClick={onRun} disabled={!canRun}>
              {testing ? <Spinner /> : null}
              {items.length > 1
                ? isChinese
                  ? "测试全部"
                  : "Test all"
                : isChinese
                  ? "开始测试"
                  : "Start test"}
            </Button>
            <Button type="button" size="sm" onClick={onClose}>
              {isChinese ? "关闭" : "Close"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>
              {isChinese ? "删除模型绑定" : "Delete model binding"}
            </DialogTitle>
            <DialogDescription>
              {isChinese
                ? `从当前渠道移除「${target?.modelName || "-"}」的绑定？保存后生效。`
                : `Remove the binding for "${target?.modelName || "-"}" from this channel? Changes take effect after saving.`}
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
