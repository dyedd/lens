import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Locale } from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";

/** Collects model names that should be tracked in the upstream catalog. */
export function AddChannelModelsDialog({
  open,
  locale,
  onOpenChange,
  onAddBinding,
  groupOptions,
}: {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onAddBinding: (
    names: string,
    protocols: ProtocolKind[],
    groupId?: string,
  ) => boolean;
  /** Execution groups the new models can join after the channel is saved. */
  groupOptions: Array<{ id: string; name: string }>;
}) {
  const [newName, setNewName] = useState("");
  const [newProtocols, setNewProtocols] = useState<ProtocolKind[]>(["auto"]);
  const [targetGroupId, setTargetGroupId] = useState("__auto__");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-md"
        title={locale === "zh-CN" ? "添加模型" : "Add models"}
        description={
          locale === "zh-CN"
            ? "每行输入一个模型名，也可用逗号分隔。模型会添加到所有 API Key，并按上游列表持续同步。"
            : "Enter one model name per line or separate names with commas. Models are added to every API key and remain tracked in the upstream catalog."
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!newName.trim() || newProtocols.length === 0}
              onClick={() => {
                if (
                  onAddBinding(
                    newName,
                    newProtocols,
                    targetGroupId === "__auto__" ? undefined : targetGroupId,
                  )
                ) {
                  setNewName("");
                  setNewProtocols(["auto"]);
                  setTargetGroupId("__auto__");
                  onOpenChange(false);
                }
              }}
            >
              {locale === "zh-CN" ? "添加" : "Add"}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          <div className="min-w-0 space-y-1">
            <Label
              required
              className="text-xs font-normal text-muted-foreground"
            >
              {locale === "zh-CN" ? "模型名（上游）" : "Upstream model names"}
            </Label>
            <Textarea
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder={"gpt-4o\ngpt-4o-mini"}
              className="max-h-48 font-mono placeholder:font-sans"
            />
          </div>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "转发协议" : "Forwarding"}
            </FieldLabel>
            <ProtocolDropdown
              value={newProtocols}
              locale={locale}
              onChange={setNewProtocols}
            />
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "添加后归入" : "Join group"}
            </FieldLabel>
            <Select value={targetGroupId} onValueChange={setTargetGroupId}>
              <SelectTrigger
                aria-label={
                  locale === "zh-CN" ? "添加后归入模型组" : "Group to join"
                }
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__auto__">
                  {locale === "zh-CN"
                    ? "不指定（按同名自动归组）"
                    : "Automatic"}
                </SelectItem>
                {groupOptions.map((group) => (
                  <SelectItem key={group.id} value={group.id}>
                    {group.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
