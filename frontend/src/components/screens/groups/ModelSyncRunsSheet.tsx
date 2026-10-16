import { useQuery } from "@tanstack/react-query";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
import { Badge } from "@/components/ui/Badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import { Spinner } from "@/components/ui/Spinner";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest } from "@/lib/api/client";
import type { ModelGroupMemberChange } from "@/lib/api/groups";
import type { ChannelModelSyncResponse } from "@/lib/api/sites";
import { formatLogDateTime } from "@/lib/datetime";

type Locale = "zh-CN" | "en-US";

interface ModelSyncRunsSheetProps {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
}

type RunSection = { key: string; title: string; lines: string[] };

function formatChange(change: ModelGroupMemberChange, locale: Locale) {
  const where = [change.channel_name, change.credential_name]
    .filter(Boolean)
    .join(" · ");
  return locale === "zh-CN"
    ? `${change.model_name} → ${change.group_name}${where ? `（${where}）` : ""}`
    : `${change.model_name} → ${change.group_name}${where ? ` (${where})` : ""}`;
}

/** Turn one run into the stage sections that changed, in pipeline order. */
function buildRunSections(
  run: ChannelModelSyncResponse,
  locale: Locale,
): RunSection[] {
  const isZh = locale === "zh-CN";
  const catalogLines = (field: "added" | "missing" | "restored") =>
    run.items
      .filter((item) => item[field].length)
      .map(
        (item) =>
          `${item.site_name} · ${item.credential_name || item.credential_id}：${item[field].join("、")}`,
      );
  const sections: RunSection[] = [
    {
      key: "failed",
      title: isZh ? "拉取失败" : "Fetch failed",
      lines: run.items
        .filter((item) => item.status === "failed")
        .map(
          (item) =>
            `${item.site_name} · ${item.credential_name || item.credential_id}：${item.error}`,
        ),
    },
    {
      key: "models-added",
      title: isZh ? "新增模型" : "New models",
      lines: catalogLines("added"),
    },
    {
      key: "created",
      title: isZh ? "新建模型组" : "Groups created",
      lines: run.groups.created_groups.map((group) => group.name),
    },
    {
      key: "joined",
      title: isZh ? "加入模型组" : "Joined groups",
      lines: run.groups.added.map((change) => formatChange(change, locale)),
    },
    {
      key: "pending",
      title: isZh ? "等你确认" : "Needs your call",
      lines: run.groups.pending.map((model) =>
        model.similar_group_names.length
          ? isZh
            ? `${model.model_name}：建议加入 ${model.similar_group_names.join("、")}`
            : `${model.model_name}: suggested group ${model.similar_group_names.join(", ")}`
          : model.similar_model_names.length
            ? isZh
              ? `${model.model_name}：和 ${model.similar_model_names.join("、")} 名字相近`
              : `${model.model_name}: close to ${model.similar_model_names.join(", ")}`
            : model.model_name,
      ),
    },
    {
      key: "removed",
      title: isZh ? "不再匹配规则" : "No longer matched",
      lines: run.groups.removed.map((change) => formatChange(change, locale)),
    },
    {
      key: "missing",
      title: isZh ? "上游缺失" : "Missing upstream",
      lines: catalogLines("missing"),
    },
    {
      key: "retired",
      title: isZh
        ? "上游缺失超过 7 天，已移出模型组"
        : "Removed after 7 days missing upstream",
      lines: run.groups.retired.map((change) => formatChange(change, locale)),
    },
    {
      key: "restored",
      title: isZh ? "上游已恢复" : "Back upstream",
      lines: catalogLines("restored"),
    },
  ];
  return sections.filter((section) => section.lines.length);
}

