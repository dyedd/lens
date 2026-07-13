import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import type { ProtocolKind } from "@/lib/api";
import type { AggregatedModel } from "./useAggregatedModels";
import type {
  BatchModelTestOption,
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
  FormState,
  Locale,
  TestableModelOption,
} from "./channelShared";

export type ChannelEditorDialogProps = {
  isDialogOpen: boolean;
  hasUnsavedChanges: boolean;
  editingSiteId: string | null;
  locale: Locale;
  form: FormState;
  fetchingProtocolConfigIndex: number | null;
  duplicatedProtocolConfigKeys: Set<string>;
  batchTestOptions: BatchModelTestOption[];
  isBatchModelTestRunning: boolean;
  testingModel: boolean;
  isEnsuringModelGroups: boolean;
  overviewModels: AggregatedModel[];
  modelTestOptionByKey: Map<string, TestableModelOption>;
  setIsDialogOpen: Dispatch<SetStateAction<boolean>>;
  setEditingSiteId: Dispatch<SetStateAction<string | null>>;
  setForm: Dispatch<SetStateAction<FormState>>;
  setAdvancedProtocolConfigIndex: Dispatch<SetStateAction<number | null>>;
  submit: FormEventHandler<HTMLFormElement>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (index: number, patch: Partial<FormCredential>) => void;
  removeCredential: (index: number) => void;
  addProtocolConfig: () => void;
  updateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  addManualProtocolConfigModel: (protocolConfigIndex: number) => void;
  fetchProtocolModels: (protocolConfigIndex: number) => void;
  openModelGroupEnsureDialog: () => void;
  openBatchModelTestDialog: () => void;
  updateModelProtocols: (
    modelKey: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  openAggregateModelTest: (modelKey: string) => void;
  removeAggregateModel: (modelKey: string) => void;
  clearAggregateModels: () => void;
  closeEditor: () => void;
};
