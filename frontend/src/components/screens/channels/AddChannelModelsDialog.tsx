import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Label } from "@/components/ui/Label";
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
}: {
  open: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onAddBinding: (names: string, protocols: ProtocolKind[]) => boolean;
}) {
  const [newName, setNewName] = useState("");
  const [newProtocols, setNewProtocols] = useState<ProtocolKind[]>(["auto"]);
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
                if (onAddBinding(newName, newProtocols)) {
                  setNewName("");
                  setNewProtocols(["auto"]);
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
              className="max-h-48 font-mono"
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
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
