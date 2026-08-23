import type { Dispatch, SetStateAction } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ProtocolConfigItem } from "./ChannelProtocolConfig";
import type { FormProtocolConfig, FormState, Locale } from "./channelShared";

type Props = {
  form: FormState;
  locale: Locale;
  fetchingProtocolConfigIndex: number | null;
  duplicatedProtocolConfigKeys: Set<string>;
  setForm: Dispatch<SetStateAction<FormState>>;
  setAdvancedProtocolConfigIndex: Dispatch<SetStateAction<number | null>>;
  addProtocolConfig: () => void;
  updateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  addManualProtocolConfigModel: (protocolConfigIndex: number) => void;
  fetchProtocolModels: (protocolConfigIndex: number) => void;
};

/** Renders all protocol configurations for a channel. */
export function ChannelProtocolSection({
  form,
  locale,
  fetchingProtocolConfigIndex,
  duplicatedProtocolConfigKeys,
  setForm,
  setAdvancedProtocolConfigIndex,
  addProtocolConfig,
  updateProtocolConfig,
  addManualProtocolConfigModel,
  fetchProtocolModels,
}: Props) {
  return (
    <div className="grid gap-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="text-base font-semibold text-foreground">
          {locale === "zh-CN" ? "上游协议配置" : "Upstream protocol configs"}
        </div>
        <Button
          type="button"
          variant="outline"
          className="justify-start border-dashed"
          onClick={addProtocolConfig}
        >
          <Plus data-icon="inline-start" />
          {locale === "zh-CN" ? "增加协议配置" : "Add protocol config"}
        </Button>
      </div>
      <div className="grid gap-3">
        {form.protocolConfigs.map((protocolConfig, protocolConfigIndex) => (
          <ProtocolConfigItem
            key={protocolConfig.id}
            form={form}
            protocolConfig={protocolConfig}
            protocolConfigIndex={protocolConfigIndex}
            locale={locale}
            fetchingProtocolConfigIndex={fetchingProtocolConfigIndex}
            duplicatedProtocolConfigKeys={duplicatedProtocolConfigKeys}
            onUpdateProtocolConfig={updateProtocolConfig}
            onRemoveProtocolConfig={(index) =>
              setForm((current) => ({
                ...current,
                protocolConfigs:
                  current.protocolConfigs.length > 1
                    ? current.protocolConfigs.filter(
                        (_, currentIndex) => currentIndex !== index,
                      )
                    : current.protocolConfigs,
              }))
            }
            onAddManualModel={addManualProtocolConfigModel}
            onFetchModels={fetchProtocolModels}
            onOpenAdvanced={setAdvancedProtocolConfigIndex}
          />
        ))}
      </div>
    </div>
  );
}
