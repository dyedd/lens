import type { BatchModelTestRow } from "@/components/model-test/batchModelTestSession";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Locale } from "./channelTypes";
import { ModelTestDialog } from "./ModelTestDialog";

type Props = {
  locale: Locale;
  targetName: string;
  rows: BatchModelTestRow[];
  testing: boolean;
  onClose: () => void;
  prompts: string[];
  promptMode: string;
  prompt: string;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onProtocolChange: (key: string, protocol: ProtocolKind) => void;
  onRun: () => void;
};

export function BatchModelTestDialog({
  locale,
  targetName,
  rows,
  testing,
  onClose,
  prompts,
  promptMode,
  prompt,
  onPromptModeChange,
  onPromptChange,
  onProtocolChange,
  onRun,
}: Props) {
  return (
    <ModelTestDialog
      locale={locale}
      targetName={targetName}
      prompts={prompts}
      promptMode={promptMode}
      prompt={prompt}
      onPromptModeChange={onPromptModeChange}
      onPromptChange={onPromptChange}
      onRun={onRun}
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
