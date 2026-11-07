import type { BatchModelTestRow } from "@/components/model-test/batchModelTestSession";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { ModelTestMode } from "@/lib/api/sites";
import type { Locale } from "@/lib/I18nContext";
import { ModelTestDialog } from "./ModelTestDialog";

type Props = {
  locale: Locale;
  targetName: string;
  rows: BatchModelTestRow[];
  testing: boolean;
  onClose: () => void;
  mode: ModelTestMode;
  onModeChange: (mode: ModelTestMode) => void;
  onProtocolChange: (key: string, protocol: ProtocolKind) => void;
  onRun: () => void;
};

export function BatchModelTestDialog({
  locale,
  targetName,
  rows,
  testing,
  onClose,
  mode,
  onModeChange,
  onProtocolChange,
  onRun,
}: Props) {
  return (
    <ModelTestDialog
      locale={locale}
      targetName={targetName}
      mode={mode}
      onModeChange={onModeChange}
      onRun={onRun}
      onProtocolChangeAll={(protocol) => {
        for (const row of rows) {
          if (row.protocol !== protocol && row.protocols.includes(protocol)) {
            onProtocolChange(row.key, protocol);
          }
        }
      }}
      items={rows.map((row) => ({
        target: {
          modelName: row.modelName,
          upstreamName: row.credentialName,
        },
        result: row.result ?? null,
        protocol: row.protocol,
        protocols: row.protocols,
        onProtocolChange: (protocol) => onProtocolChange(row.key, protocol),
      }))}
      testing={testing}
      onClose={onClose}
    />
  );
}
