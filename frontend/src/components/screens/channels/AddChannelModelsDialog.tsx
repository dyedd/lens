import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Label } from "@/components/ui/Label";
import { Textarea } from "@/components/ui/Textarea";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Locale } from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";

/** Collects manually entered upstream model names. */
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
        title={locale === "zh-CN" ? "手动添加模型" : "Add models manually"}
        description={
          locale === "zh-CN"
            ? "每行或用逗号分隔一个模型名，会加到所有密钥下。手动模型不受自动同步影响。"
            : "One model name per line or comma-separated, added for every key. Manual models are never changed by auto-sync."
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
              {locale === "zh-CN" ? "创建" : "Create"}
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
              {locale === "zh-CN" ? "上游模型名" : "Upstream model names"}
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
              {locale === "zh-CN" ? "转发方式" : "Forwarding"}
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