function formatRunSummary(run: ChannelModelSyncResponse, locale: Locale) {
  const isZh = locale === "zh-CN";
  const count = (field: "added" | "missing") =>
    new Set(run.items.flatMap((item) => item[field])).size;
  const failed = run.items.filter((item) => item.status === "failed").length;
  const parts = [
    count("added") &&
      (isZh ? `新增 ${count("added")}` : `${count("added")} new`),
    run.groups.created_groups.length &&
      (isZh
        ? `建组 ${run.groups.created_groups.length}`
        : `${run.groups.created_groups.length} groups`),
    run.groups.pending.length &&
      (isZh
        ? `待确认 ${run.groups.pending.length}`
        : `${run.groups.pending.length} pending`),
    count("missing") &&
      (isZh ? `缺失 ${count("missing")}` : `${count("missing")} missing`),
    run.groups.retired.length &&
      (isZh
        ? `退场 ${run.groups.retired.length}`
        : `${run.groups.retired.length} retired`),
    failed && (isZh ? `失败 ${failed}` : `${failed} failed`),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : isZh ? "无变化" : "No changes";
}

/** Show recorded model sync runs and what each pipeline stage changed. */
export function ModelSyncRunsSheet({
  open,
  locale,
  onOpenChange,
}: ModelSyncRunsSheetProps) {
  const isZh = locale === "zh-CN";
  const timeZone = useAppTimeZone();
  const runsQuery = useQuery({
    queryKey: ["groups", "model-sync-runs"],
    queryFn: () =>
      apiRequest<ChannelModelSyncResponse[]>("/admin/model-sync-runs?limit=30"),
    enabled: open,
  });
  const runs = runsQuery.data ?? [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex flex-col gap-0 sm:max-w-[560px]">
        <SheetHeader className="shrink-0 px-4 py-4 pr-14">
          <SheetTitle>{isZh ? "同步记录" : "Sync history"}</SheetTitle>
          <SheetDescription className="mt-1 text-xs">
            {isZh
              ? "每次模型同步新增了哪些模型、进了哪些组、哪些等你确认、哪些已退场。"
              : "What each model sync added, where models went, what needs your call, and what retired."}
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 pb-6">
          {runsQuery.isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : runsQuery.isError ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {isZh ? "同步记录加载失败" : "Failed to load sync history"}
            </p>
          ) : !runs.length ? (
            <p className="rounded-md bg-muted/35 px-3 py-6 text-center text-xs text-muted-foreground">
              {isZh
                ? "还没有同步记录。渠道保存后和定时任务运行时会自动记录同步结果。"
                : "No sync runs yet. Runs are recorded after channel saves and scheduled syncs."}
            </p>
          ) : (
            <Accordion type="multiple" className="border-y border-border/60">
              {runs.map((run) => {
                const sections = buildRunSections(run, locale);
                return (
                  <AccordionItem key={run.id} value={run.id}>
                    <AccordionTrigger className="items-center py-3 text-xs hover:no-underline">
                      <span className="flex min-w-0 flex-1 items-center justify-between gap-3 pr-2">
                        <span className="font-medium tabular-nums">
                          {run.started_at
                            ? formatLogDateTime(
                                run.started_at,
                                locale,
                                timeZone,
                              )
                            : ""}
                        </span>
                        <span className="truncate font-normal text-muted-foreground">
                          {formatRunSummary(run, locale)}
                        </span>
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="flex flex-col gap-3">
                      {sections.length ? (
                        sections.map((section) => (
                          <div
                            key={section.key}
                            className="flex flex-col gap-1"
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-medium">
                                {section.title}
                              </span>
                              <Badge variant="secondary">
                                {section.lines.length}
                              </Badge>
                            </div>
                            <ul className="flex flex-col gap-0.5 rounded-md bg-muted/35 px-3 py-2">
                              {section.lines.map((line) => (
                                <li
                                  key={line}
                                  className="break-all font-mono text-[11px] text-muted-foreground"
                                >
                                  {line}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          {isZh
                            ? "这次同步没有带来变化。"
                            : "This sync changed nothing."}
                        </p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
