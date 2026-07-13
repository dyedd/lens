"use client";

import { startTransition, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog, DialogFooter } from "@/components/ui/Dialog";
import { FieldGroup } from "@/components/ui/Field";
import { type GatewayApiKey, apiRequest, getApiErrorMessage } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { GatewayApiKeyBasicFields } from "./GatewayApiKeyBasicFields";
import { GatewayApiKeyExpiryField } from "./GatewayApiKeyExpiryField";
import { GatewayApiKeyModelPermissions } from "./GatewayApiKeyModelPermissions";
import {
  toGatewayApiKeyForm,
  toGatewayApiKeyPayload,
  type GatewayApiKeyForm,
  type GatewayModelGroupOption,
} from "./gatewayApiKeyUtils";

export type GatewayApiKeyDialogProps = {
  locale: Locale;
  open: boolean;
  editingKey: GatewayApiKey | null;
  modelGroupOptions: GatewayModelGroupOption[];
  timeZone: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

/** Renders the create and edit dialog for gateway API keys. */
export function GatewayApiKeyDialog({
  locale,
  open,
  editingKey,
  modelGroupOptions,
  timeZone,
  onClose,
  onSaved,
}: GatewayApiKeyDialogProps) {
  const [form, setForm] = useState<GatewayApiKeyForm>(() =>
    toGatewayApiKeyForm(editingKey ?? undefined, timeZone),
  );
  const [submitting, setSubmitting] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(toGatewayApiKeyForm(editingKey ?? undefined, timeZone));
      setPickerOpen(false);
    }
  }, [open, editingKey, timeZone]);

  const editingKeyId = editingKey?.id ?? null;

  function updateForm<K extends keyof GatewayApiKeyForm>(
    key: K,
    value: GatewayApiKeyForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleAllowedModel(name: string) {
    startTransition(() => {
      setForm((current) => {
        const exists = current.allowedModels.includes(name);
        return {
          ...current,
          allowedModels: exists
            ? current.allowedModels.filter((item) => item !== name)
            : [...current.allowedModels, name].sort((left, right) =>
                left.localeCompare(right),
              ),
        };
      });
    });
  }

  async function submit() {
    if (form.isModelRestrictionEnabled && form.allowedModels.length === 0) {
      toast.error(
        titleForLocale(
          locale,
          "至少选择一个模型组",
          "Select at least one model group",
        ),
      );
      return;
    }
    setSubmitting(true);
    try {
      const payload = toGatewayApiKeyPayload(form, timeZone);
      if (editingKeyId) {
        await apiRequest<GatewayApiKey>(
          `/admin/gateway-api-keys/${editingKeyId}`,
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
        );
      } else {
        await apiRequest<GatewayApiKey>("/admin/gateway-api-keys", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      toast.success(
        titleForLocale(
          locale,
          editingKeyId ? "API Key 已更新" : "API Key 已创建",
          editingKeyId ? "API key updated" : "API key created",
        ),
      );
      onClose();
      await onSaved();
    } catch (requestError) {
      const message = getApiErrorMessage(
        requestError,
        titleForLocale(
          locale,
          editingKeyId ? "更新 API Key 失败" : "创建 API Key 失败",
          editingKeyId
            ? "Failed to update API key"
            : "Failed to create API key",
        ),
      );
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setPickerOpen(false);
          onClose();
        }
      }}
    >
      <AppDialogContent
        className="sm:max-w-xl"
        title={titleForLocale(
          locale,
          editingKeyId ? "编辑 API Key" : "创建 API Key",
          editingKeyId ? "Edit API key" : "Create API key",
        )}
      >
        <div className="flex flex-col gap-4">
          <FieldGroup>
            <GatewayApiKeyBasicFields
              locale={locale}
              remark={form.remark}
              enabled={form.enabled}
              maxCostUsd={form.maxCostUsd}
              onRemarkChange={(value) => updateForm("remark", value)}
              onEnabledChange={(value) => updateForm("enabled", value)}
              onMaxCostUsdChange={(value) => updateForm("maxCostUsd", value)}
            />
            <GatewayApiKeyModelPermissions
              locale={locale}
              isRestrictionEnabled={form.isModelRestrictionEnabled}
              allowedModels={form.allowedModels}
              modelGroupOptions={modelGroupOptions}
              pickerOpen={pickerOpen}
              onPickerOpenChange={setPickerOpen}
              onRestrictionEnabledChange={(enabled) => {
                startTransition(() => {
                  updateForm("isModelRestrictionEnabled", enabled);
                });
              }}
              onToggleAllowedModel={toggleAllowedModel}
            />
            <GatewayApiKeyExpiryField
              locale={locale}
              expiresOn={form.expiresOn}
              onChange={(value) => updateForm("expiresOn", value)}
            />
          </FieldGroup>

          <DialogFooter className="mx-0 mb-0 rounded-none border-0 bg-transparent p-0 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              onClick={() => void submit()}
              disabled={submitting}
            >
              {submitting
                ? titleForLocale(locale, "保存中...", "Saving...")
                : titleForLocale(locale, "保存", "Save")}
            </Button>
          </DialogFooter>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
