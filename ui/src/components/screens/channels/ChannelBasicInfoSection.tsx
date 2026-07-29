import type { Dispatch, SetStateAction } from "react";
import { CircleHelp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { ChannelBaseUrlSection } from "./ChannelBaseUrlSection";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import type {
  FormBaseUrl,
  FormCredential,
  FormState,
  Locale,
} from "./channelShared";

type Props = {
  form: FormState;
  locale: Locale;
  setForm: Dispatch<SetStateAction<FormState>>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (index: number, patch: Partial<FormCredential>) => void;
  removeCredential: (index: number) => void;
};

/** Renders the channel name, base URL, and credential fields. */
export function ChannelBasicInfoSection({
  form,
  locale,
  setForm,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  updateCredential,
  removeCredential,
}: Props) {
  return (
    <section className="grid gap-5">
      <div className="text-base font-semibold text-foreground">
        {locale === "zh-CN" ? "基本信息" : "Channel and keys"}
      </div>
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
          <Field>
            <FieldLabel htmlFor="channel-name">
              {locale === "zh-CN" ? "渠道名称" : "Channel name"}
            </FieldLabel>
            <Input
              id="channel-name"
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
            />
          </Field>
          <Field>
            <div className="flex items-center gap-1">
              <FieldLabel htmlFor="channel-priority">
                {locale === "zh-CN" ? "渠道优先级" : "Priority"}
              </FieldLabel>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    aria-label={
                      locale === "zh-CN"
                        ? "查看渠道优先级说明"
                        : "About channel priority"
                    }
                  >
                    <CircleHelp />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {locale === "zh-CN"
                    ? "仅故障转移策略生效，数值越大越优先"
                    : "Failover only; higher values are preferred"}
                </TooltipContent>
              </Tooltip>
            </div>
            <Input
              id="channel-priority"
              type="number"
              min={0}
              step={1}
              value={form.priority}
              onChange={(event) => {
                const value = event.target.valueAsNumber;
                if (!Number.isFinite(value)) return;
                setForm((current) => ({
                  ...current,
                  priority: Math.max(0, Math.trunc(value)),
                }));
              }}
            />
          </Field>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <ChannelBaseUrlSection
            baseUrls={form.base_urls}
            locale={locale}
            onAdd={addBaseUrl}
            onUpdate={updateBaseUrl}
            onRemove={removeBaseUrl}
          />
          <ChannelCredentialSection
            credentials={form.credentials}
            locale={locale}
            onAdd={(credential) =>
              setForm((current) => ({
                ...current,
                credentials: [...current.credentials, credential],
              }))
            }
            onUpdate={updateCredential}
            onRemove={removeCredential}
          />
        </div>
      </FieldGroup>
    </section>
  );
}
