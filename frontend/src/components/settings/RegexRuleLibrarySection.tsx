import { Pencil, Plus, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";

import {
  DeleteRegexRuleDialog,
  RegexRuleEditorDialog,
} from "@/components/ruleEditors/RegexRuleDialogs";
import { Button } from "@/components/ui/Button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { TabsContent } from "@/components/ui/Tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useRegexRules } from "@/hooks/useRegexRules";
import type { RegexRule } from "@/lib/api/regexRules";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import {
  formatRegexRuleUsage,
  listRegexRuleUsageLines,
} from "@/lib/regexRules";
import { SettingsSectionCard } from "./SettingsSectionCard";

function RowAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground shadow-none"
          aria-label={label}
          onClick={onClick}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function RegexRuleUsage({ rule, locale }: { rule: RegexRule; locale: Locale }) {
  const usageLines = listRegexRuleUsageLines(rule, locale);
  const usage = formatRegexRuleUsage(rule, locale);
  if (!usageLines.length) return usage;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-default">{usage}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm flex-col items-start gap-0.5">
        {usageLines.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </TooltipContent>
    </Tooltip>
  );
}

/** Render the regex rule library that channels and groups reference. */
export function RegexRuleLibrarySection({ locale }: { locale: Locale }) {
  const library = useRegexRules();
  const [editor, setEditor] = useState<{ rule: RegexRule | null } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RegexRule | null>(null);
  const statusLabel = library.isError
    ? titleForLocale(locale, "规则库加载失败", "Failed to load rules")
    : !library.isLoaded
      ? titleForLocale(locale, "加载中...", "Loading...")
      : !library.rules.length
        ? titleForLocale(locale, "暂无规则", "No rules")
        : "";

  return (
    <TabsContent value="regex-rules" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "正则规则库", "Regex library")}
        actions={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
            onClick={() => setEditor({ rule: null })}
            disabled={!library.isLoaded}
          >
            <Plus className="size-3.5" />
            {titleForLocale(locale, "添加规则", "Add rule")}
          </Button>
        }
      >
        <p className="text-xs text-muted-foreground">
          {titleForLocale(
            locale,
            "渠道同步过滤和模型组匹配引用这里的规则，匹配不区分大小写；修改或删除规则会立即作用于所有使用处。",
            "Channel sync filters and group match rules reference these rules; matching is case-insensitive. Editing or deleting a rule applies everywhere it is used.",
          )}
        </p>
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-40">
                {titleForLocale(locale, "名称", "Name")}
              </TableHead>
              <TableHead>{titleForLocale(locale, "正则", "Pattern")}</TableHead>
              <TableHead>
                {titleForLocale(locale, "说明", "Description")}
              </TableHead>
              <TableHead>{titleForLocale(locale, "使用", "Usage")}</TableHead>
              <TableHead className="w-20 text-right">
                {titleForLocale(locale, "操作", "Actions")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {statusLabel ? (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={5}
                  className="h-32 text-center text-muted-foreground"
                >
                  {statusLabel}
                </TableCell>
              </TableRow>
            ) : null}
            {library.rules.map((rule) => (
              <TableRow key={rule.id}>
                <TableCell className="font-medium">{rule.name}</TableCell>
                <TableCell className="whitespace-normal break-all font-mono">
                  {rule.pattern}
                </TableCell>
                <TableCell className="whitespace-normal break-words text-muted-foreground">
                  {rule.description}
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  <RegexRuleUsage rule={rule} locale={locale} />
                </TableCell>
                <TableCell className="w-20">
                  <div className="flex justify-end gap-1">
                    <RowAction
                      label={titleForLocale(locale, "编辑规则", "Edit rule")}
                      onClick={() => setEditor({ rule })}
                    >
                      <Pencil />
                    </RowAction>
                    <RowAction
                      label={titleForLocale(locale, "删除规则", "Delete rule")}
                      onClick={() => setDeleteTarget(rule)}
                    >
                      <Trash2 />
                    </RowAction>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SettingsSectionCard>
      {editor ? (
        <RegexRuleEditorDialog
          locale={locale}
          rule={editor.rule}
          onClose={() => setEditor(null)}
        />
      ) : null}
      {deleteTarget ? (
        <DeleteRegexRuleDialog
          locale={locale}
          rule={deleteTarget}
          onClose={() => setDeleteTarget(null)}
        />
      ) : null}
    </TabsContent>
  );
}
